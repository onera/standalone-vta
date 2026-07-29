package fpga.synthesis

import org.scalatest.flatspec.AnyFlatSpec
import org.scalatest.matchers.should.Matchers

class BoardTest extends AnyFlatSpec with Matchers {
  private def boardsDir: os.Path = {
    var d = os.pwd
    while (!os.exists(d / "modules" / "fpga" / "boards") && d != d / os.up)
      d = d / os.up
    d / "modules" / "fpga" / "boards"
  }

  "Board.load" should "read zcu104.json fields" in {
    val b = Board.load((boardsDir / "zcu104.json").toString)
    b.name shouldBe "zcu104"
    b.part should not be empty
    b.isVersal shouldBe false
    b.ports("vta_dram_master") should not be empty
    b.psClkAclks should not be empty
    b.addresses should not be empty
    b.psConfig.map(_._1) should contain("PSU__FPGA_PL0_ENABLE")
  }

  it should "read the versal board" in {
    val b = Board.load((boardsDir / "vek280.json").toString)
    b.isVersal shouldBe true
  }
}
