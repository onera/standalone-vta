package fpga.synthesis

import org.scalatest.flatspec.AnyFlatSpec
import org.scalatest.matchers.should.Matchers
import fpga.synthesis.models.GoldenSupport

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

  "BuildFpga dry-run with --skip-synth" should "stop after the create-project stage and skip the manifest preview" in {
    val out = GoldenSupport.sandbox("build-fpga-dry-run-skip-synth")
    val buf = new java.io.ByteArrayOutputStream()
    val printStream = new java.io.PrintStream(buf)
    val rc = Console.withOut(printStream) {
      BuildFpga.run(
        Array(
          "--board",
          "zcu104",
          "--dry-run",
          "--skip-synth",
          "--out",
          out.toString
        )
      )
    }
    rc shouldBe 0
    os.exists(out / "project") shouldBe false
    os.exists(out / "manifest.json") shouldBe false
    val printed = buf.toString
    printed should include("skip-synth")
    printed should not include "manifest.json (preview)"
  }
}
