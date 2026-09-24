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

    val resolvedSuffixToIdx = t.suffixToIdx.getOrElse(layers.zipWithIndex.map {
      case (l, i) => l.suffix -> i
    }.toMap)
    val resolvedCpuOut = t.cpuOut.getOrElse {
      val (m, _, _) = MemoryLayout.buildCpuOutAddrs(
        dep,
        layers,
        ddrBase,
        resolvedSuffixToIdx,
        compDir,
        // ExecPlan carries no refDir of its own; every production caller
        // (GenNnBaremetal.generate) always passes an explicit cpuOut, so this
        // fallback path never resolves input_nn.bin itself - None is correct,
        // not a stopgap.
        None
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

    // Producers whose post-VTA rescale folds into their single downstream
    // im2row / int32-chain consumer (see ExecSteps.fusedRescaleProducers). The
    // consumer then reads the raw int32 OUT and requantizes inline, so no
    // standalone RescaleStep is emitted for these layers.
    val fusedProducers =
      ExecSteps.fusedRescaleProducers(
        dep,
        layers,
        resolvedSuffixToIdx,
        logOutWidth
      )
    def fusedScale(depName: String): (Double, Int) =
      if (fusedProducers.contains(depName))
        dep.layers
          .get(depName)
          .map(l => (l.scale, l.offsetC))
          .getOrElse((0.0, 0))
      else (0.0, 0)

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
          val (rs, ro) = fusedScale(depName)
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
            outW,
            rs,
            ro
          )
        }
      }).toMap

    // relayout pre/post for each VTA layer with reshape "direct". The layer
    // reads and writes the flat layout while everything around it uses the
    // block-tiled one, so it is bracketed: convert the producer's output into
    // this layer's INP, and convert this layer's OUT into a scratch buffer
    // that MemoryLayout.outAddr hands to consumers (a permutation cannot be
    // done in place).
    def chPad(c: Int): Int =
      (((c + blockSize - 1) / blockSize) * blockSize).toInt

    val relayoutIn: Map[String, RelayoutStep] =
      (for {
        (_, processor, layerName) <- dep.executionOrder
        if processor == "vta"
        ld <- dep.layers.get(layerName)
        if ld.reshapeInfo == "direct"
        lidx <- resolvedSuffixToIdx.get(layerName)
      } yield {
        val srcAddr = MemoryLayout.outAddr(
          ld.deps.headOption.getOrElse(""),
          dep,
          layers,
          ddrBase,
          resolvedSuffixToIdx,
          resolvedCpuOut
        )
        layerName -> RelayoutStep(
          layerName,
          srcAddr,
          ddrBase + layers(lidx).mem("INP").offset,
          ld.tensorH * ld.tensorW,
          chPad(ld.tensorCh),
          toFlat = true,
          ld.offsetA
        )
      }).toMap

    val relayoutOut: Map[String, RelayoutStep] =
      (for {
        (_, processor, layerName) <- dep.executionOrder
        if processor == "vta"
        ld <- dep.layers.get(layerName)
        if ld.reshapeInfo == "direct"
        lidx <- resolvedSuffixToIdx.get(layerName)
        scratch <- resolvedCpuOut.get(layerName)
      } yield layerName -> RelayoutStep(
        layerName,
        ddrBase + layers(lidx).mem("OUT").offset,
        scratch,
        ld.outH * ld.outW,
        chPad(ld.outCh),
        toFlat = false
      )).toMap

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
          val (rs, ro) = fusedScale(depName)
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
              ld.tensorW,
              rs,
              ro
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
          else if (processor == "vta" && relayoutIn.contains(layerName))
            Seq(relayoutIn(layerName))
          else if (processor == "vta" && int32Pre.contains(layerName))
            Seq(int32Pre(layerName))
          else Seq.empty

        val main: Seq[PlanStep] = if (processor == "vta") {
          val vtaIdx = resolvedSuffixToIdx.getOrElse(layerName, -1)
          if (vtaIdx < 0)
            println(s"WARNING: VTA layer '$layerName' not found in layers list")
          val vta = VtaStep(stepIdx, layerName, vtaIdx)
          val rescale: Seq[PlanStep] =
            if (
              logOutWidth > 3 && vtaIdx >= 0 && ldOpt.isDefined &&
              !fusedProducers.contains(layerName)
            ) {
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
          val post: Seq[PlanStep] =
            relayoutOut.get(layerName).toSeq
          (vta +: rescale) ++ post
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
          val n = roundUp((ld.outH * ld.outW).toLong) * roundUp(ld.outCh.toLong)
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
          // An im2row producer pads its final partial row-block; an int32 or
          // direct one stores it compactly, and a concat can mix both.
          val outElemBytes = HwConfig.elemBytes(logOutWidth)
          val densePerBranch = ld.tensorCh.toLong * ld.tensorH * ld.tensorW
          val paddedPerBranch =
            roundUp((ld.tensorH * ld.tensorW).toLong) * roundUp(ld.tensorCh.toLong)
          def branchIsPadded(dep_ : String): Boolean =
            resolvedSuffixToIdx.get(dep_) match {
              // A VTA producer: its OUT allocation says which convention it used.
              case Some(i) =>
                layers(i).mem("OUT").byteSize / outElemBytes >= paddedPerBranch
              // A CPU-op producer writes scratch sized by buildCpuOutAddrs,
              // which is padded.
              case None => true
            }
          val branchPad = ld.deps.take(ld.nbInp).map(branchIsPadded)
          val compactMask =
            branchPad.zipWithIndex.foldLeft(0) { case (m, (padded, i)) =>
              if (padded) m else m | (1 << i)
            }
          if (compactMask != 0 && paddedPerBranch != densePerBranch)
            println(
              s"[gen] concat '$layerName': " +
                s"${branchPad.count(!_)}/${branchPad.length} branch(es) store" +
                s" the final partial row-block compactly (H*W=" +
                s"${ld.tensorH * ld.tensorW} is not a multiple of $blockSize)" +
                s" - run_concat will read those with the compact stride"
            )
          val nRows = roundUp(ld.tensorH.toLong * ld.tensorW)
          val nRowsValid = ld.tensorH.toLong * ld.tensorW
          // n_ch_per_inp stays unpadded: branches are packed densely, and
          // run_concat gathers element-wise when a boundary falls mid-block.
          if (ld.tensorCh % blockSize != 0)
            println(
              s"[gen] concat '$layerName': ${ld.tensorCh} channels per branch" +
                s" is not a multiple of $blockSize - run_concat will use the" +
                s" element-wise gather path"
            )
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
              ld.offsetC,
              nRowsValid,
              compactMask
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
          val n =
            roundUp((ld.tensorH * ld.tensorW).toLong) * roundUp(ld.tensorCh.toLong)
          Seq(DequantStep(stepIdx, layerName, inp, n, ld.scaleA, ld.offsetA))
        } else if (processor == "quant" && ldOpt.isDefined) {
          val ld = ldOpt.get
          val out = resolvedCpuOut.getOrElse(layerName, 0L)
          // Block-tiled: both dims round up to the block.
          val n = roundUp((ld.outH * ld.outW).toLong) * roundUp(ld.outCh.toLong)
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
