package fpga.host

import org.scalatest.flatspec.AnyFlatSpec
import fpga.host.models.GoldenSupport
import fpga.host.parsers.ConfigParser

/** End-to-end golden test: [[GenNnBaremetal.generate]] must regenerate every
  * file in each fixture's gen/ directory byte-identically.
  */
class GenNnBaremetalGoldenTest extends AnyFlatSpec {
  for (name <- GoldenSupport.cases) {
    s"GenNnBaremetal [$name]" should "regenerate all gen/ files byte-identically" in {
      val c = GoldenSupport.loadCase(name)
      val d = GoldenSupport.sandbox("gen-nn", name)
      GenNnBaremetal.generate(
        compDir = c.comp.toString,
        outdir = d.toString,
        ddrBase = c.ddrBase,
        cfg = ConfigParser.load(c.cfg.toString),
        refDir = Some((c.comp / "reference").toString)
      )
      for (
        f <- Seq(
          "vta_hw_config.h",
          "nn_ddr_map.h",
          "nn_exec_plan.h",
          "load_nn_static.tcl",
          "load_nn.tcl",
          "load_input.tcl",
          "nn_bin_data.S",
          "nn_vta_sections.ld"
        )
      )
        GoldenSupport.assertGolden(c, f, os.read(d / f))
    }
  }
}
