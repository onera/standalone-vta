package fpga.host.transform

import fpga.host.models._

/** Lowers an [[ExecPlan]] (raw inputs) into the resolved [[PlanStep]] IR plus
  * the network-output address/size and the total step count. This is the whole
  * "Job A" that used to live inline in `HeaderRender.execPlan`: address
  * resolution, reshape/int32 pre-step derivation, and the per-processor
  * payload. Rendering then becomes a pure `PlanStep => String` pass.
  */
object ExecPlanResolver {

  final case class ResolvedPlan(
      outputAddr: Long,
      outputBytes: Long,
      numSteps: Int,
      steps: Seq[PlanStep]
  )

  def resolve(t: ExecPlan): ResolvedPlan = {
    val dep = t.dep
    val layers = t.layers
    val ddrBase = t.ddrBase
    val compDir = t.compDir
    val blockSize = t.blockSize
    val logOutWidth = t.logOutWidth

    val resolvedSuffixToIdx = t.suffixToIdx.getOrElse(
      layers.zipWithIndex.map { case (l, i) => l.suffix -> i }.toMap
    )
    val resolvedCpuOut = t.cpuOut.getOrElse {
      val (m, _, _) = MemoryLayout.buildCpuOutAddrs(
        dep,
        layers,
        ddrBase,
        resolvedSuffixToIdx,
        compDir
      )
      m
    }

    // Resolve the true final network output address.
    val outputName = dep.outputLayer
    val (nnOutputAddr, nnOutputBytes): (Long, Long) =
      resolvedSuffixToIdx.get(outputName) match {
        case Some(outIdx) =>
          val outRegion = layers(outIdx).mem("OUT")
          val addr = ddrBase + outRegion.offset
          val outSize = outRegion.byteSize
          val bytes =
            if (logOutWidth > 3) outSize / HwConfig.elemBytes(logOutWidth)
            else outSize
          (addr, bytes)
        case None =>
          val addr = resolvedCpuOut.getOrElse(outputName, 0L)
          val bytes = dep.layers
            .get(outputName)
            .map(ld => ld.outCh.toLong * ld.outH * ld.outW)
            .getOrElse(0L)
          (addr, bytes)
      }
    if (nnOutputAddr == 0L)
      println(
        s"WARNING: could not resolve NN_OUTPUT_ADDR for output layer '$outputName'"
      )

    // Round x up to the next multiple of blockSize.
    def roundUp(x: Long): Long = ((x + blockSize - 1) / blockSize) * blockSize

    val rawPhys = MemoryLayout.scratchAddr(layers, ddrBase)

    // format_input / im2row pre-step for each VTA layer with reshape "im2row".
    // Each qualifying layer maps to exactly one ReshapeStep.
    val reshapePre: Map[String, ReshapeStep] =
      (for {
        (_, processor, layerName) <- dep.executionOrder
        if processor == "vta"
        ld <- dep.layers.get(layerName).toSeq
        if ld.reshapeInfo == "im2row"
        idx <- resolvedSuffixToIdx.get(layerName).toSeq
      } yield {
        val outH = (ld.tensorH + ld.pad._1 + ld.pad._3 - ld.kh) / ld.sh + 1
        val outW = (ld.tensorW + ld.pad._2 + ld.pad._4 - ld.kw) / ld.sw + 1
        val inpAddr = ddrBase + layers(idx).mem("INP").offset
        if (ld.deps.headOption.contains("image")) {
          layerName -> ReshapeStep(
            layerName,
            ReshapeKind.FormatInput,
            rawPhys,
            inpAddr,
            ld.tensorCh,
            ld.tensorH,
            ld.tensorW,
            ld.kh,
            ld.kw,
            ld.sh,
            ld.sw,
            ld.pad,
            ld.offsetA,
            outH,
            outW
          )
        } else {
          val depName = ld.deps.headOption.getOrElse("")
          val src = MemoryLayout.outAddr(
            depName,
            dep,
            layers,
            ddrBase,
            resolvedSuffixToIdx,
            resolvedCpuOut
          )
          if (src == 0L)
            println(
              s"WARNING: im2row source address for '$layerName' dep '$depName' resolved to 0"
            )
          layerName -> ReshapeStep(
            layerName,
            ReshapeKind.Im2Row,
            src,
            inpAddr,
            ld.tensorCh,
            ld.tensorH,
            ld.tensorW,
            ld.kh,
            ld.kw,
            ld.sh,
            ld.sw,
            ld.pad,
            ld.offsetA,
            outH,
            outW
          )
        }
      }).toMap

    // int32_chain pre-step for each VTA layer with reshape "int32" (maxpool/ALU).
    val int32Pre: Map[String, Int32ChainStep] =
      (for {
        (_, processor, layerName) <- dep.executionOrder
        if processor == "vta"
        ld <- dep.layers.get(layerName).toSeq
        if ld.reshapeInfo == "int32"
        idx <- resolvedSuffixToIdx.get(layerName).toSeq
      } yield {
        val acc = layers(idx).mem("ACC")
        if (acc.byteSize == 0L) {
          println(
            s"WARNING: int32 layer '$layerName' has no ACC - chain skipped"
          )
          None
        } else {
          val depName = ld.deps.headOption.getOrElse("")
          val src = MemoryLayout.outAddr(
            depName,
            dep,
            layers,
            ddrBase,
            resolvedSuffixToIdx,
            resolvedCpuOut
          )
          if (src == 0L)
            println(
              s"WARNING: int32-chain source for '$layerName' dep '$depName' resolved to 0"
            )
          val outH = ld.tensorH + ld.pad._1 + ld.pad._3
          val outW = ld.tensorW + ld.pad._2 + ld.pad._4
          val nElemsBlocked =
            roundUp((outH * outW).toLong) * roundUp(ld.tensorCh.toLong)
          Some(
            layerName -> Int32ChainStep(
              layerName,
              src,
              ddrBase + acc.offset,
              nElemsBlocked,
              ld.offsetA,
              ld.pad,
              ld.tensorCh,
              ld.tensorH,
              ld.tensorW
            )
          )
        }
      }).flatten.toMap

    // NN_NUM_STEPS counts the emitted array entries (pre-steps + rescales
    // included) - the single source of truth shared with the CPU-debug map.
    val numSteps =
      ExecSteps.of(dep, layers, resolvedSuffixToIdx, logOutWidth).length

    val steps: Seq[PlanStep] =
      dep.executionOrder.flatMap { case (stepIdx, processor, layerName) =>
        val ldOpt = dep.layers.get(layerName)

        // Pre-step injected before a VTA layer that needs one.
        val pre: Seq[PlanStep] =
          if (processor == "vta" && reshapePre.contains(layerName))
            Seq(reshapePre(layerName))
          else if (processor == "vta" && int32Pre.contains(layerName))
            Seq(int32Pre(layerName))
          else Seq.empty

        val main: Seq[PlanStep] = if (processor == "vta") {
          val vtaIdx = resolvedSuffixToIdx.getOrElse(layerName, -1)
          if (vtaIdx < 0)
            println(s"WARNING: VTA layer '$layerName' not found in layers list")
          val vta = VtaStep(stepIdx, layerName, vtaIdx)
          val rescale: Seq[PlanStep] =
            if (logOutWidth > 3 && vtaIdx >= 0 && ldOpt.isDefined) {
              val ld = ldOpt.get
              val outBytes = layers(vtaIdx).mem("OUT").byteSize
              val nElems = outBytes / HwConfig.elemBytes(logOutWidth)
              val outAddr = ddrBase + layers(vtaIdx).mem("OUT").offset
              Seq(
                RescaleStep(
                  stepIdx,
                  layerName,
                  outAddr,
                  nElems,
                  ld.scale,
                  ld.offsetC
                )
              )
            } else Seq.empty
          vta +: rescale
        } else if (processor == "qadd" && ldOpt.isDefined) {
          val ld = ldOpt.get
          val inpA = MemoryLayout.outAddr(
            if (ld.deps.nonEmpty) ld.deps(0) else "",
            dep,
            layers,
            ddrBase,
            resolvedSuffixToIdx,
            resolvedCpuOut
          )
          val inpB = MemoryLayout.outAddr(
            if (ld.deps.length > 1) ld.deps(1) else "",
            dep,
            layers,
            ddrBase,
            resolvedSuffixToIdx,
            resolvedCpuOut
          )
          val out = resolvedCpuOut.getOrElse(layerName, 0L)
          val n = ld.outCh.toLong * ld.outH * ld.outW
          Seq(
            QaddStep(
              stepIdx,
              layerName,
              inpA,
              inpB,
              out,
              n,
              ld.scaleA,
              ld.scaleB,
              ld.scaleC,
              ld.offsetA,
              ld.offsetB,
              ld.offsetC
            )
          )
        } else if (processor == "concat" && ldOpt.isDefined) {
          val ld = ldOpt.get
          val inpAddrs = (0 until 4).map { j =>
            MemoryLayout.outAddr(
              if (j < ld.deps.length) ld.deps(j) else "",
              dep,
              layers,
              ddrBase,
              resolvedSuffixToIdx,
              resolvedCpuOut
            )
          }
          val out = resolvedCpuOut.getOrElse(layerName, 0L)
          val nRows = ld.tensorH.toLong * ld.tensorW
          Seq(
            ConcatStep(
              stepIdx,
              layerName,
              inpAddrs,
              out,
              nRows,
              ld.tensorCh,
              ld.nbInp,
              ld.scaleA,
              ld.scaleB,
              ld.scaleU,
              ld.scaleV,
              ld.offsetA,
              ld.offsetB,
              ld.offsetU,
              ld.offsetV,
              ld.scaleC,
              ld.offsetC
            )
          )
        } else if (processor == "dequant" && ldOpt.isDefined) {
          val ld = ldOpt.get
          val inp = MemoryLayout.outAddr(
            if (ld.deps.nonEmpty) ld.deps(0) else "",
            dep,
            layers,
            ddrBase,
            resolvedSuffixToIdx,
            resolvedCpuOut
          )
          val n = ld.tensorCh.toLong * ld.tensorH * ld.tensorW
          Seq(DequantStep(stepIdx, layerName, inp, n, ld.scaleA, ld.offsetA))
        } else if (processor == "quant" && ldOpt.isDefined) {
          val ld = ldOpt.get
          val out = resolvedCpuOut.getOrElse(layerName, 0L)
          val n = ld.outCh.toLong * ld.outH * ld.outW
          Seq(QuantStep(stepIdx, layerName, out, n, ld.scaleA, ld.offsetA))
        } else if (processor == "convtranspose" && ldOpt.isDefined) {
          val ld = ldOpt.get
          t.ctParams.flatMap(_.get(layerName)) match {
            case None =>
              println(
                s"WARNING: convtranspose '$layerName' has no param allocation - emitting VTA stub"
              )
              Seq(ConvTransposeStubStep(stepIdx, layerName))
            case Some(p) =>
              val nOut =
                roundUp((ld.outH * ld.outW).toLong) * roundUp(ld.outCh.toLong)
              Seq(
                ConvTransposeStep(
                  stepIdx,
                  layerName,
                  p.wgtAddr,
                  p.biasAddr,
                  p.hasBias,
                  ld.tensorCh,
                  ld.tensorH,
                  ld.tensorW,
                  ld.outCh,
                  ld.outH,
                  ld.outW,
                  ld.kh,
                  ld.kw,
                  ld.sh,
                  ld.pad,
                  nOut
                )
              )
          }
        } else {
          println(
            s"WARNING: unsupported processor '$processor' for '$layerName' - emitting VTA stub"
          )
          Seq(UnsupportedStep(stepIdx, layerName, processor))
        }

        pre ++ main
      }

    ResolvedPlan(nnOutputAddr, nnOutputBytes, numSteps, steps)
  }
}
