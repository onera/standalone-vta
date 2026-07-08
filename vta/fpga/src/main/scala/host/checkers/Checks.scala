package fpga.host.checkers

import vta.models.DataType
import fpga.host.models._
import fpga.host.transform.MemoryLayout
import vta.models.CompilerOutputModel.DependencyInfo
import vta.models.CompilerOutputModel.alignPage

/** DDR layout guard checks (overlap, fit) and the DRAM summary. Translated from
  * nnbaremetal/checks.py.
  *
  * Each check returns true when clean and prints a one-line reason per
  * violation otherwise. [[GenNnBaremetal]] calls them as a pre-emit guard.
  */
object Checks {

  /** Check that the hardware config is compatible with the compiled network.
    * Prints warnings and error messages, returning false on error instead of
    * calling sys.exit - the caller decides what to do on failure.
    */
  def checkConfigCompat(
    cfg: HwConfig.ConfigParams,
    dep: DependencyInfo
  ): Boolean = {
    if (cfg.logInpWidth == 3 || cfg.logOutWidth == 3) {
      println(
        s"WARNING: 8-bit data width detected" +
          s" (LOG_INP_WIDTH=${cfg.logInpWidth}, LOG_OUT_WIDTH=${cfg.logOutWidth})." +
          s" CPU ops will use int8_t." +
          s" Ensure compiler output and network quantization are 8-bit."
      )
    }

    val requantLayers = dep.executionOrder.collect {
      case (_, "vta", name)
          if dep.layers
            .get(name)
            .exists(ld => math.abs(ld.scale - 1.0) > 1e-9 || ld.offsetC != 0) =>
        name
    }

    val outAccError =
      cfg.logOutWidth < cfg.logAccWidth && requantLayers.nonEmpty
    if (outAccError) {
      System.err.println(
        s"ERROR: LOG_OUT_WIDTH=${cfg.logOutWidth} < LOG_ACC_WIDTH=" +
          s"${cfg.logAccWidth} but ${requantLayers.size} layer(s) need CPU" +
          s" requantization (e.g. '${requantLayers.head}'). This stack truncates" +
          s" the int32 accumulator to the OUT width in the store (no shift) and" +
          s" rescales on the CPU, so QLinear requant needs OUT as wide as ACC" +
          s" (int32). Use a config with LOG_OUT_WIDTH=LOG_ACC_WIDTH, or add" +
          s" store-side requantization."
      )
    }

    // Side-effecting warnings/errors per layer (in execution order); collect the
    // concat-arity offenders so `ok` is derived rather than mutated.
    val concatErrors = dep.executionOrder.flatMap {
      case (_, processor, layerName) =>
        dep.layers.get(layerName).toList.flatMap { ld =>
          if (
            processor == "vta" && ld.reshapeInfo == "im2row" && ld.sh != ld.sw
          ) {
            println(
              s"WARNING: layer '$layerName' uses asymmetric strides" +
                s" (sh=${ld.sh}, sw=${ld.sw})." +
                s" The functional simulator im2row() only supports isotropic stride;" +
                s" simulation results will differ from FPGA execution."
            )
          }
          if (processor == "concat" && ld.nbInp > 4) {
            System.err.println(
              s"ERROR: concat layer '$layerName' has ${ld.nbInp} inputs;" +
                s" NnConcatStep supports at most 4."
            )
            Some(layerName)
          } else None
        }
    }

    !outAccError && concatErrors.isEmpty
  }

  /** Every non-empty DDR region as (start, end, label): VTA buffers, CPU
    * scratch, and (if populated) isolation-check golden regions.
    */
  private def liveRegions(
    layers: Seq[Model.LayerInfo],
    ddrBase: Long,
    cpuScratch: Seq[(String, Long, Long)] = Nil
  ): Seq[(Long, Long, String)] = {
    val scratchRegions = cpuScratch.collect {
      case (label, addr, size) if size > 0 =>
        (addr, addr + size, s"cpu-scratch $label")
    }
    val layerRegions = layers.zipWithIndex.flatMap { case (layer, i) =>
      val vtaBufs = DataType.names.collect {
        case bt if layer.mem(bt).byteSize != 0 =>
          val m = layer.mem(bt)
          val start = ddrBase + m.offset
          (start, start + m.byteSize, s"L$i ${layer.suffix} $bt")
      }
      val refRegions = Model
        .refEntries(layer, i)
        .filter(_.size > 0)
        .map(e =>
          (
            e.addr,
            e.addr + e.size,
            s"L$i ${layer.suffix} ${if (e.isInput) "INREF" else "OUTREF"}"
          )
        )
      vtaBufs ++ refRegions
    }
    scratchRegions ++ layerRegions
  }

