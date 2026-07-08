package fpga.host.models

import org.scalatest.flatspec.AnyFlatSpec
import org.scalatest.matchers.should.Matchers
import vta.parsers.CompilerOutputParser
import fpga.host.transform.MemoryLayout
import fpga.host.parsers.LayerParser

class LayoutTest extends AnyFlatSpec with Matchers {
  private val c = GoldenSupport.loadCase("lenet5-default")
  private val layers = LayerParser.collectLayers(
    c.comp.toString,
    CompilerOutputParser.loadDependencyInfo(
      (c.comp / "dependency.csv").toString
    )
  )

  "scratchAddr" should "be page-aligned and above every VTA region" in {
    val s = MemoryLayout.scratchAddr(layers, c.ddrBase)
    (s % 0x1000L) shouldBe 0L
    layers.flatMap(_.mem.values).foreach { r =>
      s should be >= (c.ddrBase + r.offset + r.byteSize)
    }
  }
}
