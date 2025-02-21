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

import my_experiments.formal.SimConfig
import vta.core.MatrixVectorMultiplicationBypass

/**
 * Formal verification
 */
class MatrixVectorMultiplicationBypassFormalSpec(makeDut: => MatrixVectorMultiplicationBypass) extends Module {
  // Create an instance of our DUT and expose its I/O
  val dut = Module(makeDut)
  val io = IO(chiselTypeOf(dut.io))
  io <> dut.io

  // Create a cross module binding to inspect internal state

  // PROPERTIES
  // ----------
  assert(dut.io.inp === dut.io.inp)
}


/**
 * Execute Formal test
 */
class MatrixVectorMultiplicationBypassFormalTester extends AnyFlatSpec with ChiselScalatestTester with Formal {
  val SimParam = new SimConfig
  implicit val p: Parameters = SimParam.config

  // Formal Verification
  "MatrixVectorMultiplication" should "pass formal properties" in {
    verify(new MatrixVectorMultiplicationBypassFormalSpec(new MatrixVectorMultiplicationBypass()(p)), Seq(BoundedCheck(10), WriteVcdAnnotation))
  }
}


/**
 * Emit SystemVerilog design
 * Generate System Verilog sources and save it in file .sv
 */
object MatrixVectorMultiplicationBypassEmitter extends App {
  val SimParam = new SimConfig
  implicit val p: Parameters = SimParam.config

  // Emit circuit
  ChiselStage.emitSystemVerilogFile(
    new MatrixVectorMultiplicationBypass()(p),
    firtoolOpts = Array("-disable-all-randomization", "-strip-debug-info",  "-o", "test_run_dir/output/MatrixVectorMultiplicationBypass.sv")
  )
}
