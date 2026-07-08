package fpga.host.transform

import vta.parsers.CompilerOutputParser
import vta.models.CompilerOutputModel.DependencyInfo
import fpga.host.models._

/** DDR address allocation and resolution for VTA/CPU buffers. Translated from
  * nnbaremetal/layout.py.
  */
object MemoryLayout {

  private val PAGE = 0x1000L

  /** Return the first page-aligned DDR address after all VTA allocations. */
  def scratchAddr(layers: Seq[Model.LayerInfo], ddrBase: Long): Long =
    CompilerOutputParser.alignPage(
      layers
        .flatMap(_.mem.values)
        .map(r => ddrBase + r.offset + r.byteSize)
        .foldLeft(ddrBase)(math.max)
    )

  /** DDR address where layerName wrote its output.
    *
    * Checks VTA OUT buffers first, then the pre-resolved cpuOut map (which
    * covers CPU ops that write to VTA INP/ACC or to CPU scratch).
    */
  def outAddr(
      layerName: String,
      dep: DependencyInfo,
      layers: Seq[Model.LayerInfo],
      ddrBase: Long,
      suffixToIdx: Map[String, Int],
      cpuOut: Map[String, Long]
  ): Long = {
    suffixToIdx.get(layerName) match {
      case Some(idx) => ddrBase + layers(idx).mem("OUT").offset
      case None      => cpuOut.getOrElse(layerName, 0L)
    }
  }

  /** Pre-resolve every CPU op's output DDR address.
    *
    * For ops that write into a VTA layer's INP/ACC the VTA address is used
    * (shared buffer, no extra allocation). For ops whose output feeds only
    * other CPU ops a fresh page-aligned scratch region is allocated above the
    * VTA + raw-input footprint.
    *
    * dequant is excluded: its output is a CPU-allocated float* not in DDR.
    *
    * Returns (cpuOut, allocTop, cpuScratch) where allocTop is the first free
    * page-aligned address above all VTA buffers, the raw-input scratch, and
    * CPU-op scratch; cpuScratch is the list of (label, addr, nBytes) regions
    * freshly allocated here (not aliasing a VTA buffer).
    */
  def buildCpuOutAddrs(
      dep: DependencyInfo,
      layers: Seq[Model.LayerInfo],
      ddrBase: Long,
      suffixToIdx: Map[String, Int],
      compDir: String
  ): (Map[String, Long], Long, Seq[(String, Long, Long)]) = {
    val rawPhys = scratchAddr(layers, ddrBase)
    val inputNnPath = os.Path(s"$compDir/input_nn.bin", os.pwd)
    val rawSize = if (os.exists(inputNnPath)) os.size(inputNnPath) else 0L
    val initAlloc =
      rawPhys + math.max(CompilerOutputParser.alignPage(rawSize), PAGE)

    val (cpuOut, allocPtr, cpuScratch) =
      dep.executionOrder.foldLeft(
        (Map.empty[String, Long], initAlloc, Vector.empty[(String, Long, Long)])
      ) { case ((cpuOut, allocPtr, cpuScratch), (_, processor, layerName)) =>
        // dequant/convtranspose produce a CPU-allocated float* (the run_nn
        // float_buf), not a DDR buffer, so they need no DDR output address.
        if (Set("vta", "dequant", "convtranspose").contains(processor)) {
          (cpuOut, allocPtr, cpuScratch)
        } else {
          dep.layers.get(layerName) match {
            case Some(ld)
                if Set("qadd", "concat", "quant").contains(processor) =>
              // A CPU op's compact int8 output is never written straight into a
              // downstream VTA buffer (INP needs im2row, ACC is wider int32), so
              // it always gets its own scratch DDR region.  quant included so a
              // requantizing quant (e.g. after a convtranspose) or a terminal quant
              // writes its int8 output to a real, readable address rather than 0.
              // Its output is consumed either by a downstream VTA layer (via im2row
              // from this scratch) or read back as the network output.
              val nBytes = ld.outCh.toLong * ld.outH * ld.outW
              println(
                s"[gen] CPU scratch alloc: $layerName -> " +
                  s"${Model.hex32(allocPtr)} ($nBytes bytes)"
              )
              (
                cpuOut + (layerName -> allocPtr),
                allocPtr + CompilerOutputParser.alignPage(nBytes),
                cpuScratch :+ ((layerName, allocPtr, nBytes))
              )
            case _ =>
              (cpuOut, allocPtr, cpuScratch)
          }
        }
      }

    // allocPtr is the first free page-aligned address above all VTA buffers,
    // the raw-input scratch, and any CPU-op scratch - the safe base for the
    // isolation-check golden regions.
    (cpuOut, allocPtr, cpuScratch.toSeq)
  }

