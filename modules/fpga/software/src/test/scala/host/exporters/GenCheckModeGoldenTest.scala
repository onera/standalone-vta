package fpga.host

import org.scalatest.flatspec.AnyFlatSpec
import org.scalatest.matchers.should.Matchers
import fpga.host.models.GoldenSupport
import fpga.host.parsers.ConfigParser

class GenCheckModeGoldenTest extends AnyFlatSpec with Matchers {
  for (name <- GoldenSupport.cases) {
    s"GenNnBaremetal --emit-cpu-check [$name]" should "reproduce gen-debug goldens" in {
      val c = GoldenSupport.loadCase(name)
      val outDir = GoldenSupport.sandbox("gen-check-mode", name)
      GenNnBaremetal.generate(
        compDir = c.comp.toString,
        outdir = outDir.toString,
        ddrBase = c.ddrBase,
        cfg = ConfigParser.load(c.cfg.toString),
        emitCpuCheck = true,
        goldenDir = Some(c.comp.toString)
      )
      // maps: direct compare
      for (f <- Seq("nn_debug_map.h", "nn_cpu_debug_map.h"))
        os.read(outDir / f) shouldBe os.read(c.dir / "gen-debug" / f)
      // augmented loaders: canonicalize the comp abspath
      for (f <- Seq("nn_bin_data.S", "nn_vta_sections.ld"))
        os.read(outDir / f).replace(c.comp.toString, "@COMP_DIR@") shouldBe
          os.read(c.dir / "gen-debug" / f)
      // base headers still match the no-flag goldens
      for (f <- Seq("vta_hw_config.h", "nn_ddr_map.h", "nn_exec_plan.h"))
        os.read(outDir / f) shouldBe os.read(c.gen / f)
    }
  }
}
