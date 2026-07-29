package fpga.host.exporters

import org.scalatest.flatspec.AnyFlatSpec
import org.scalatest.matchers.should.Matchers
import fpga.host.models._
import fpga.host.transform.MemoryLayout
import fpga.host.parsers.LayerParser
import fpga.host.exporters.all._
import vta.parsers.Dependency.loadDependencyInfo

class EmitSdGoldenTest extends AnyFlatSpec with Matchers {
  for (name <- GoldenSupport.cases) {
    s"SdManifest [$name]" should "match golden manifest and stage the right files" in {
      val c = GoldenSupport.loadCase(name)
      val dep = loadDependencyInfo((c.comp / "dependency.csv").toString)
      val layers = LayerParser.collectLayers(c.comp.toString, dep)
      val suffixToIdx = layers.zipWithIndex.map { case (l, i) =>
        l.suffix -> i
      }.toMap
      val (_, allocTop, _) =
        MemoryLayout.buildCpuOutAddrs(
          dep,
          layers,
          c.ddrBase,
          suffixToIdx,
          c.comp.toString
        )
      val (_, ctBlobs, _) =
        MemoryLayout.buildCpuParamAddrs(dep, c.comp.toString, allocTop)
      val d = GoldenSupport.sandbox("emit-sd", name)
      SdManifest(
        layers,
        c.ddrBase,
        c.comp.toString,
        sdCardDir = (d / "sd_card").toString,
        extraBlobs = ctBlobs
      ).export(d / "nn_sd_manifest.h")
      os.read(d / "nn_sd_manifest.h") shouldBe os.read(
        c.dir / "gen-sd" / "nn_sd_manifest.h"
      )
      val staged = os
        .walk(d / "sd_card")
        .filter(os.isFile)
        .map(_.relativeTo(d / "sd_card").toString)
        .sorted
      staged shouldBe os.read
        .lines(c.dir / "gen-sd" / "staged_files.txt")
        .toList
    }
  }
}
