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

<<<<<<< HEAD

/**
 * Formal verification
 */
=======
/** Formal verification
  */
>>>>>>> 29f3bd6 (refactor tests into main sources for simulation VTA full)
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

<<<<<<< HEAD

/**
 * Execute Formal test
 */
class ComputeFormalTester extends AnyFlatSpec with ChiselScalatestTester with Formal {
=======
/** Execute Formal test
  */
class ComputeFormalTester
    extends AnyFlatSpec
    with ChiselScalatestTester
    with Formal {
>>>>>>> 29f3bd6 (refactor tests into main sources for simulation VTA full)
  val SimParam = new SimConfig
  implicit val p: Parameters = SimParam.config

//  // Formal Verification
//  "Compute" should "pass formal properties" taggedAs(FormalTests) in {
//    verify(new ComputeFormalSpec(new Compute()(p)), Seq(BoundedCheck(10), WriteVcdAnnotation))
//  }
}

<<<<<<< HEAD

/**
 * Emit SystemVerilog design
 * Generate System Verilog sources and save it in file .sv
 */
=======
/** Emit SystemVerilog design Generate System Verilog sources and save it in
  * file .sv
  */
>>>>>>> 29f3bd6 (refactor tests into main sources for simulation VTA full)
object ComputeEmitter extends App {
  val SimParam = new SimConfig
  implicit val p: Parameters = SimParam.config

  // Emit circuit
  ChiselStage.emitSystemVerilogFile(
    new Compute()(p),
<<<<<<< HEAD
    firtoolOpts = Array("-disable-all-randomization", "-strip-debug-info",  "-o", "test_run_dir/output/Compute.sv")
  )
}

=======
    firtoolOpts = Array(
      "-disable-all-randomization",
      "-strip-debug-info",
      "-o",
      "test_run_dir/output/Compute.sv"
    )
  )
}
>>>>>>> 29f3bd6 (refactor tests into main sources for simulation VTA full)
