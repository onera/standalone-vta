package vta.interface

import chisel3._
import org.scalatest.flatspec.AnyFlatSpec
import chisel3.simulator.scalatest.ChiselSim
import vta.shell.AxiFullSimUtils
import vta.interface.axi.AxiClientWrapper
import os.Source.WritableSource
import vta.interface.axi.AXIClient
import vta.util.config.Parameters
import vta.DefaultPynqConfig
import vta.shell.ShellKey
import _root_.util.SimulationUtils.verilatorWithWaveDump

class ProcessSpec extends AnyFlatSpec with ChiselSim with AxiFullSimUtils {
  behavior of "axi4-full"

  implicit val parameters: Parameters = new DefaultPynqConfig
  implicit val simulWave = verilatorWithWaveDump

  class MockMem extends Module with AxiClientWrapper {
    val io = IO(new AXIClient(parameters(ShellKey).memParams))
    readHandler(io, true.B)
    writeHandler(io, true.B)
    io.r.data.bits.data := "xdeadbeef".U(32.W)
    io.b.bits.user := DontCare
    io.r.bits.user := DontCare
  }
  it should "correctly handle a burst read transaction" in {
    simulate(new MockMem) { dut =>
      enableWaves()
      implicit val axi = dut.io
      implicit val clock = dut.clock

      writeAxiBurst(0, (0 until 4))
      clock.step(3)
    }
  }
}
