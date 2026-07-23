package fpga.host

import org.scalatest.flatspec.AnyFlatSpec
import org.scalatest.matchers.should.Matchers
import fpga.host.models.GoldenSupport
import fpga.host.parsers.ConfigParser

class GenSdModeGoldenTest extends AnyFlatSpec with Matchers {
  for (name <- GoldenSupport.cases) {
    s"GenNnBaremetal --emit-sd-manifest [$name]" should "reproduce gen-sd goldens" in {
      val c = GoldenSupport.loadCase(name)
      val outDir = GoldenSupport.sandbox("gen-sd-mode", name)
      GenNnBaremetal.generate(
        compDir = c.comp.toString,
        outdir = outDir.toString,
        ddrBase = c.ddrBase,
        cfg = ConfigParser.load(c.cfg.toString),
        emitSdManifest = true
      )
      os.read(outDir / "nn_sd_manifest.h") shouldBe os.read(
        c.dir / "gen-sd" / "nn_sd_manifest.h"
      )
      val staged = os
        .walk(outDir / "sd_card")
        .filter(os.isFile)
        .map(_.relativeTo(outDir / "sd_card").toString)
        .sorted
      staged shouldBe os.read
        .lines(c.dir / "gen-sd" / "staged_files.txt")
        .toList
    }
  }

  for (name <- GoldenSupport.cases) {
    s"GenNnBaremetal --no-stage-sd-files [$name]" should
      "emit the manifest without staging any binaries" in {
        val c = GoldenSupport.loadCase(name)
        val outDir = GoldenSupport.sandbox("gen-sd-nostage", name)
        GenNnBaremetal.generate(
          compDir = c.comp.toString,
          outdir = outDir.toString,
          ddrBase = c.ddrBase,
          cfg = ConfigParser.load(c.cfg.toString),
          emitSdManifest = true,
          stageSdFiles = false
        )
        os.read(outDir / "nn_sd_manifest.h") shouldBe os.read(
          c.dir / "gen-sd" / "nn_sd_manifest.h"
        )
        os.exists(outDir / "sd_card") shouldBe false
      }
  }
}
