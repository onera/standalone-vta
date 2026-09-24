package fpga.host.transform

import vta.models.CompilerOutputModel.DependencyInfo
import fpga.host.models._

object ExecSteps {

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

    def isReshapeConsumer(name: String): Boolean =
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
