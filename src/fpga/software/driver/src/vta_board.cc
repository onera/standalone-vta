#include "vta_board.h"
extern "C" {
#include "xparameters.h"
}

// XUartPs is the Cadence UART of Zynq-7000 / Zynq UltraScale+. Versal drives
// its PS UART through the PL011-based XUartPsv driver and its BSP ships no
// xuartps.h, so gate the include as well as the body on the controller being
// present in the generated xparameters.h. Where it is absent the BSP-configured
// baud rate stands and board_init() is a no-op.
#if defined(XPAR_XUARTPS_0_BASEADDR) && !defined(versal) && !defined(VERSAL_NET)
#define VTA_HAS_XUARTPS 1
#endif

#ifdef VTA_HAS_XUARTPS
extern "C" {
#include "xuartps.h"
}
#endif

namespace vta {

void board_init(std::uint32_t baud) {
#ifdef VTA_HAS_XUARTPS
  XUartPs inst;
  XUartPs_Config *cfg = XUartPs_LookupConfig(XPAR_XUARTPS_0_BASEADDR);
  XUartPs_CfgInitialize(&inst, cfg, cfg->BaseAddress);
  XUartPs_SetBaudRate(&inst, baud);
#else
  (void)baud;
#endif
}

} // namespace vta
