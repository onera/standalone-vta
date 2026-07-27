package vta.interface.axi

import chisel3._
import org.scalatest.flatspec.AnyFlatSpec
import vta.interface.axi.AxiLike._
import vta.shell.{ShellKey, VCR}
import vta.util.AnyFlatSpecSim
import vta.util.config.Parameters

/** Drives a real VCR (AXILite slave) with the new AXILiteMaster helpers: write
  * a pointer register, then read it back through the same host bus.
  */
class MasterLoopbackHarness(implicit p: Parameters) extends Module {
  val hp = p(ShellKey).hostParams
  val io = IO(new Bundle {
    val wrStart = Input(Bool())
    val rdStart = Input(Bool())
    val addr = Input(UInt(hp.addrBits.W))
    val wdata = Input(UInt(hp.dataBits.W))
    val wrDone = Output(Bool())
    val rdDone = Output(Bool())
    val rdata = Output(UInt(hp.dataBits.W))
  })
  val vcr = Module(new VCR)
  vcr.io.vcr.finish := false.B
  vcr.io.vcr.ecnt.foreach { e => e.valid := false.B; e.bits := 0.U }
  vcr.io.vcr.ucnt.foreach { u => u.valid := false.B; u.bits := 0.U }

  val m = Wire(new AXILiteMaster(hp))
  m <> vcr.io.host

  val wd = m.writeHandler(io.wrStart, io.addr, io.wdata)
  val (rd, rdd) = m.readHandler(io.rdStart, io.addr)
  io.wrDone := wd
  io.rdDone := rdd
  io.rdata := rd
}

class AXILiteMasterSpec extends AnyFlatSpec with AnyFlatSpecSim {
  behavior of "AxiLike AXILiteMaster helpers"

  it should "write a VCR register and read it back" in {
    simulate(new MasterLoopbackHarness) { dut =>
      implicit val clock = dut.clock
      // ptrs(0) lives at byte offset 12 (insn base pointer register)
      val addr = 12
      val value = 0x1234

      dut.io.wrStart.poke(false.B)
      dut.io.rdStart.poke(false.B)
      dut.io.addr.poke(addr.U)
      dut.io.wdata.poke(value.U)
      clock.step(1)

      // issue write
      dut.io.wrStart.poke(true.B)
      clock.step(1)
      dut.io.wrStart.poke(false.B)
      var guard = 0
      while (!dut.io.wrDone.peekBoolean() && guard < 50) {
        clock.step(1); guard += 1
      }
      assert(guard < 50, "write never completed")

      // issue read of the same register
      dut.io.rdStart.poke(true.B)
      clock.step(1)
      dut.io.rdStart.poke(false.B)
      guard = 0
      var got: BigInt = -1
      while (got < 0 && guard < 50) {
        if (dut.io.rdDone.peekBoolean()) got = dut.io.rdata.peek().litValue
        clock.step(1); guard += 1
      }
      assert(got == BigInt(value), s"read back $got expected $value")
    }
  }
}
