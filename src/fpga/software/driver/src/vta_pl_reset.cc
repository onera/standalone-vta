#include "../include/vta_pl_reset.h"

extern "C" {
#include "sleep.h"
#include "xgpiops.h"
#include "xparameters.h"
}

namespace vta {

// ZynqMP routes pl_resetn0 to PS GPIO bank 5 EMIO bit 31, which is XGpioPs
// global pin 173 (bank 5 spans pins 142-173).  Writing this pin goes through
// the same DATA_5 register (0xFF0A0054 bit31) that psu_init.tcl pulses for its
// "FABRIC RESET USING EMIO" sequence.  pl_resetn0 is active-low, so driving the
// pin low asserts the fabric reset and driving it high releases it.
static constexpr unsigned kPlResetN0Pin = 173u;

int pl_reset() {
  static XGpioPs gpio;
  static bool ready = false;

  if (!ready) {
    // SDT BSP flow: XGpioPs_LookupConfig takes the controller base address.
    XGpioPs_Config *cfg = XGpioPs_LookupConfig(XPAR_XGPIOPS_0_BASEADDR);
    if (cfg == nullptr)
      return -1;
    if (XGpioPs_CfgInitialize(&gpio, cfg, cfg->BaseAddr) != XST_SUCCESS)
      return -1;
    ready = true;
  }

  // psu_init already configured DIRM_5/OEN_5 bit31 as a driven output; repeat
  // it here so the helper does not depend on that having happened.
  XGpioPs_SetDirectionPin(&gpio, kPlResetN0Pin, 1u);
  XGpioPs_SetOutputEnablePin(&gpio, kPlResetN0Pin, 1u);

  XGpioPs_WritePin(&gpio, kPlResetN0Pin, 0u); // assert  (pl_resetn0 active-low)
  usleep(10);
  XGpioPs_WritePin(&gpio, kPlResetN0Pin, 1u); // release
  usleep(10);
  return 0;
}

} // namespace vta