  /** Allocate DDR for CPU-op parameter blobs (currently the float weights and
    * bias of each convtranspose op).
    *
    * Unlike the inter-layer activation scratch handled by buildCpuOutAddrs,
    * these are read-only model parameters: they are loaded into DRAM by the
    * same static-load path as the VTA INSN/UOP/WGT/ACC buffers (ELF .incbin +
    * Tcl dow) and read by the CPU op at run time. The PL never touches them.
    *
    * Returns (ctParams, blobs, allocTop): ctParams: layerName ->
    * CtParams(wgtAddr, biasAddr, hasBias) blobs: list of [[ExtraBlob]] for the
    * loaders (emit_load) and the overlap/fit checks allocTop: first free
    * page-aligned address above these blobs
    */
  def buildCpuParamAddrs(
      dep: DependencyInfo,
      compDir: String,
      allocBase: Long
  ): (Map[String, CtParams], Seq[ExtraBlob], Long) = {

    case class Acc(
        alloc: Long,
        ctParams: Map[String, CtParams],
        blobs: Vector[ExtraBlob],
        ctIdx: Int
    )

    val result = dep.executionOrder.foldLeft(
      Acc(CompilerOutputParser.alignPage(allocBase), Map.empty, Vector.empty, 0)
    ) { case (acc, (_, processor, name)) =>
      if (processor != "convtranspose") acc
      else {
        // node_cpu writes flat float32 "weight{suffix}.bin" / "accumulator{suffix}.bin"
        // (no _block sibling - consumed directly as flat float by run_convtranspose).
        val wpath = s"$compDir/weight$name.bin"
        val bpath = s"$compDir/accumulator$name.bin"
        val wsize = Model.fileSizeOr0(wpath)
        val bsize = Model.fileSizeOr0(bpath)
        if (wsize == 0L)
          println(s"WARNING: convtranspose '$name' weight bin missing: $wpath")
        val safe = Model.safeCName(name, acc.ctIdx)
        val wgtAddr = acc.alloc
        val alloc1 =
          acc.alloc + math.max(CompilerOutputParser.alignPage(wsize), PAGE)
        val blob1 =
          ExtraBlob(
            s".ct_${safe}_wgt",
            os.Path(wpath, os.pwd).toString,
            wgtAddr,
            wsize
          )

        val hasBias = bsize > 0L
        val (biasAddr, alloc2, extraBlob) =
          if (hasBias) {
            val ba = alloc1
            val blob2 =
              ExtraBlob(
                s".ct_${safe}_bias",
                os.Path(bpath, os.pwd).toString,
                ba,
                bsize
              )
            (
              ba,
              alloc1 + math.max(CompilerOutputParser.alignPage(bsize), PAGE),
              Some(blob2)
            )
          } else {
            (0L, alloc1, None)
          }

        val biasStr =
          if (hasBias) s", bias ${Model.hex32(biasAddr)} (${bsize} B)" else ""
        println(
          s"[gen] convtranspose param alloc: $name wgt ${Model.hex32(wgtAddr)}" +
            s" (${wsize} B)$biasStr"
        )

        val newBlobs = extraBlob match {
          case Some(b2) => acc.blobs :+ blob1 :+ b2
          case None     => acc.blobs :+ blob1
        }
        Acc(
          alloc = alloc2,
          ctParams =
            acc.ctParams + (name -> CtParams(wgtAddr, biasAddr, hasBias)),
          blobs = newBlobs,
          ctIdx = acc.ctIdx + 1
        )
      }
    }

    (result.ctParams, result.blobs.toSeq, result.alloc)
  }

