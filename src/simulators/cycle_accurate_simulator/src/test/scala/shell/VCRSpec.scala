package vta.shell
import chisel3._
import org.scalatest.flatspec.AnyFlatSpec
import org.scalatest.matchers.should.Matchers
import chisel3.simulator.scalatest.ChiselSim
import vta.util.config.Parameters
import vta.DefaultPynqConfig

import vta.interface.axi.AXILiteClient
import vta.util.SimulationUtils._
import unittest.AnyFlatSpecSim

class VCRSpec
    extends AnyFlatSpecSim
    with Matchers
    with vta.test.AxiLiteSimUtils {
  behavior of "VCR"
  "Control registers" should "be writable from the host" in {
    simulate(new VCR) { vcr =>
      implicit val axi = vcr.io.host
      implicit val clock = vcr.clock
      vcr.io.host.b.ready.poke(true.B)
      for (i <- (0 to 9)) {
        writeControlRegister(i * 4, i + 11)
      }
    }
  }

  "Launch" should "be configurable from the host" in {
    simulate(new VCR) { vcr =>
      implicit val axi = vcr.io.host
      implicit val clock = vcr.clock
      vcr.io.host.b.ready.poke(true.B)

      launchVTA()
    }
  }

  "VCR" should "be configurable from the host" in {
    simulate(new VCR) { vcr =>
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

      for (i <- 0 until 10) {
        writeAxiLiteReadAddress(i * 4)
        val data = readAxiLiteData()
        println(data)
      }
      clock.stepUntil(vcr.io.vcr.finish, 1, 10)
    }
  }

}
