package formal

import chisel3._
import chisel3.util._
import chiseltest._
import chiseltest.formal._
import chiseltest.experimental.observe
import chiseltest.simulator.WriteVcdAnnotation
import org.scalatest.flatspec.AnyFlatSpec
import _root_.circt.stage.ChiselStage

import vta.core.MAC

/**
 * Testing MacVTA
 */
class MacTest extends AnyFlatSpec with ChiselScalatestTester {
  behavior of "MAC"

  // Functional tests
  it should "accumulate correctly when enabled" in {
    test(new MAC(8, 8, 16, true)).withAnnotations(Seq(WriteVcdAnnotation)) { dut =>
      // Test A => 2 * 3 = 6
      print("\t Test A -> 2 * 3 = 6")
      dut.io.a.poke(2.S)
      dut.io.b.poke(3.S)
      dut.io.c.poke(0.S)
      dut.clock.step()
      dut.io.y.expect(6.S)  // Expected

      // Test B => 6 + (4 * 5) = 26
      print("\n\n\t Test B -> 6 + (4 * 5) = 26")
      dut.io.a.poke(4.S)
      dut.io.b.poke(5.S)
      dut.io.c.poke(6.S)
      dut.clock.step()
      dut.io.y.expect(26.S)  // Expected

      // Test C => reset and compute (-1 * 5) - 2 = -7
      print("\n\n\t Test C -> reset and compute 3 * 5 = 15 -> reset do nothing...")
      dut.reset.poke(true.B)
      dut.io.a.poke(-1.S)
      dut.io.b.poke(5.S)
      dut.io.c.poke(-2.S)
      dut.clock.step()
      dut.io.y.expect(-7.S) // Reset do nothing
    }
  }
}


/**
 * Formal verification
 */
class MacFormalSpec_Computation_flopOut extends Module {
  // Create an instance of our DUT and expose its I/O
  val dut = Module(new MAC(8, 8, 16, false))
  val io = IO(chiselTypeOf(dut.io))
  io <> dut.io

  // Create a cross module binding to inspect internal state
  val mult = observe(dut.mult)
  val add = observe(dut.add)
  val addV = observe(dut.addV)
  val rA = observe(dut.rA)
  val rB = observe(dut.rB)
  val rC = observe(dut.rC)

  // PROPERTIES
  // ----------
  // rA = a, rB = b, rC = c (we consider flopIn = false)
  assert(io.a === rA, "Signal rA should be equal to port A (when flopIn is false)")
  assert(io.b === rB, "Signal rB should be equal to port B (when flopIn is false)")
  assert(io.c === rC, "Signal rC should be equal to port C (when flopIn is false)")

  // Output Y is always equal to the register output (addV)
  assert(io.y === addV, "Y should be equal to addV")

  // Computation chain: mult = rA*rB, add = mult +& rC (+& perform a sign extension)
  assert(mult === (rA * rB), "mult should be the product of rA and rB")
  assert(add === mult +& rC, "add should be the signed sum (+&) of mult and rC")

  // Register node (we consider flopIn = false)
  assert(addV === past(add), "addV should be the previous state of add (when flopIn is false)")
  assert(addV === past((mult) +& rC), "addV should be the previous mult +& rC (when flopIn is false)")

  // Functional verification on the input-output
  assert(io.y === past((io.a * io.b) +& io.c), "Y should be the computation of the previous input signals")
}

class MacFormalSpec_Computation_flopIn extends Module {
  // Create an instance of our DUT and expose its I/O
  val dut = Module(new MAC(8, 8, 16, true))
  val io = IO(chiselTypeOf(dut.io))
  io <> dut.io

  // Create a cross module binding to inspect internal state
  val mult = observe(dut.mult)
  val add = observe(dut.add)
  val addV = observe(dut.addV)
  val rA = observe(dut.rA)
  val rB = observe(dut.rB)
  val rC = observe(dut.rC)

  // PROPERTIES
  // ----------
  // REGISTER IN INPUT
  assert(rA === past(io.a))
  assert(rB === past(io.b))
  assert(rC === past(io.c))

