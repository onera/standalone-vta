package vta.shell
import chisel3._
import org.scalatest.flatspec.AnyFlatSpec
import org.scalatest.matchers.should.Matchers
import chisel3.simulator.scalatest.ChiselSim
import vta.util.config.Parameters
import vta.DefaultPynqConfig

import vta.interface.axi.AXILiteClient
import vta.shell.VCRParams
import _root_.util.SimulationUtils.verilatorWithWaveDump
import chisel3.simulator.HasSimulator

class VCRSpec
    extends AnyFlatSpec
    with Matchers
    with ChiselSim
    with AxiLiteSimUtils {
  behavior of "VCR"
  implicit val verilator: HasSimulator = verilatorWithWaveDump
  "Control registers" should "be writable from the host" in {
    implicit val parameters: Parameters = new DefaultPynqConfig
    simulate(new VCR) { vcr =>
      enableWaves()
      implicit val axi = vcr.io.host
      implicit val clock = vcr.clock
      vcr.io.host.b.ready.poke(true.B)
      for (i <- (0 to 9)) {
        writeControlRegister(i * 4, i + 11)
      }
    }
  }

  "Launch" should "be configurable from the host" in {
    implicit val parameters: Parameters = new DefaultPynqConfig
    simulate(new VCR) { vcr =>
      enableWaves()
      implicit val axi = vcr.io.host
      implicit val clock = vcr.clock
      vcr.io.host.b.ready.poke(true.B)

      launchVTA()
    }
  }

  "VCR" should "be configurable from the host" in {
    implicit val parameters: Parameters = new DefaultPynqConfig
    simulate(new VCR) { vcr =>
      enableWaves()
      implicit val axi = vcr.io.host
      implicit val clock = vcr.clock
      vcr.io.host.b.ready.poke(true.B)

      // Configure memory pointers
      writeInstructionBaseAddress(0)
      writeInstructionCount(5)
      writeUopBaseAddress(100)
      writeInputBaseAddress(200)
      writeWeightBaseAddress(300)
      writeAccBaseAddress(400)
      writeOutBaseAddress(500)

      launchVTA()
      clock.stepUntil(vcr.io.vcr.finish, 1, 10)
    }
  }
}
