package fpga.host.models

/** Resolved, render-ready intermediate representation of the `nn_exec_steps[]`
  * table. One [[PlanStep]] per emitted C entry, with every address / count /
  * scale already resolved. Built by
  * [[fpga.host.transform.ExecPlanResolver.resolve]] and rendered (without any
  * further computation) by `HeaderRender.execPlan`.
  *
  * `stepIdx` on the main steps is the `dependency.csv` execution-order index
  * used only in the `/* step N */` comment; it is intentionally NOT the
  * position in `nn_exec_steps[]` (that count comes from
  * [[fpga.host.transform.ExecSteps]]). Pre-steps (reshape / int32-chain) carry
  * no index because their comment prints none.
  */
sealed trait PlanStep

/** Which reshape a [[ReshapeStep]] performs: they share an identical payload and
  * differ only in the C macro / struct member / name prefix / comment.
  */
sealed trait ReshapeKind
object ReshapeKind {
  case object FormatInput extends ReshapeKind
  case object Im2Row extends ReshapeKind
}

/** format_input / im2row pre-step feeding a VTA layer's INP buffer. */
final case class ReshapeStep(
    layer: String,
    kind: ReshapeKind,
    srcAddr: Long,
    inpAddr: Long,
    tensorCh: Int,
    tensorH: Int,
    tensorW: Int,
    kh: Int,
    kw: Int,
    sh: Int,
    sw: Int,
    pad: (Int, Int, Int, Int),
    offsetA: Int,
    outH: Int,
    outW: Int
) extends PlanStep

/** int32-chain pre-step feeding a maxpool/ALU layer's ACC buffer. */
final case class Int32ChainStep(
    layer: String,
    srcAddr: Long,
    dstAddr: Long,
    nElems: Long,
    offsetA: Int,
    pad: (Int, Int, Int, Int),
    tensorCh: Int,
    tensorH: Int,
    tensorW: Int
) extends PlanStep

/** A VTA layer launch (`nn_layers[vtaIdx]`). */
final case class VtaStep(stepIdx: Int, layer: String, vtaIdx: Int) extends PlanStep

/** Post-VTA CPU rescale (32-bit-out configs only). */
final case class RescaleStep(
    stepIdx: Int,
    layer: String,
    outAddr: Long,
    nElems: Long,
    scale: Double,
    offsetC: Int
) extends PlanStep

final case class QaddStep(
    stepIdx: Int,
    layer: String,
    inpA: Long,
    inpB: Long,
    out: Long,
    n: Long,
    scaleA: Double,
    scaleB: Double,
    scaleC: Double,
    offsetA: Int,
    offsetB: Int,
    offsetC: Int
) extends PlanStep

final case class ConcatStep(
    stepIdx: Int,
    layer: String,
    inpAddrs: Seq[Long],
    out: Long,
    nRows: Long,
    nChPerInp: Int,
    nbInp: Int,
    scaleA: Double,
    scaleB: Double,
    scaleU: Double,
    scaleV: Double,
    offsetA: Int,
    offsetB: Int,
    offsetU: Int,
    offsetV: Int,
    scaleC: Double,
    offsetC: Int
) extends PlanStep

final case class DequantStep(
    stepIdx: Int,
    layer: String,
    inp: Long,
    n: Long,
    scaleA: Double,
    offsetA: Int
) extends PlanStep

final case class QuantStep(
    stepIdx: Int,
    layer: String,
    out: Long,
    n: Long,
    scaleA: Double,
    offsetA: Int
) extends PlanStep

final case class ConvTransposeStep(
    stepIdx: Int,
    layer: String,
    wgtAddr: Long,
    biasAddr: Long,
    hasBias: Boolean,
    tensorCh: Int,
    tensorH: Int,
    tensorW: Int,
    outCh: Int,
    outH: Int,
    outW: Int,
    kh: Int,
    kw: Int,
    sh: Int,
    pad: (Int, Int, Int, Int),
    nOut: Long
) extends PlanStep

/** A convtranspose with no allocated params: emitted as a `.vta = { -1 }` stub. */
final case class ConvTransposeStubStep(stepIdx: Int, layer: String) extends PlanStep

/** Any unhandled processor (or a known one missing its layer): `.vta = { -1 }`. */
final case class UnsupportedStep(stepIdx: Int, layer: String, processor: String)
    extends PlanStep
