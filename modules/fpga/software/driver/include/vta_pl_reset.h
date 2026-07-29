#ifndef VTA_PL_RESET_H_
#define VTA_PL_RESET_H_

namespace vta {

// Pulse the PL-only fabric reset (ZynqMP / ZCU104).
//
// On ZynqMP the PS drives pl_resetn[3:0] from PS GPIO bank 5 EMIO bits
// [31:28] (XGpioPs pins [173:170]).  pl_resetn0 = pin 173 = bank5 bit31 - the
// same bit psu_init.tcl's "FABRIC RESET USING EMIO" block toggles
// (DATA_5 @ 0xFF0A0054 bit31).  In the ZCU104 platform pl_resetn0 feeds
// rst_ps8_0_100M (proc_sys_reset), whose peripheral_aresetn resets the whole
// PL, including the VTA.  The PS, DDR contents, and the PS caches are left
// untouched - so this is a PL-only reset, not a system reset.
//
// Only call when the PL is idle (no AXI transaction in flight), e.g. between
// layers in the isolation runner after CTRL_DONE.  A reset clears every VTA VCR
// register; run_layer() reprograms them for each layer, so nothing extra is
// needed afterwards.
//
// Returns 0 on success, -1 if the PS GPIO controller could not be initialised.
int pl_reset();

} // namespace vta

#endif // VTA_PL_RESET_H_
