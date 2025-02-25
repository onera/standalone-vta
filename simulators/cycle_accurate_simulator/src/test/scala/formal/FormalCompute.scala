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

import vta.core.Compute


/**
 * Formal verification
 */
class ComputeFormalSpec(makeDut: => Compute) extends Module {
  // Create an instance of our DUT and expose its I/O
  val dut = Module(makeDut)
  val io = IO(chiselTypeOf(dut.io))
  io <> dut.io

  // Create a cross module binding to inspect internal state

  // PROPERTIES
  // ----------
  assert(io.inp === io.inp)
}


/**
 * Execute Formal test
 */
class ComputeFormalTester extends AnyFlatSpec with ChiselScalatestTester with Formal {
  val SimParam = new SimConfig
  implicit val p: Parameters = SimParam.config

  // Formal Verification
  "Compute" should "pass formal properties" in {
    verify(new ComputeFormalSpec(new Compute()(p)), Seq(BoundedCheck(10), WriteVcdAnnotation))
  }
}


/**
 * Emit SystemVerilog design
 * Generate System Verilog sources and save it in file .sv
 */
object ComputeEmitter extends App {
  val SimParam = new SimConfig
  implicit val p: Parameters = SimParam.config

  // Emit circuit
  ChiselStage.emitSystemVerilogFile(
    new Compute()(p),
    firtoolOpts = Array("-disable-all-randomization", "-strip-debug-info",  "-o", "test_run_dir/output/Compute.sv")
  )
}

