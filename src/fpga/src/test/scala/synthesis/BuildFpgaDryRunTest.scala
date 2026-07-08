package fpga.synthesis

import org.scalatest.flatspec.AnyFlatSpec
import org.scalatest.matchers.should.Matchers
import fpga.host.models.GoldenSupport

class BuildFpgaDryRunTest extends AnyFlatSpec with Matchers {
  "BuildFpga dry-run" should "render board_params + manifest preview without running tools" in {
    val out = GoldenSupport.sandbox("build-fpga-dry-run")
    val rc = BuildFpga.run(
      Array("--board", "zcu104", "--dry-run", "--out", out.toString)
    )
    rc shouldBe 0
    os.exists(out / "project") shouldBe false
    os.exists(
      out / "board_params.tcl"
    ) shouldBe false // dry-run prints, does not write
  }
}