  /** No two live DDR regions may overlap. */
  def checkBufferOverlaps(
    layers: Seq[Model.LayerInfo],
    ddrBase: Long,
    cpuScratch: Seq[(String, Long, Long)] = Nil
  ): Boolean = {
    val regions = liveRegions(layers, ddrBase, cpuScratch)
    val conflicts = for {
      j <- regions.indices
      k <- (j + 1) until regions.length
      (s1, e1, l1) = regions(j)
      (s2, e2, l2) = regions(k)
      if s1 < e2 && s2 < e1
    } yield f"  $l1 [0x$s1%08X-0x$e1%08X) overlaps $l2 [0x$s2%08X-0x$e2%08X)"
    if (conflicts.nonEmpty) {
      println(s"[overlap] FAIL - ${conflicts.size} overlap(s):")
      conflicts.foreach(println)
      false
    } else {
      println(s"[overlap] OK (${regions.size} regions)")
      true
    }
  }

  /** Each static binary (INSN/UOP/WGT/ACC) must fit its allocated slot. */
  def checkBinaryFits(
    layers: Seq[Model.LayerInfo],
    compDir: String
  ): Boolean = {
    val (bad, checked) = Model
      .iterStaticBuffers(layers)
      .foldLeft((Vector.empty[String], 0)) {
        case ((bad, checked), (i, layer, bt, m)) =>
          val p = os.Path(layer.binFiles(bt), os.pwd)
          if (os.exists(p)) {
            val size = os.size(p)
            if (size > m.byteSize)
              (
                bad :+ s"  L$i ${layer.suffix} $bt: file $size B > slot ${m.byteSize} B",
                checked + 1
              )
            else
              (bad, checked + 1)
          } else {
            (bad, checked)
          }
      }
    if (bad.nonEmpty) {
      println(s"[binfit] FAIL - ${bad.size} overflow(s):")
      bad.foreach(println)
      false
    } else {
      println(s"[binfit] OK ($checked files)")
      true
    }
  }

  /** CPU-side outputs must fit the VTA region they feed.
    *
    * im2row writes vta_inp_t elements into INP (byte size scales with
    * inpElemBytes); qadd/concat/quant write compact int8 into the next VTA
    * consumer's INP/ACC.
    */
  def checkCpuOutputFits(
    dep: DependencyInfo,
    layers: Seq[Model.LayerInfo],
    ddrBase: Long,
    suffixToIdx: Map[String, Int],
    cpuOut: Map[String, Long],
    blockSize: Int,
    inpElemBytes: Int = 1
  ): Boolean = {
    val bad = dep.executionOrder.zipWithIndex.flatMap {
      case ((_, processor, name), k) =>
        dep.layers.get(name).toSeq.flatMap { ld =>
          if (processor == "vta") {
            if (
              ld.reshapeInfo == "im2row" && ld.deps.headOption.contains("image")
            ) {
              val idx = suffixToIdx.getOrElse(name, -1)
              if (idx >= 0) {
                val outH =
                  (ld.tensorH + ld.pad._1 + ld.pad._3 - ld.kh) / ld.sh + 1
                val outW =
                  (ld.tensorW + ld.pad._2 + ld.pad._4 - ld.kw) / ld.sw + 1
                val tiled =
                  math
                    .ceil(ld.kh.toDouble * ld.kw * ld.tensorCh / blockSize)
                    .toLong * blockSize
                val need = outH.toLong * outW * tiled * inpElemBytes
                val have = layers(idx).mem("INP").byteSize
                if (need > have) Seq(s"  im2row $name: $need B > INP $have B")
                else Nil
              } else Nil
            } else Nil
          } else if (Set("qadd", "concat", "quant").contains(processor)) {
            // Find the first downstream VTA consumer of this layer.
            // Break at the first VTA entry that lists `name` in its deps
            // (Python: `break` is unconditional once a dep-match is found).
            val consumer = dep.executionOrder.iterator
              .drop(k + 1)
              .collectFirst {
                case (_, "vta", cname)
                    if dep.layers.get(cname).exists(_.deps.contains(name)) =>
                  suffixToIdx.get(cname).flatMap { idx =>
                    dep.layers.get(cname).map { vld =>
                      val buf =
                        if (vld.reshapeInfo == "im2row") "INP" else "ACC"
                      (idx, buf)
                    }
                  }
              }
              .flatten
            consumer.toSeq.flatMap { case (idx, buf) =>
              val need = ld.outCh.toLong * ld.outH * ld.outW
              val have = layers(idx).mem(buf).byteSize
              if (need > have)
                Seq(s"  $processor $name: $need B > $buf $have B")
              else Nil
            }
          } else Nil
        }
    }

    if (bad.nonEmpty) {
      println(s"[cpufit] FAIL - ${bad.size} overflow(s):")
      bad.foreach(println)
      false
    } else {
      println("[cpufit] OK")
      true
    }
  }

