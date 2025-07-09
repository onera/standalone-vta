package formal

import chisel3._
import chisel3.util._
import chiseltest._
import chiseltest.formal._
import chiseltest.experimental.observe
import chiseltest.simulator.WriteVcdAnnotation
import org.scalatest.flatspec.AnyFlatSpec
import _root_.circt.stage.ChiselStage

import vta.core.DotProduct


/**
 * Testing MacVTA
 */
class DotProductTest extends AnyFlatSpec with ChiselScalatestTester {
  behavior of "DotProduct"

  it should "compute dot product correctly" taggedAs(UnitTests) in {
    test(new DotProduct).withAnnotations(Seq(WriteVcdAnnotation)) { dut =>
      // Test case 1: Y = 2
      dut.io.a(0).poke(2.S)
      dut.io.a(1).poke(2.S)
      dut.io.a(2).poke(1.S)
      dut.io.a(3).poke(1.S)
      dut.io.a(4).poke(0.S)
      dut.io.a(5).poke(0.S)
      dut.io.a(6).poke(0.S)
      dut.io.a(7).poke(0.S)
      dut.io.a(8).poke(0.S)
      dut.io.a(9).poke(0.S)
      dut.io.a(10).poke(0.S)
      dut.io.a(11).poke(0.S)
      dut.io.a(12).poke(0.S)
      dut.io.a(13).poke(0.S)
      dut.io.a(14).poke(0.S)
      dut.io.a(15).poke(0.S)

      dut.io.b(0).poke(1.S)
      dut.io.b(1).poke(1.S)
      dut.io.b(2).poke(-1.S)
      dut.io.b(3).poke(-1.S)
      dut.io.b(4).poke(0.S)
      dut.io.b(5).poke(0.S)
      dut.io.b(6).poke(0.S)
      dut.io.b(7).poke(0.S)
      dut.io.b(8).poke(0.S)
      dut.io.b(9).poke(0.S)
      dut.io.b(10).poke(0.S)
      dut.io.b(11).poke(0.S)
      dut.io.b(12).poke(0.S)
      dut.io.b(13).poke(0.S)
      dut.io.b(14).poke(0.S)
      dut.io.b(15).poke(0.S)

      dut.clock.step(1)

      // Test case 2: Y = -2
      dut.io.a(0).poke(1.S)
      dut.io.a(1).poke(1.S)
      dut.io.a(2).poke(2.S)
      dut.io.a(3).poke(2.S)

      dut.clock.step(1)

      // Expected result of test case 1
      dut.io.y.expect(2.S)

      dut.clock.step(1)

      // Expected result of test case 2
      dut.io.y.expect(-2.S)

      // RESET DO NOTHING
      dut.reset.poke(true.B)
      dut.clock.step(1)
      dut.io.y.expect(-2.S)
    }
  }
}


/**
 * Formal verification
 */
class DotProductFormalSpec(makeDut: => DotProduct) extends Module {
  // Create an instance of our DUT and expose its I/O
  val dut = Module(makeDut)
  val io = IO(chiselTypeOf(dut.io))
  io <> dut.io

  // Create a cross module binding to inspect internal state

  // PROPERTIES
  // ----------
  // Global functional behaviour
  val product = Wire(Vec(16, SInt(16.W)))
  for (i <- 0 until 16) {
    product(i) := io.a(i) * io.b(i)
  }
  val accumulation = product.reduce(_ +& _)

  assert(io.y === past(accumulation, 2))
//  assert(io.y === past(io.a(0) * io.b(0)
//    +& io.a(1) * io.b(1)
//    +& io.a(2) * io.b(2)
//    +& io.a(3) * io.b(3)
//    +& io.a(4) * io.b(4)
//    +& io.a(5) * io.b(5)
//    +& io.a(6) * io.b(6)
//    +& io.a(7) * io.b(7)
//    +& io.a(8) * io.b(8)
//    +& io.a(9) * io.b(9)
//    +& io.a(10) * io.b(10)
//    +& io.a(11) * io.b(11)
//    +& io.a(12) * io.b(12)
//    +& io.a(13) * io.b(13)
//    +& io.a(14) * io.b(14)
//    +& io.a(15) * io.b(15), 2)
//  )
}

class DotProductFormalSpec_Decomposed(makeDut: => DotProduct) extends Module {
  // Create an instance of our DUT and expose its I/O
  val dut = Module(makeDut)
  val io = IO(chiselTypeOf(dut.io))
  io <> dut.io

  // Create a cross module binding to inspect internal state
  val macs = dut.m.map(mac => observe(mac.io.y)) // Get MAC output
  val firstLayerAdders = dut.a(0).map(adder => observe(adder.io.y)) // Get 1st layer of Adders
  val secondLayerAdders = dut.a(1).map(adder => observe(adder.io.y)) // Get 2nd layer of Adder
  val thirdLayerAdders = dut.a(2).map(adder => observe(adder.io.y)) // Get PipeAdder output
  val finalAdderOutput = observe(dut.a(3)(0).io.y) // Get the output

  // PROPERTIES
  // ----------
  //assert(macs(0) === past(io.a(0) * io.b(0)))
  // MAC outputs
  for (i <- 0 until 16) {
    assert(macs(i) === past(io.a(i) * io.b(i)))
  }

  // 1st Adders outputs
  for (i <- 0 until 8) {
    assert(firstLayerAdders(i) === (macs(2 * i) +& macs(2 * i + 1)))
  }

  // 2nd Adders outputs
  for (i <- 0 until 4) {
    assert(secondLayerAdders(i) === (firstLayerAdders(2 * i) +& firstLayerAdders(2 * i + 1)))
  }

  // 3rd Adders outputs -> PipeAdder
  for (i <- 0 until 2) {
    assert(thirdLayerAdders(i) === past(secondLayerAdders(2 * i) +& secondLayerAdders(2 * i + 1)))
  }

  // 4th and last Adder output
  assert(finalAdderOutput === (thirdLayerAdders(0) +& thirdLayerAdders(1)))

  // Output
  assert(io.y === finalAdderOutput)
}


/**
 * Execute Formal test
 */
class DotProductFormalTester extends AnyFlatSpec with ChiselScalatestTester with Formal {
  "DotProduct" should "pass formal properties" taggedAs(LongTests) in {
    verify(new DotProductFormalSpec(new DotProduct), Seq(BoundedCheck(5), WriteVcdAnnotation))
  }
  "DotProduct" should "pass decomposed formal properties" taggedAs(FormalTests) in {
    verify(new DotProductFormalSpec_Decomposed(new DotProduct), Seq(BoundedCheck(5), WriteVcdAnnotation))
  }
}


/**
 * Emit SystemVerilog design
 * Generate System Verilog sources and save it in file .sv
 */
object DotProductEmitter extends App {
  ChiselStage.emitSystemVerilogFile(
    new DotProduct,
    firtoolOpts = Array("-disable-all-randomization", "-strip-debug-info",  "-o", "test_run_dir/output/DotProduct.sv")
  )
}