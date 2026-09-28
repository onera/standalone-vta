package fpga.host.transform

import vta.models.CompilerOutputModel.DependencyInfo
import fpga.host.models._

object ExecSteps {

  /** Whether [[cpuOutRetargets]] is on, from `-Dvta.alias.cpu.out`. A system
    * property, so every layout and plan call site sees the same value.
    */
  private lazy val enabled: Boolean =
    System.getProperty("vta.alias.cpu.out", "false").toLowerCase == "true"

  /** CPU op -> the VTA layer whose INP buffer it writes into directly, instead
    * of writing its own scratch region for that layer to then copy out of.
    *
    * A consumer qualifies on the same terms as the 1x1 INP alias, and its INP
    * buffer must be exactly the size of the producer's output, since the CPU
    * op writes nothing else. Only the first eligible consumer of a producer is
    * retargeted; the others read that consumer's INP through their im2row.
    */
  def cpuOutRetargets(
    dep: DependencyInfo,
    layers: Seq[Model.LayerInfo],
    suffixToIdx: Map[String, Int]
  ): Map[String, String] = {
    if (!enabled) return Map.empty

    val procOf =
      dep.executionOrder.map { case (_, p, n) => n -> p }.toMap

    val consumersOf: Map[String, Seq[String]] = {
      val pairs = for {
        (_, _, consumer) <- dep.executionOrder
        cld <- dep.layers.get(consumer).toSeq
        d <- cld.deps
      } yield d -> consumer
      pairs.groupBy(_._1).view.mapValues(_.map(_._2)).toMap
    }

    def eligible(consumer: String, outBytes: Long): Boolean =
      procOf.get(consumer).contains("vta") &&
        !dep.aliases.contains(consumer) &&
        dep.layers.get(consumer).exists { c =>
          c.reshapeInfo == "im2row" && c.nbInp == 1 &&
          c.kh == 1 && c.kw == 1 && c.sh == 1 && c.sw == 1 &&
          c.pad == (0, 0, 0, 0) && c.offsetA == 0
        } &&
        // The CPU op writes int8, so this size match is also what keeps the
        // alias off a wider INP (LOG_INP_WIDTH > 3): there the INP buffer is
        // several bytes per element and can never equal outBytes.
        suffixToIdx
          .get(consumer)
          .exists(i => layers(i).mem("INP").byteSize == outBytes)

    (for {
      (_, proc, producer) <- dep.executionOrder
      if proc == "qadd" || proc == "concat"
      if producer != dep.outputLayer
      pld <- dep.layers.get(producer).toSeq
      outBytes = pld.outCh.toLong * pld.outH * pld.outW
      consumer <- consumersOf
        .getOrElse(producer, Nil)
        .find(c => eligible(c, outBytes))
    } yield producer -> consumer).toMap
  }

  /** VTA producer layers whose post-VTA rescale is folded into their single
    * downstream im2row / int32-chain consumer (which then reads the raw int32
    * OUT and requantizes inline). A producer qualifies when OUT is wider than
    * int8 (`logOutWidth > 3`), it feeds exactly one step, and that step is a
    * non-image im2row or an int32 chain with an allocated ACC. Multi-consumer
    * producers keep the standalone rescale.
    *
    * Shared by [[of]] (step ordering / count) and
    * [[fpga.host.transform.ExecPlanResolver]] (which also reads the scale).
    */
  def fusedRescaleProducers(
    dep: DependencyInfo,
    layers: Seq[Model.LayerInfo],
    suffixToIdx: Map[String, Int],
    logOutWidth: Int
  ): Set[String] = {
    if (logOutWidth <= 3) return Set.empty

    val consumersOf: Map[String, Seq[String]] = {
      val pairs = for {
        (_, _, consumer) <- dep.executionOrder
        cld <- dep.layers.get(consumer).toSeq
        d <- cld.deps
      } yield d -> consumer
      pairs.groupBy(_._1).view.mapValues(_.map(_._2)).toMap
    }

    // An aliased consumer has no im2row to carry the rescale, so its producer
    // keeps a standalone rescale and OUT holds int8.
    def isReshapeConsumer(name: String): Boolean =
      !dep.aliases.contains(name) &&
      dep.layers.get(name).exists { c =>
        c.processor == "vta" && (
          (c.reshapeInfo == "im2row" && !c.deps.headOption.contains("image")) ||
            (c.reshapeInfo == "int32" &&
              suffixToIdx
                .get(name)
                .exists(i => layers(i).mem("ACC").byteSize != 0L))
        )
      }

    // A direct convolution is never a fusion candidate. Fusing its rescale
    // into the consumer would leave its OUT as raw int32, but the relayout
    // that follows it moves int8 - it would convert the layout of the wrong
    // element width, silently.
    def isDirect(name: String): Boolean =
      dep.layers.get(name).exists(_.reshapeInfo == "direct")

    dep.executionOrder.iterator.collect {
      case (_, "vta", pName)
          if !isDirect(pName) && consumersOf.get(pName).exists(cs =>
            cs.size == 1 && isReshapeConsumer(cs.head)
          ) =>
        pName
    }.toSet
  }

