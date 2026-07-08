package fpga.host

import org.scalatest.flatspec.AnyFlatSpec
import fpga.host.models._
import fpga.host.transform.MemoryLayout
import fpga.host.parsers.{ConfigParser, LayerParser}
import fpga.host.exporters.all._
import vta.parsers.Dependency.loadDependencyInfo

class NnExecPlanGoldenTest extends AnyFlatSpec {
  for (name <- GoldenSupport.cases) {
    s"ExecPlan [$name]" should "match golden nn_exec_plan.h" in {
      val c = GoldenSupport.loadCase(name)
      val dep = loadDependencyInfo((c.comp / "dependency.csv").toString)
      val layers = LayerParser.collectLayers(c.comp.toString, dep)
      val cfg = ConfigParser.load(c.cfg.toString)
      // Mirror the CLI wiring: resolve cpuOut + the convtranspose param blobs
      // (ctParams) and pass them, else the convtranspose step falls back to its
      // no-params stub and diverges from the golden.
      val suffixToIdx = layers.zipWithIndex.map { case (l, i) =>
        l.suffix -> i
      }.toMap
      val (cpuOut, allocTop, _) =
        MemoryLayout.buildCpuOutAddrs(
          dep,
          layers,
          c.ddrBase,
          suffixToIdx,
          c.comp.toString
        )
      val (ctParams, _, _) =
        MemoryLayout.buildCpuParamAddrs(dep, c.comp.toString, allocTop)
      val tmp = GoldenSupport.sandbox("nn-exec-plan", name) / "nn_exec_plan.h"
      ExecPlan(
        dep,
        layers,
        c.ddrBase,
        c.comp.toString,
        blockSize = cfg.blockSize,
        suffixToIdx = Some(suffixToIdx),
        cpuOut = Some(cpuOut),
        logOutWidth = cfg.logOutWidth,
        ctParams = Some(ctParams)
      ).export(tmp)
      GoldenSupport.assertGolden(c, "nn_exec_plan.h", os.read(tmp))
    }
  }
}
