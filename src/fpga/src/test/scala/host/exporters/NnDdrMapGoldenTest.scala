package fpga.host.exporters

import org.scalatest.flatspec.AnyFlatSpec
import vta.parsers.CompilerOutputParser
import fpga.host.models._
import fpga.host.parsers.LayerParser
import fpga.host.exporters.all._

class NnDdrMapGoldenTest extends AnyFlatSpec {
  for (name <- GoldenSupport.cases) {
    s"DdrMap [$name]" should "match golden nn_ddr_map.h" in {
      val c = GoldenSupport.loadCase(name)
      val layers = LayerParser.collectLayers(
        c.comp.toString,
        CompilerOutputParser.loadDependencyInfo(
          (c.comp / "dependency.csv").toString
        )
      )
      val tmp = os.pwd / "nn_ddr_map.h"
      DdrMap(layers, c.ddrBase).export(tmp)
      GoldenSupport.assertGolden(c, "nn_ddr_map.h", os.read(tmp))
    }
  }
}
