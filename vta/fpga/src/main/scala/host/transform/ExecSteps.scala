package fpga.host.transform

import vta.models.CompilerOutputModel.DependencyInfo
import fpga.host.models._

object ExecSteps {

  /** The full ordered exec-step list. `kind` is one of: format_input, im2row,
    * int32_chain, vta, rescale, qadd, concat, dequant, quant, convtranspose,
    * unsupported. Pre-step inclusion uses the SAME guards as genExecPlanHeader
    * (suffixToIdx membership; int32 needs ACC byteSize > 0).
    */
  def of(
    dep: DependencyInfo,
    layers: Seq[Model.LayerInfo],
    suffixToIdx: Map[String, Int],
    logOutWidth: Int
  ): Seq[ExecStep] = {
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
              } else if (
                ld.reshapeInfo == "int32" &&
                layers(lidx).mem("ACC").byteSize != 0L
              ) Seq("int32_chain" -> layerName)
              else Seq.empty
            }).flatten
          val rescale =
            if (logOutWidth > 3) Seq("rescale" -> layerName) else Seq.empty
          pre ++ Seq("vta" -> layerName) ++ rescale
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
