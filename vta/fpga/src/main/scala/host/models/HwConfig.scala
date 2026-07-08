package fpga.host.models

/** Hardware config data model and width-derived C-type helpers.
  *
  * This object is pure data: it holds the [[ConfigParams]] model (the
  * `Emittable` target rendered into `vta_hw_config.h`) and the width helpers
  * shared by the emitters. Deriving a `ConfigParams` from the Chisel core
  * parameters lives in [[fpga.host.transform.HwConfigResolver]]; config-JSON
  * parsing in [[fpga.host.parsers.ConfigParser]]; config/network compatibility
  * validation in [[fpga.host.checkers.Checks.checkConfigCompat]].
  */
object HwConfig {

  case class ConfigParams(
    blockSize: Int,
    logInpWidth: Int,
    logOutWidth: Int,
    logWgtWidth: Int,
    logAccWidth: Int,
    target: Option[String]
  )

  def ctypeFromLogWidth(logWidth: Int): String = {
    val bits = 1 << logWidth
    bits match {
      case 8  => "std::int8_t"
      case 16 => "std::int16_t"
      case 32 => "std::int32_t"
      case _  => s"/* unsupported ${bits}-bit */"
    }
  }

  def elemBytes(logWidth: Int): Int = (1 << logWidth) / 8
}
