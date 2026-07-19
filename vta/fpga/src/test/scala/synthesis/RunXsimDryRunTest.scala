package fpga.synthesis

import org.scalatest.flatspec.AnyFlatSpec
import org.scalatest.matchers.should.Matchers

class RunXsimDryRunTest extends AnyFlatSpec with Matchers {
  // Basename of a planned command's executable: the tools resolve to an
  // absolute $XILINX_VIVADO/bin path when that env var is set, bare names
  // otherwise, and the plan must be assertable in both environments.
  private def tool(cmd: String): String =
    cmd.takeWhile(_ != ' ').split(Array('/', '\\')).last

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
    tool(plan.commands.head) shouldBe "xvlog"
    plan.commands.exists(c =>
      tool(c) == "xelab" && c.contains("sim_top")
    ) shouldBe true
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
      tool(c) == "xvlog" && c.contains("_funcsim.v")
    ) shouldBe true
    plan.commands.exists(c =>
      tool(c) == "xelab" && c.contains("unisims_ver")
    ) shouldBe true
  }

  "RunXsim.run with no --behavioral/--netlist" should "error and return 1" in {
    RunXsim.run(Array("--out", os.temp.dir().toString)) shouldBe 1
  }
}
