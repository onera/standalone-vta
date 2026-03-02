package vta.interface

import chisel3._
import org.scalatest.flatspec.AnyFlatSpec
import org.scalatest.matchers.should.Matchers
import chisel3.simulator.scalatest.ChiselSim
import vta.test.AxiFullSimUtils
import os.Source.WritableSource
import vta.interface.axi.AXIClient
import vta.interface.axi.AxiLike._
import vta.util.config.Parameters
import vta.DefaultPynqConfig
import vta.shell.ShellKey
import vta.util.SimulationUtils.verilatorWithWaveDump
import vta.util.SimulationUtils

class AxiLikeSpec
    extends AnyFlatSpec
    with ChiselSim
    with AxiFullSimUtils
    with Matchers {
  behavior of "axi4-full"

  implicit val parameters: Parameters = new DefaultPynqConfig
  implicit val simulWave = verilatorWithWaveDump

  class MockMem extends Module {
    val io = IO(new AXIClient(parameters(ShellKey).memParams))
    val readAddress = io.readHandler(true.B)
    val writeAddress = io.writeHandler(true.B)

    val mem = Mem(10, UInt(parameters(ShellKey).memParams.dataBits.W))

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
