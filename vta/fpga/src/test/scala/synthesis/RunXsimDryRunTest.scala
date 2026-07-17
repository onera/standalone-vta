package fpga.synthesis

import org.scalatest.flatspec.AnyFlatSpec
import org.scalatest.matchers.should.Matchers

class RunXsimDryRunTest extends AnyFlatSpec with Matchers {
  private def tbDir(): os.Path = {
    val tb = os.temp.dir()
    Seq(
      "VTAPostSynthTb.sv",
      "VtaHostDriver.sv",
      "MultiMemAxiClient.sv",
      "memory_0.sv"
    )
      .foreach(f => os.write(tb / f, "// stub\n"))
    tb
  }

  "RunXsim --behavioral --dry-run" should "plan xvlog+xelab with the layer-idx width and not run xsim" in {
    val tb = tbDir()
    val out = os.temp.dir()
    val plan = RunXsim.planFor(
      Array(
        "--behavioral",
        "--tb",
        tb.toString,
        "--out",
        out.toString,
        "--layers",
        "3",
        "--dry-run"
      )
    )
    // layers=3 -> ceil(log2(max(3,2))) = 2 bits.
    plan.idxWidth shouldBe 2
    plan.mode shouldBe "behavioral"
    plan.commands.head should startWith("xvlog")
    plan.commands.exists(_.startsWith("xelab sim_top")) shouldBe true
    plan.commands.exists(
      _.contains("unisims_ver")
    ) shouldBe false // behavioral leg
  }

  "RunXsim --netlist --dry-run" should "plan the netlist parse + unisim elaboration" in {
    val tb = tbDir()
    val out = os.temp.dir()
    val netlist = os.temp(suffix = "_funcsim.v")
    val plan = RunXsim.planFor(
      Array(
        "--netlist",
        netlist.toString,
        "--tb",
        tb.toString,
        "--out",
        out.toString,
        "--layers",
        "1",
        "--dry-run"
      )
    )
    plan.idxWidth shouldBe 1 // ceil(log2(max(1,2))) = 1
    plan.mode shouldBe "netlist"
    plan.commands.exists(c =>
      c.startsWith("xvlog") && c.contains("_funcsim.v")
    ) shouldBe true
    plan.commands.exists(c =>
      c.startsWith("xelab") && c.contains("unisims_ver")
    ) shouldBe true
  }
}
