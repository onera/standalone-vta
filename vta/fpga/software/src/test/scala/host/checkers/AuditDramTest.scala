package fpga.host.checkers

import org.scalatest.flatspec.AnyFlatSpec
import org.scalatest.matchers.should.Matchers
import fpga.host.checkers.AuditDram
import fpga.host.models.GoldenSupport

class AuditDramTest extends AnyFlatSpec with Matchers {

  "audit" should "return 0 (PASS) for the lenet5-default fixture (ddr base 0x0)" in {
    val c = GoldenSupport.loadCase("lenet5-default")
    AuditDram.audit(
      compDir = c.comp.toString,
      ddrBase = c.ddrBase,
      configJson = c.cfg.toString,
      maxAddr = None
    ) shouldBe 0
  }

  it should "return 0 (PASS) for the lenet5-w8b fixture (ddr base 0x10000000)" in {
    val c = GoldenSupport.loadCase("lenet5-w8b")
    AuditDram.audit(
      compDir = c.comp.toString,
      ddrBase = c.ddrBase,
      configJson = c.cfg.toString,
      maxAddr = None
    ) shouldBe 0
  }
}
