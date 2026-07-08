package fpga.host.exporters

import org.scalatest.flatspec.AnyFlatSpec
import fpga.host.models._
import fpga.host.transform.MemoryLayout
import fpga.host.parsers.LayerParser
import fpga.host.exporters.all._
import vta.parsers.Dependency.loadDependencyInfo

class EmitLoadersGoldenTest extends AnyFlatSpec {
  for (name <- GoldenSupport.cases) {
    s"emit loaders [$name]" should "match golden tcl/asm/ld" in {
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
      val d = GoldenSupport.sandbox("emit-loaders", name)
      LoadTcl(
        layers,
        c.ddrBase,
        c.comp.toString,
        scriptName = "load_nn_static.tcl",
        includeInput = false,
        extraBlobs = ctBlobs
      ).export(d / "load_nn_static.tcl")
      LoadTcl(
        layers,
        c.ddrBase,
        c.comp.toString,
        scriptName = "load_nn.tcl",
        includeInput = true,
        extraBlobs = ctBlobs
      ).export(d / "load_nn.tcl")
      InputTcl(layers, c.ddrBase, c.comp.toString)
        .export(d / "load_input.tcl")
      AsmIncbin(layers, extraBlobs = ctBlobs).export(d / "nn_bin_data.S")
      LinkerFragment(layers, c.ddrBase, extraBlobs = ctBlobs)
        .export(d / "nn_vta_sections.ld")
      for (
        f <- Seq(
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
