package fpga.host.exporters

import org.scalatest.flatspec.AnyFlatSpec
import org.scalatest.matchers.should.Matchers
import fpga.host.models._
import fpga.host.transform.MemoryLayout
import fpga.host.parsers.{ConfigParser, LayerParser}
import fpga.host.exporters.all._
import vta.parsers.Dependency.loadDependencyInfo

class DebugEmitGoldenTest extends AnyFlatSpec with Matchers {
  for (name <- GoldenSupport.cases) {
    s"DebugEmit [$name]" should "match golden nn_debug_map.h + nn_cpu_debug_map.h" in {
      val c = GoldenSupport.loadCase(name)
      val dep = loadDependencyInfo((c.comp / "dependency.csv").toString)
      val layers = LayerParser.collectLayers(c.comp.toString, dep)
      val cfg = ConfigParser.load(c.cfg.toString)
      val suffixToIdx = layers.zipWithIndex.map { case (l, i) =>
        l.suffix -> i
      }.toMap

      // Reproduce the cli.py layout pipeline so the golden-region base (alloc
      // top above all VTA + CPU-scratch + CPU-param allocations) matches.
      val (_, allocTop, _) =
        MemoryLayout.buildCpuOutAddrs(
          dep,
          layers,
          c.ddrBase,
          suffixToIdx,
          c.comp.toString,
          None
        )
      val (_, _, allocTop2) =
        MemoryLayout.buildCpuParamAddrs(dep, c.comp.toString, allocTop)

      // --emit-cpu-check uses the compiler_output dir as --golden-dir (golden
      // input<suffix>.bin live there; output<suffix>.bin are absent).
      val (checkedLayers, _) = MemoryLayout.assignLayerCheckRegions(
        layers,
        dep,
        c.ddrBase,
        c.comp.toString,
        allocTop2
      )

      val tmp = GoldenSupport.sandbox("debug-emit", name)

      DebugMap(checkedLayers).export(tmp / "nn_debug_map.h")
      os.read(tmp / "nn_debug_map.h") shouldBe os.read(
        c.dir / "gen-debug" / "nn_debug_map.h"
      )

      CpuDebugMap(
        dep,
        checkedLayers,
        cfg,
        suffixToIdx,
        c.ddrBase,
        c.comp.toString
      ).export(tmp / "nn_cpu_debug_map.h")
      os.read(tmp / "nn_cpu_debug_map.h") shouldBe
        os.read(c.dir / "gen-debug" / "nn_cpu_debug_map.h")
    }
  }
}
