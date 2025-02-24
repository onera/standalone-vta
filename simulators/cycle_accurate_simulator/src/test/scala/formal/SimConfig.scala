package formal

import vta.core.{CoreKey, CoreParams}
import vta.interface.axi.AXIParams
import vta.shell.{ShellKey, ShellParams, VCRParams, VMEParams}
import vta.util.config.Config

/**
 * VTA HARDWARE CONFIGURATION
 */
class SimConfig {
  // Hard-define the VTA parameters
  val config = new Config((site, here, up) => {
    // Default configuration //TODO: confirm configuration
    case CoreKey => CoreParams(
      batch = 1,
      blockOut = 16,
      blockOutFactor = 1,
      blockIn = 16,
      inpBits = 8,
      wgtBits = 8,
      uopBits = 32,
      accBits = 32,
      outBits = 8,
      uopMemDepth = 2048,
      inpMemDepth = 2048,
      wgtMemDepth = 1024,
      accMemDepth = 2048,
      outMemDepth = 2048,
      instQueueEntries = 512
    )
    // Copy of PynqConfig in vta.shell.Configs.PynqConfig
    case ShellKey =>
      ShellParams(
        hostParams = AXIParams(coherent = false,
          addrBits = 16,
          dataBits = 32,
          lenBits = 8,
          userBits = 1),
        memParams = AXIParams(coherent = true,
          addrBits = 32,
          dataBits = 64,
          lenBits = 8,
          userBits = 1),
        vcrParams = VCRParams(),
        vmeParams = VMEParams()
      )
  })
  //implicit val p: Parameters = config
}