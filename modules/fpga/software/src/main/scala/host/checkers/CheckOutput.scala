package fpga.host.checkers

import vta.parsers.Dependency._
import scopt.OParser
import fpga.host.parsers.ConfigParser

/** Compare a baremetal VTA output dump against the functional simulator's
  * final_output.bin (the source of truth).
  *
  * The board writes the output block-tiled; [[detile]] converts it to NCHW and
  * [[reportDiff]] diffs it against the reference.
  *
  * The block layout mirrors output_tensor()/unsplit() in
  * src/simulators/functional_simulator/include/cpu_functions.h: blocks are laid
  * out row-major over (N/B row-blocks, C/B col-blocks); within a block element
  * [rr][cc] maps to (spatial row rr, channel cc). The matrix is [N=H*W rows, C
  * cols].
  *
  * Translated from host/check_output.py.
  */
object CheckOutput {

  private def ceilDiv(a: Int, b: Int): Int = (a + b - 1) / b

  /** Block-tiled [N/B][C/B][B][B] -> NCHW flat [C][H*W]. Drops padding cells.
    *
    * Mirrors the Python detile() function exactly: same index formula
    * `(rb*Cb+cb)*B*B + rr*B + cc`.
    */
  def detile(raw: Array[Byte], C: Int, H: Int, W: Int, B: Int): Array[Byte] = {
    val N = H * W
    val Cb = ceilDiv(C, B)
    val expect = ceilDiv(N, B) * Cb * B * B
    require(
      raw.length >= expect,
      s"raw output too small: ${raw.length} < expected tiled $expect"
    )
    val out = new Array[Byte](C * N)
    for (n <- 0 until N) {
      val rb = n / B
      val rr = n % B
      for (c <- 0 until C) {
        val cb = c / B
        val cc = c % B
        out(c * N + n) = raw((rb * Cb + cb) * B * B + rr * B + cc)
      }
    }
    out
  }

  /** Diff two byte arrays as signed ints; print stats; return true if
    * identical.
    *
    * Mirrors the Python report_diff() function exactly, including the SIZE DIFF
    * / MATCH / MISMATCH output format and the context window (first-4 ..
    * first+12).
    */
  def reportDiff(name: String, a: Array[Byte], b: Array[Byte]): Boolean = {
    val n = math.min(a.length, b.length)
    if (a.length != b.length)
      println(
        s"[$name] SIZE DIFF: got ${a.length} vs ref ${b.length} (comparing first $n)"
      )
    val a32 = a.take(n).map(_.toInt)
    val b32 = b.take(n).map(_.toInt)
    val diff = a32.zip(b32).map { case (x, y) => x - y }
    val nz = diff.zipWithIndex.collect { case (v, i) if v != 0 => i }

    if (a.length == b.length && nz.isEmpty) {
      println(s"[$name] MATCH ($n elements identical)")
      return true
    }

    val first = if (nz.nonEmpty) nz(0) else -1
    val pct = 100.0 * nz.length / n
    val maxDiff = if (diff.nonEmpty) diff.map(math.abs).max else 0
    println(
      f"[$name] MISMATCH: ${nz.length}/$n differ ($pct%.3f%%)," +
        s" max|diff|=$maxDiff," +
        s" first @ idx $first"
    )
    if (first >= 0) {
      val lo = math.max(0, first - 4)
      val hi = math.min(n, first + 12)
      println(s"        idx[$lo:$hi] got = ${a32.slice(lo, hi).toList}")
      println(s"        idx[$lo:$hi] ref = ${b32.slice(lo, hi).toList}")
    }
    false
  }

  private case class Opts(
    baremetalOut: String = "",
    compDir: String = "compiler_output",
    simDir: String = "simulators_output",
    configJson: Option[String] = None,
    shape: Option[String] = None,
    ref: Option[String] = None,
    detiled: Boolean = false
  )

  private val argParser: OParser[_, Opts] = {
    val b = OParser.builder[Opts]
    import b._
    OParser.sequence(
      programName("checkOutput"),
      head(
        "checkOutput",
        "compare a baremetal VTA output dump against the fsim reference"
      ),
      arg[String]("<baremetal_output>")
        .action((x, c) => c.copy(baremetalOut = x))
        .text("baremetal output file (block-tiled or pre-detiled)"),
      opt[String]("comp-dir")
        .action((x, c) => c.copy(compDir = x))
        .text("compiler output directory (default compiler_output)"),
      opt[String]("sim-dir")
        .action((x, c) => c.copy(simDir = x))
        .text("simulator output directory (default simulators_output)"),
      opt[String]("config-json")
        .action((x, c) => c.copy(configJson = Some(x)))
        .text("path to vta_config.json (default: Chisel DefaultPynqConfig)"),
      opt[String]("shape")
        .action((x, c) => c.copy(shape = Some(x)))
        .text("output shape C,H,W (inferred from dependency.csv if omitted)"),
      opt[String]("ref")
        .action((x, c) => c.copy(ref = Some(x)))
        .text("reference binary (default <sim-dir>/final_output.bin)"),
      opt[Unit]("detiled")
        .action((_, c) => c.copy(detiled = true))
        .text("treat input as already NCHW (skip detile step)")
    )
  }

  def main(args: Array[String]): Unit =
    OParser.parse(argParser, args, Opts()) match {
      case Some(o) =>
        val compDir = o.compDir
        val detiledFlag = o.detiled

        val cfg = ConfigParser.load(o.configJson.orNull)
        val blk = cfg.blockSize

        val (outC, outH, outW) = o.shape match {
          case Some(shapeStr) =>
            val parts = shapeStr.split(",")
            (parts(0).toInt, parts(1).toInt, parts(2).toInt)
          case None =>
            val dep = loadDependencyInfo(s"$compDir/dependency.csv")
            dep.layers.get(dep.outputLayer) match {
              case None =>
                System.err.println(
                  s"ERROR: output layer '${dep.outputLayer}' not in dependency.csv; pass --shape"
                )
                sys.exit(1)
              case Some(ld) => (ld.outCh, ld.outH, ld.outW)
            }
        }

        val refPath = o.ref.getOrElse(s"${o.simDir}/final_output.bin")
        val raw = os.read.bytes(os.Path(o.baremetalOut, os.pwd))
        val ref = os.read.bytes(os.Path(refPath, os.pwd))

        println(s"shape C,H,W = $outC,$outH,$outW  block=$blk")
        val layout = if (detiledFlag) "NCHW (pre-detiled)" else "block-tiled"
        println(
          s"baremetal raw: ${raw.length} B [$layout]   " +
            s"reference (NCHW): ${ref.length} B   ($refPath)\n"
        )

        val got = if (detiledFlag) raw else detile(raw, outC, outH, outW, blk)
        val label =
          if (detiledFlag) "NCHW vs NCHW ref" else "detiled vs NCHW ref"
        val ok = reportDiff(label, got, ref)
        val result =
          if (ok) "PASS - matches the functional simulator."
          else "FAIL - output diverges from the functional simulator."
        println("\nRESULT: " + result)
        sys.exit(if (ok) 0 else 1)
      case _ => sys.exit(1)
    }
}
