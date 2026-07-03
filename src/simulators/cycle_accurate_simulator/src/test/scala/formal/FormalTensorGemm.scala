package formal

import _root_.circt.stage.ChiselStage
import vta.core.TensorGemm
import vta.util.config._

/** Formal verification
  */

/** Execute Formal test
  */

/** Emit SystemVerilog design Generate System Verilog sources and save it in
  * file .sv
  */
object TensorGemmEmitter extends App {
  val SimParam = new SimConfig
  implicit val p: Parameters = SimParam.config

  // Emit circuit
  ChiselStage.emitSystemVerilogFile(
    new TensorGemm()(p),
    firtoolOpts = Array(
      "-disable-all-randomization",
      "-strip-debug-info",
      "-o",
      "test_run_dir/output/TensorGemm.sv"
    )
  )
}
