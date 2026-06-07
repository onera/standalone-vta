package vta.test

import chisel3._
import org.scalatest.flatspec.AnyFlatSpec
import vta.shell.{ShellKey, VCR}
import vta.test.CompilerOutputLayout.LaunchParams
import vta.util.AnyFlatSpecSim
import vta.util.config.Parameters

/** Driver + VCR (its AXILite slave). Exposes VCR outputs and a finish poke so
  * the test can emulate the core completing each layer.
  */
class DriverVcrHarness(layers: Seq[LaunchParams])(implicit p: Parameters)
    extends Module {
  val io = IO(new Bundle {
    val finish = Input(Bool())
    val launch = Output(Bool())
    val ptrs = Output(Vec(6, UInt(32.W)))
    val vals = Output(Vec(1, UInt(32.W)))
    val done = Output(Bool())
    val error = Output(Bool())
    val layerIdx = Output(UInt(chisel3.util.log2Ceil((layers.size).max(2)).W))
  })
  val drv = Module(new VtaHostDriver(layers, perLayerTimeout = 100000))
  val vcr = Module(new VCR)
  drv.io.host <> vcr.io.host
  vcr.io.vcr.finish := io.finish
  vcr.io.vcr.ecnt.foreach { e => e.valid := false.B; e.bits := 0.U }
  vcr.io.vcr.ucnt.foreach { u => u.valid := false.B; u.bits := 0.U }
  io.launch := vcr.io.vcr.launch
  io.ptrs := vcr.io.vcr.ptrs
  io.vals := vcr.io.vcr.vals
  io.done := drv.io.done
  io.error := drv.io.error
  io.layerIdx := drv.io.layerIdx
}

class VtaHostDriverSpec extends AnyFlatSpec with AnyFlatSpecSim {
  behavior of "VtaHostDriver"

  private def stepUntilLaunch(dut: DriverVcrHarness, clock: Clock): Unit = {
    var g = 0
    while (!dut.io.launch.peekBoolean() && g < 500) { clock.step(1); g += 1 }
    assert(g < 500, "driver never asserted launch")
  }

  it should "program VCR, launch, and advance through two layers to done" in {
    val layers = Seq(
      LaunchParams(insnBaddr = 0x1000, insnCount = 7, relo = 0x0),
      LaunchParams(insnBaddr = 0x201000, insnCount = 5, relo = 0x200000)
    )
    simulate(new DriverVcrHarness(layers)) { dut =>
      implicit val clock = dut.clock
      dut.io.finish.poke(false.B)

      // ---- layer 0 ----
      stepUntilLaunch(dut, clock)
      // ptrs(0)=insn base, ptrs(1..5)=relo, vals(0)=insnCount
      assert(dut.io.ptrs(0).peek().litValue == BigInt(0x1000))
      (1 to 5).foreach(i =>
        assert(dut.io.ptrs(i).peek().litValue == BigInt(0x0), s"ptr$i")
      )
      assert(dut.io.vals(0).peek().litValue == BigInt(7))
      assert(dut.io.layerIdx.peek().litValue == BigInt(0))
      // emulate core finishing layer 0
      dut.io.finish.poke(true.B); clock.step(1); dut.io.finish.poke(false.B)

      // ---- layer 1 ----
      stepUntilLaunch(dut, clock)
      assert(dut.io.ptrs(0).peek().litValue == BigInt(0x201000))
      (1 to 5).foreach(i =>
        assert(dut.io.ptrs(i).peek().litValue == BigInt(0x200000), s"ptr$i L1")
      )
      assert(dut.io.vals(0).peek().litValue == BigInt(5))
      assert(dut.io.layerIdx.peek().litValue == BigInt(1))
      dut.io.finish.poke(true.B); clock.step(1); dut.io.finish.poke(false.B)

      // ---- done ----
      var g = 0
      while (!dut.io.done.peekBoolean() && g < 500) { clock.step(1); g += 1 }
      assert(dut.io.done.peekBoolean(), "driver never reached done")
      assert(!dut.io.error.peekBoolean(), "driver flagged error")
    }
  }
}