  // Output Y is always equal to the register output (addV)
  assert(io.y === addV, "Y should be equal to addV")

  // Computation chain: mult = rA*rB, add = mult +& rC (+& perform a sign extension)
  assert(mult === (rA * rB), "mult should be the product of rA and rB")
  assert(add === mult +& rC, "add should be the signed sum (+&) of mult and rC")

  // NO REGISTER NODE IN OUTPUT
  assert(addV === add)
  assert(addV === (mult) +& rC)

  // Functional verification on the input-output
  assert(io.y === past((io.a * io.b) +& io.c), "Y should be the computation of the previous input signals")
}

class MacFormalSpec_FailExample(makeDut: => MAC) extends Module {
  // Create an instance of our DUT and expose its I/O
  val dut = Module(makeDut)
  val io = IO(chiselTypeOf(dut.io))
  io <> dut.io

  // PROPERTIES
  // ----------
  // It fails because Y is the previous (past) result of the computation
  assert(io.y === (io.a * io.b) +& io.c)
}

class MacFormalSpec_Overflow(makeDut: => MAC) extends Module {
  // Create an instance of our DUT and expose its I/O
  val dut = Module(makeDut)
  val io = IO(chiselTypeOf(dut.io))
  io <> dut.io

  // Get the constant of the component
  val outBits = dut.outBits // No observer needed

  // Create a cross module binding to inspect internal state
  val mult = observe(dut.mult)
  val add = observe(dut.add)

  // NO OVERFLOW PROPERTIES
  // ----------------------
  // Define the possible range of value for Y (e.g., int8 = [-128; 127] = [-(2^8-1); (2^8-1) - 1]
  val YminValue = (-(1 << (outBits - 1))).S(outBits.W) // (2^n) => 1 << n OR: 1L << n (1L = Long integer) to avoid overflow
  val YmaxValue = ((1 << (outBits - 1)) - 1).S(outBits.W)
  assert(io.y >= YminValue && io.y <= YmaxValue, "There is an overflow on Y")

  // Define the possible range of value for mult
  val multBits = mult.getWidth
  val multMinValue = (-(1 << (multBits - 1))).S(multBits.W)
  val multMaxValue = ((1 << (multBits - 1)) - 1).S(multBits.W)
  assert((io.a * io.b) >= multMinValue && (io.a * io.b) <= multMaxValue, "There is an overflow on mult")

  // Define the possible range of value for add
  val addBits = add.getWidth
  val addMinValue = (-(1 << (addBits - 1))).S(addBits.W)
  val addMaxValue = ((1 << (addBits - 1)) - 1).S(addBits.W)
  assert((mult +& io.c) >= addMinValue && (mult +& io.c) <= addMaxValue, "There is an overflow on add")
}


/**
 * Execute Formal test
 */
class MacFormalTester extends AnyFlatSpec with ChiselScalatestTester with Formal {
  "MAC_flopOut" should "pass computation properties" in {
    verify(new MacFormalSpec_Computation_flopOut, Seq(BoundedCheck(10), WriteVcdAnnotation))
  }
  "MAC_flopIn" should "pass computation properties" in {
    verify(new MacFormalSpec_Computation_flopIn, Seq(BoundedCheck(10), WriteVcdAnnotation))
  }
  "MAC" should "not pass these properties" in {
    verify(new MacFormalSpec_FailExample(new MAC(8, 8, 16, false)), Seq(BoundedCheck(10), WriteVcdAnnotation))
  }
  "MAC" should "pass overflow properties" in {
    verify(new MacFormalSpec_Overflow(new MAC), Seq(BoundedCheck(10)))
  }
}


/**
 * Emit SystemVerilog design
 * Generate System Verilog sources and save it in file .sv
 */
object MacEmitter extends App {
  ChiselStage.emitSystemVerilogFile(
    new MAC,
    firtoolOpts = Array("-disable-all-randomization", "-strip-debug-info", "-o", "test_run_dir/output/MAC.sv")
  )
}
