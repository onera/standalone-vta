package fpga.host.models

import org.scalatest.flatspec.AnyFlatSpec
import org.scalatest.matchers.should.Matchers
import fpga.host.parsers.ConfigParser
import fpga.host.exporters.all._

class HwConfigTest extends AnyFlatSpec with Matchers {
  for (name <- GoldenSupport.cases) {
    s"ConfigParams emit [$name]" should "match the golden vta_hw_config.h" in {
      val c = GoldenSupport.loadCase(name)
      val cfg = ConfigParser.load(c.cfg.toString)
      val tmp = GoldenSupport.sandbox("hw-config", name) / "vta_hw_config.h"
      cfg.export(tmp)
      os.read(tmp) shouldBe os.read(c.gen / "vta_hw_config.h")
    }
  }
}
