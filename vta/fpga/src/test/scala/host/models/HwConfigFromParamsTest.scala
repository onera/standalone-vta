package fpga.host

import org.scalatest.flatspec.AnyFlatSpec
import org.scalatest.matchers.should.Matchers
import vta.core.CoreConfigFromValues
import fpga.host.transform.HwConfigResolver
import vta.parsers.ConfigParser.parseConfigJsonAt
import vta.parsers.ConfigParser
import vta.configs.DefaultPynqConfig

/** `HwConfig.fromParameters` must reproduce the active Chisel config. The
  * `fpga.test` JVM runs with the default `vta_config.json` (32-bit out), so
  * this test pins the block-16 / 8-bit `vta_config_test.json` explicitly via a
  * [[CoreConfigFromValues]] override rather than relying on
  * `-Dvta.config.file`.
  */
class HwConfigFromParamsTest extends AnyFlatSpec with Matchers {
  // Walk up to the cycle-accurate-sim root that owns the shared test config.
  private def simRoot: os.Path = {
    var d = os.pwd
    while (
      !os.exists(
        d / "vta" / "hardware" / "src" / "test" / "resources" / "vta_config_test.json"
      ) &&
      d != (d / os.up)
    ) d = d / os.up
    d
  }

  "HwConfigResolver.fromParameters" should "derive the config from an explicit config" in {
    val cfgPath =
      (simRoot / "vta" / "hardware" / "src" / "test" / "resources" / "vta_config_test.json").toString
    val raw = parseConfigJsonAt(cfgPath).get
    val values = ConfigParser.getConfigParametersFromMap(raw)
    val core = new CoreConfigFromValues(values, raw("TARGET"))

    val cfg = HwConfigResolver.fromParameters(new DefaultPynqConfig(core))
    cfg.blockSize shouldBe 16
    cfg.logInpWidth shouldBe 3
    cfg.logOutWidth shouldBe 3
    cfg.logWgtWidth shouldBe 3
    cfg.logAccWidth shouldBe 5
    cfg.target shouldBe Some("sim")
  }
}