  /** Lay out the golden in/out bins in a reserved DRAM region.
    *
    * Regions start at baseTop (the first free address above all VTA buffers,
    * raw-input scratch, and CPU-op scratch) and grow page-aligned upward, so
    * they never collide with live data. Returns the updated layer sequence
    * (each with `check = Some(LayerCheck(...))` filled in) and the new free-top
    * address. The golden input destination is the layer's INP buffer for im2row
    * layers and its ACC buffer for int32 layers (matching fsim's dump).
    */
  def assignLayerCheckRegions(
      layers: Seq[Model.LayerInfo],
      depInfo: DependencyInfo,
      ddrBase: Long,
      refDir: String,
      baseTop: Long
  ): (Seq[Model.LayerInfo], Long) = {
    // Thread the page-aligned allocation pointer through the layers with a fold
    // (was a `var` mutated inside `map`). Per layer the golden OUT region is
    // allocated before the golden IN region, matching the old order.
    val (updatedRev, finalPtr) =
      layers.foldLeft(
        (List.empty[Model.LayerInfo], CompilerOutputParser.alignPage(baseTop))
      ) { case ((acc, allocPtr), layer) =>
        val suffix = layer.suffix
        val ld = depInfo.layers.get(suffix)
        val reshape = ld.map(_.reshapeInfo).getOrElse("im2row")

        val dstBuf =
          if (reshape == "im2row") layer.mem("INP")
          else layer.mem("ACC")
        val inDstAddr = ddrBase + dstBuf.offset
        if (reshape != "im2row" && dstBuf.byteSize == 0)
          println(
            s"WARNING: int32 layer '$suffix' has no ACC region" +
              s" - golden input has nowhere to land"
          )

        // Golden output (raw OUT, pre-rescale) - compared against board OUT.
        val outFile = Model.refOutputPath(refDir, suffix)
        val (outRefFile, outRefAddr, outRefSize, ptrAfterOut) =
          if (Model.isFile(outFile)) {
            val size = os.size(os.Path(outFile, os.pwd))
            if (size > layer.mem("OUT").byteSize)
              println(
                s"WARNING: $outFile ($size B) larger than OUT buffer" +
                  s" (${layer.mem("OUT").byteSize} B) for layer '$suffix'"
              )
            (
              outFile,
              allocPtr,
              size,
              allocPtr + CompilerOutputParser.alignPage(
                size
              )
            )
          } else {
            println(
              s"WARNING: golden output not found: $outFile" +
                s" - layer '$suffix' output will not be checked"
            )
            ("", 0L, 0L, allocPtr)
          }

        // Golden input - copied into inDstAddr before the layer runs.
        val inFile = Model.refInputPath(refDir, suffix)
        val (inRefFile, inRefAddr, inRefSize, ptrAfterIn) =
          if (Model.isFile(inFile)) {
            val size = os.size(os.Path(inFile, os.pwd))
            if (size > dstBuf.byteSize)
              println(
                s"WARNING: $inFile ($size B) larger than destination" +
                  s" buffer (${dstBuf.byteSize} B) for layer '$suffix'"
              )
            (
              inFile,
              ptrAfterOut,
              size,
              ptrAfterOut + CompilerOutputParser
                .alignPage(size)
            )
          } else {
            println(
              s"WARNING: golden input not found: $inFile" +
                s" - layer '$suffix' will run on its preloaded buffer"
            )
            ("", 0L, 0L, ptrAfterOut)
          }

        // Dual-operand isolation is not wired up (no such VTA layer in current
        // nets; nbInp==2 int32 is the CPU qadd path).
        val yFile = Model.refInputYPath(refDir, suffix)
        if (Model.isFile(yFile))
          println(
            s"WARNING: $yFile exists but dual-operand (accY) isolation is" +
              s" not implemented - layer '$suffix' second input is ignored"
          )

        val updatedLayer = layer.copy(check =
          Some(
            LayerCheck(
              inRefFile = inRefFile,
              inRefAddr = inRefAddr,
              inRefSize = inRefSize,
              inDstAddr = inDstAddr,
              outRefFile = outRefFile,
              outRefAddr = outRefAddr,
              outRefSize = outRefSize
            )
          )
        )
        (updatedLayer :: acc, ptrAfterIn)
      }

    (updatedRev.reverse, finalPtr)
  }
}