  /** Every allocation (page-aligned) plus the input_nn scratch must end below
    * maxAddr.
    */
  def checkMemoryFit(
    layers: Seq[Model.LayerInfo],
    ddrBase: Long,
    maxAddr: Long,
    compDir: String,
    cpuScratch: Seq[(String, Long, Long)] = Nil
  ): Boolean = {
    val baseRegions = liveRegions(layers, ddrBase, cpuScratch)
    val rawPhys = MemoryLayout.scratchAddr(layers, ddrBase)
    val sz = Model.fileSizeOr0(s"$compDir/input_nn.bin")
    val allRegions =
      if (sz > 0) baseRegions :+ ((rawPhys, rawPhys + sz, "input_nn scratch"))
      else baseRegions

    val alignedRegions = allRegions.map { case (start, end0, label) =>
      (start, start + alignPage(end0 - start), label)
    }
    val high = alignedRegions.map(_._2).foldLeft(ddrBase)(math.max)
    val bad = alignedRegions.collect {
      case (_, end, label) if end > maxAddr =>
        f"  $label: end 0x$end%08X > max 0x$maxAddr%08X"
    }

    println(
      f"[memfit] base 0x$ddrBase%08X  high 0x$high%08X  max 0x$maxAddr%08X"
    )
    if (bad.nonEmpty) {
      println(s"[memfit] FAIL - ${bad.size} overflow(s):")
      bad.foreach(println)
      false
    } else {
      println(s"[memfit] OK (${maxAddr - high} B free)")
      true
    }
  }

  /** Run every layout guard (each prints its own reasons); returns true iff all
    * pass. A Seq is strict so all guards run before the verdict is folded.
    */
  def runGuards(
    dep: DependencyInfo,
    layers: Seq[Model.LayerInfo],
    ddrBase: Long,
    suffixToIdx: Map[String, Int],
    cpuOut: Map[String, Long],
    blockSize: Int,
    inpElemBytes: Int,
    cpuScratch: Seq[(String, Long, Long)],
    compDir: String,
    maxAddr: Option[Long]
  ): Boolean = (
    Seq(
      checkBufferOverlaps(layers, ddrBase, cpuScratch),
      checkBinaryFits(layers, compDir),
      checkCpuOutputFits(
        dep,
        layers,
        ddrBase,
        suffixToIdx,
        cpuOut,
        blockSize,
        inpElemBytes
      )
    ) ++ maxAddr.toSeq.map(ma =>
      checkMemoryFit(layers, ddrBase, ma, compDir, cpuScratch)
    )
  ).forall(identity)

  /** Compact DRAM map (* = runtime buffer, not pre-loaded). */
  def printSummary(layers: Seq[Model.LayerInfo], ddrBase: Long): Unit = {
    println(s"\nDRAM map (base ${Model.hex32(ddrBase)}):")
    for ((layer, i) <- layers.zipWithIndex) {
      for (bt <- DataType.names) {
        val m = layer.mem(bt)
        val tag = if (Set("INP", "OUT").contains(bt)) "*" else " "
        println(f"  L$i%-2d $bt%-4s ${Model.hex32(ddrBase + m.offset)} ${Model
            .hex32(m.byteSize)}%10s $tag")
      }
    }
  }
}
