#include "vta_board.h"
extern "C" {
#include "xparameters.h"
#include "xuartps.h"
}

namespace vta {

void board_init(std::uint32_t baud) {
  XUartPs inst;
  XUartPs_Config *cfg = XUartPs_LookupConfig(XPAR_XUARTPS_0_BASEADDR);
  XUartPs_CfgInitialize(&inst, cfg, cfg->BaseAddress);
  XUartPs_SetBaudRate(&inst, baud);
}

} // namespace vta