  /** Violations of the conditions under which an applied alias may drop its
    * layer's im2row; empty when the plan is sound.
    */
  def aliasViolations(
    dep: DependencyInfo,
    fused: Set[String]
  ): Seq[String] =
    dep.aliases.toSeq.sorted.flatMap { case (consumer, producer) =>
      val cOpt = dep.layers.get(consumer)
      val pOpt = dep.layers.get(producer)
      Seq(
        Option.when(cOpt.isEmpty)(
          s"aliased layer '$consumer' is not in dependency.csv"
        ),
        Option.when(pOpt.isEmpty)(
          s"'$consumer' is aliased to '$producer', which is not in dependency.csv"
        ),
        // Only an im2row reads what the producer's OUT holds.
        cOpt.filterNot(_.reshapeInfo == "im2row").map(c =>
          s"'$consumer' is aliased but its reshape is '${c.reshapeInfo}'," +
            s" not im2row"
        ),
        // The aliased producer must be the one the im2row would read.
        cOpt.filterNot(_.deps == Seq(producer)).map(c =>
          s"'$consumer' is aliased to '$producer' but its inputs are" +
            s" ${c.deps.mkString("[", ", ", "]")}"
        ),
        // With a run-time zero point the im2row is not a copy.
        cOpt.filter(_.offsetA != 0).map(c =>
          s"'$consumer' is aliased but carries offsetA=${c.offsetA};" +
            s" its im2row is not a plain copy"
        ),
        // A rescale fused into the dropped im2row would leave int32 in OUT.
        Option.when(fused.contains(producer))(
          s"'$consumer' is aliased to '$producer', whose rescale is still" +
            s" fused into a downstream reshape - its OUT would hold int32"
        )
      ).flatten
    }

  /** The full ordered exec-step list. `kind` is one of: format_input, im2row,
    * int32_chain, vta, rescale, qadd, concat, dequant, quant, convtranspose,
    * unsupported. Pre-step inclusion uses the SAME guards as genExecPlanHeader
    * (suffixToIdx membership; int32 needs ACC byteSize > 0). A `rescale` step is
    * emitted after a VTA layer only when its rescale is not fused into a
    * downstream reshape (see [[fusedRescaleProducers]]).
    */
  def of(
    dep: DependencyInfo,
    layers: Seq[Model.LayerInfo],
    suffixToIdx: Map[String, Int],
    logOutWidth: Int
  ): Seq[ExecStep] = {
    val fused = fusedRescaleProducers(dep, layers, suffixToIdx, logOutWidth)
    // Layers whose INP a CPU op writes directly.
    val cpuWritten = cpuOutRetargets(dep, layers, suffixToIdx).values.toSet

    // (kind, layerName) pairs in execution order; stepIdx is the position, so it
    // is assigned by zipWithIndex below (matching the old running-counter `add`).
    val raw: Seq[(String, String)] =
      dep.executionOrder.flatMap { case (_, processor, layerName) =>
        if (processor == "vta") {
          val pre: Seq[(String, String)] =
            (for {
              ld <- dep.layers.get(layerName).toSeq
              lidx <- suffixToIdx.get(layerName).toSeq
            } yield {
              if (ld.reshapeInfo == "im2row") {
                if (ld.deps.headOption.contains("image"))
                  Seq("format_input" -> layerName)
                else if (
                  dep.aliases.contains(layerName) ||
                  cpuWritten.contains(layerName)
                ) Seq.empty
                else Seq("im2row" -> layerName)
              } else if (ld.reshapeInfo == "direct") {
                // A direct convolution reads flat; its producer wrote blocked.
                Seq("relayout_in" -> layerName)
              } else if (
                ld.reshapeInfo == "int32" &&
                layers(lidx).mem("ACC").byteSize != 0L
              ) Seq("int32_chain" -> layerName)
              else Seq.empty
            }).flatten
          val rescale =
            if (logOutWidth > 3 && !fused.contains(layerName))
              Seq("rescale" -> layerName)
            else Seq.empty
          // and back out of the flat layout afterwards, so consumers see the
          // canonical block-tiled form. After the rescale, which is elementwise
          // and so indifferent, and which leaves int8 to move rather than int32.
          val relayoutOut =
            dep.layers
              .get(layerName)
              .filter(_.reshapeInfo == "direct")
              .map(_ => Seq("relayout_out" -> layerName))
              .getOrElse(Seq.empty)
          pre ++ Seq("vta" -> layerName) ++ rescale ++ relayoutOut
        } else {
          val kind = processor match {
            case "qadd" | "concat" | "dequant" | "quant" => processor
            case "convtranspose"                         => "convtranspose"
            case _                                       => "unsupported"
          }
          Seq(kind -> layerName)
        }
      }
    raw.zipWithIndex.map { case ((kind, name), i) => ExecStep(i, kind, name) }
  }
}
