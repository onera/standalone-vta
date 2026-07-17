package fpga.synthesis

import scopt.OParser

/** Strb-aware comparison of an xsim post-synth run's OUT writes against the
  * fsim golden. Ported from postsynth/compare_out.py.
  *
  * Reads writes.log ("addr data strb last" from sim_top.sv's io_dbgW snoop),
  * reconstructs each layer's OUT buffer applying the per-beat 8-bit write
  * strobe, and compares to simulators_output/output<layer>.bin.
  *
  * Address model (mirrors CompilerOutputLayout): layer L (0-based in --layers)
  * is relocated by relo = L * reloStride; a beat at absolute byte A belongs to
  * layer A / reloStride, at offset A - L*reloStride - OUT_base, where OUT_base
  * is the "OUT" row of compiler_output/memory_addresses<layer>.csv.
  *
  * Note: compares the whole OUT buffer including block-padding lanes. When a
  * layer's output-channel count is not a multiple of the block size the
  * hardware leaves the padding lanes non-zero while the golden zeroes them, so
  * those lanes report as mismatches even though the valid channels are
  * byte-exact; the next layer ignores the padding, so such a partial conv
  * mismatch is benign.
  */
object CompareOut {

  def main(args: Array[String]): Unit = sys.exit(run(args))

  private case class Opts(
    writes: String = "",
    layers: String = "",
    compilerOut: String = "",
    goldenDir: String = "",
    reloStride: String = "0x200000",
    show: Int = 8
  )

  private val argParser: OParser[_, Opts] = {
    val b = OParser.builder[Opts]
    import b._
    OParser.sequence(
      programName("compareOut"),
      opt[String]("writes").required().action((x, c) => c.copy(writes = x)),
      opt[String]("layers")
        .required()
        .action((x, c) => c.copy(layers = x))
        .text("comma-separated, in emit order"),
      opt[String]("compiler-out")
        .required()
        .action((x, c) => c.copy(compilerOut = x)),
      opt[String]("golden-dir")
        .required()
        .action((x, c) => c.copy(goldenDir = x)),
      opt[String]("relo-stride").action((x, c) => c.copy(reloStride = x)),
      opt[Int]("show").action((x, c) => c.copy(show = x))
    )
  }

  private def parseHex(s: String): Long =
    java.lang.Long.parseUnsignedLong(s.stripPrefix("0x"), 16)

  /** OUT base address from compiler_output/memory_addresses<layer>.csv. */
  private def outBase(compilerOut: os.Path, layer: String): Long = {
    val path = compilerOut / s"memory_addresses$layer.csv"
    os.read
      .lines(path)
      .iterator
      .map(_.split(",").map(_.trim))
      .collectFirst {
        case p if p.length >= 3 && p(0) == "OUT" => parseHex(p(1))
      }
      .getOrElse(sys.error(s"no OUT row in $path"))
  }

  /** writes.log -> layerIdx -> (absByteAddr -> byteValue), applying strb. */
  private def parseWrites(
    writesPath: os.Path,
    reloStride: Long
  ): Map[Long, scala.collection.mutable.Map[Long, Int]] = {
    val perLayer = scala.collection.mutable
      .Map[Long, scala.collection.mutable.Map[Long, Int]]()
    os.read.lines(writesPath).foreach { raw =>
      val line = raw.trim
      if (line.nonEmpty) {
        val Array(a, d, s, _) = line.split("\\s+")
        val addr = parseHex(a)
        val data = parseHex(d) // 64-bit LE
        val strb = parseHex(s).toInt // 8-bit lane mask
        val lidx = addr / reloStride
        val bucket =
          perLayer.getOrElseUpdate(lidx, scala.collection.mutable.Map())
        (0 until 8).foreach { i =>
          if ((strb & (1 << i)) != 0)
            bucket(addr + i) = ((data >>> (8 * i)) & 0xff).toInt
        }
      }
    }
    perLayer.toMap
  }

  def run(argv: Array[String]): Int = {
    val o = OParser.parse(argParser, argv, Opts()) match {
      case Some(parsed) => parsed
      case _            => return 2
    }
    val reloStride = parseHex(o.reloStride)
    val layers = o.layers.split(",").map(_.trim).filter(_.nonEmpty).toSeq
    val compilerOut = os.Path(o.compilerOut, os.pwd)
    val goldenDir = os.Path(o.goldenDir, os.pwd)
    val perLayer = parseWrites(os.Path(o.writes, os.pwd), reloStride)

    var allOk = true
    layers.zipWithIndex.foreach { case (layer, idx) =>
      val goldenPath = goldenDir / s"output$layer.bin"
      if (!os.exists(goldenPath)) {
        println(s"[$layer] SKIP - no golden $goldenPath")
      } else {
        val golden = os.read.bytes(goldenPath)
        val base = outBase(compilerOut, layer)
        val relo = idx.toLong * reloStride
        val written =
          perLayer.getOrElse(idx.toLong, scala.collection.mutable.Map())
        var matched = 0
        val mism =
          scala.collection.mutable.ArrayBuffer[(Int, Int, Option[Int])]()
        golden.indices.foreach { off =>
          val absAddr = relo + base + off
          val got = written.get(absAddr)
          val exp = golden(off) & 0xff
          if (got.contains(exp)) matched += 1
          else if (mism.length < o.show) mism += ((off, exp, got))
        }
        val ok = matched == golden.length
        allOk &= ok
        val verdict = if (ok) "OK" else "MISMATCH"
        println(
          f"[$layer] $matched%d/${golden.length}%d bytes  base=0x${base.toHexString}%s relo=0x${relo.toHexString}%s  $verdict%s"
        )
        mism.foreach { case (off, exp, got) =>
          val gs = got.map(g => f"0x$g%02x").getOrElse("----")
          println(f"    off $off%6d: golden=0x$exp%02x got=$gs%s")
        }
      }
    }
    if (allOk) 0 else 1
  }
}
