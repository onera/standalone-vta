package fpga.host.transform

import vta.core.CoreKey
import vta.util.config.Parameters
import fpga.host.models.HwConfig.ConfigParams

/** Derives the host [[ConfigParams]] from the Chisel core parameters. Kept out
  * of `fpga.host.models` so that package stays free of any Chisel dependency.
  */
object HwConfigResolver {

  /** Derive the host config from the Chisel core parameters (the single config
    * source, set via `-Dvta.config.file`). `CoreConfig` stores each value as
    * `2^LOG_*` (block size and bit widths), so block size is taken directly and
    * the log widths are recovered with log2. This is what the CLI uses instead
    * of a `--config-json` argument, keeping it consistent with the SV emitters.
    */
  def fromParameters(p: Parameters): ConfigParams = {
    val c = p(CoreKey)
    def log2(n: Int): Int = 31 - Integer.numberOfLeadingZeros(n)
    ConfigParams(
      blockSize = c.blockIn,
      logInpWidth = log2(c.inpBits),
      logOutWidth = log2(c.outBits),
      logWgtWidth = log2(c.wgtBits),
      logAccWidth = log2(c.accBits),
      target = Some(c.target)
    )
  }
}
