package formal

import chisel3._
import chisel3.util._
import chiseltest._
import chiseltest.formal._
import chiseltest.experimental.observe
import chiseltest.simulator.WriteVcdAnnotation
import org.scalatest.flatspec.AnyFlatSpec
import _root_.circt.stage.ChiselStage
import vta.util.config._

import vta.core.TensorGemm

/**
 * Formal verification
 */


/**
 * Execute Formal test
 */


/**
 * Emit SystemVerilog design
 * Generate System Verilog sources and save it in file .sv
 */
object TensorGemmEmitter extends App{
  val SimParam = new SimConfig
  implicit val p: Parameters = SimParam.config

  // Emit circuit
  ChiselStage.emitSystemVerilogFile(
    new TensorGemm()(p),
      firtoolOpts = Array("-disable-all-randomization", "-strip-debug-info",  "-o", "test_run_dir/output/TensorGemm.sv")
  )
}
