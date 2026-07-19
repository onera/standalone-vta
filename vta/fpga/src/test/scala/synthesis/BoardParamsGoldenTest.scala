package fpga.synthesis

import org.scalatest.flatspec.AnyFlatSpec
import org.scalatest.matchers.should.Matchers

class BoardParamsGoldenTest extends AnyFlatSpec with Matchers {
  private def repoRoot: os.Path = {
    var d = os.pwd
    while (
      !os
        .exists(d / "vta" / "fpga" / "boards") && d != (d / os.up)
    ) d = d / os.up
    d
  }
  private val golden: os.Path =
    os.Path(
      java.nio.file.Paths
        .get(getClass.getClassLoader.getResource("fpga-golden").toURI)
    )

  // zcu104: non-Versal (noc_config + versal ports come from defaults).
  // vek280: Versal, omits noc_config/versal_* (defaults path).
  // vck190: Versal, overrides both noc_config and the versal_* ports.
  for (name <- Seq("zcu104", "vek280", "vck190")) {
    s"renderBoardParams [$name]" should "match the Python golden" in {
      val b = Board.load(
        (repoRoot / "vta" / "fpga" / "boards" / s"$name.json").toString
      )
      val actual = BoardParams.render(
        b,
        vtaCell = "VTA_0",
        vtaVlnv = "onera:user:VTA:0.2.0",
        ipRepo = "/fixed/ip_repo",
        outDir = "/fixed/out",
        projDir = "/fixed/out/project",
        exportDir = "/fixed/out",
        jobs = 4
      ) + "\n"
      println(actual)
      actual shouldBe os.read(golden / s"$name.board_params.tcl")
    }
  }
}
