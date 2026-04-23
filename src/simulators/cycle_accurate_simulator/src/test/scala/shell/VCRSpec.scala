package vta.shell
import chisel3._
import org.scalatest.matchers.should.Matchers

import vta.util.SimulationUtils._
import unittest.AnyFlatSpecSim

class VCRSpec extends AnyFlatSpecSim with Matchers with vta.test.VcrTestUtils {
  behavior of "VCR"

  "VCR" should "be configurable from the host" in {
    simulate(new VCR) { vcr =>
      implicit val axi = vcr.io.host
      implicit val clock = vcr.clock
      vcr.io.host.b.ready.poke(true.B)

      // Configure memory pointers
      writeInstructionBaseAddress(10)
      writeInstructionCount(5)
      writeUopBaseAddress(100)
      writeInputBaseAddress(200)
      writeWeightBaseAddress(300)
      writeAccBaseAddress(400)
      writeOutBaseAddress(500)

      launchVTA()

      val expected = Seq(1, 0, 5, 10, 100, 200, 300, 400, 500, 0)
      for (i <- 0 until 10) {
        writeAxiLiteReadAddress(i * 4)
        val data = readAxiLiteData()
        clock.step()
        // println(data)
        data.get.litValue shouldBe expected(i)
      }
      clock.stepUntil(vcr.io.vcr.finish, 1, 10)
    }
  }

}
