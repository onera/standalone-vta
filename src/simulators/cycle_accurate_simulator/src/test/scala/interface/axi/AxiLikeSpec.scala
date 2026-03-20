package vta.interface

import chisel3._
import org.scalatest.matchers.should.Matchers
import vta.test.AxiFullSimUtils
import vta.interface.axi.AXIClient
import vta.interface.axi.AxiLike._
import vta.shell.ShellKey
import unittest.AnyFlatSpecSim

class AxiLikeSpec extends AnyFlatSpecSim with AxiFullSimUtils with Matchers {
  behavior of "axi4-full"

  class MockMem extends Module {
    val io = IO(new AXIClient(p(ShellKey).memParams))
    val readAddress = io.readHandler(true.B)
    val writeAddress = io.writeHandler(true.B)

    val mem = Mem(10, UInt(p(ShellKey).memParams.dataBits.W))

    io.r.data.bits.data := mem(readAddress)
    when(io.w.fire) {
      mem(writeAddress) := io.w.data.bits.data
    }
    io.b.bits.user := DontCare
    io.r.bits.user := DontCare
  }
  it should "correctly handle a burst read transaction" in {
    simulate(new MockMem) { dut =>
      implicit val axi = dut.io
      implicit val clock = dut.clock

      writeAxiBurst(0, (0 until 4))
      val res = readAxiBurst(0, 4)
      res.map(_.litValue.toInt) shouldBe Seq.tabulate(4) { i => i }
      clock.step(3)
    }
  }
}
