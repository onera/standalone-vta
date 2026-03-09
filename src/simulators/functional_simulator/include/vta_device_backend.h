/*!
 * \file vta_device_backend.h
 * \brief Abstract VTA device backend interface.
 *
 * Both the functional software model (FunctionalDevice) and the Verilated
 * RTL model (VerilatedDevice) implement this interface so that the upper-
 * level driver (sim_driver.cc) can select between them at runtime.
 */

#ifndef VTA_DEVICE_BACKEND_H_
#define VTA_DEVICE_BACKEND_H_

#include <cstdint>
#include "./driver.h"

/** Physical addresses of all VTA buffers (set by functional_simulator.cc). */
struct VTABufferAddrs {
  vta_phy_addr_t insn;
  vta_phy_addr_t uop;
  vta_phy_addr_t inp;
  vta_phy_addr_t wgt;
  vta_phy_addr_t acc;
  vta_phy_addr_t out;
};

class VTADeviceBackend {
 public:
  virtual int Run(vta_phy_addr_t insn_phy_addr,
                  uint32_t insn_count,
                  uint32_t wait_cycles) = 0;
  /** Optionally called before Run() to supply all buffer physical addresses. */
  virtual void SetBufferAddresses(const VTABufferAddrs& /*addrs*/) {}
  virtual ~VTADeviceBackend() = default;
};

/** Global flag set by functional_simulator.cc before VTADeviceAlloc(). */
extern bool g_use_verilator;

#ifdef VERILATOR_BUILD_ENABLED
#include <string>
struct VerilatorRunConfig {
    bool        trace_enabled = false;
    std::string trace_file    = "";  // empty → default: "vtashell.fst" or "vtashell.vcd"
    std::string sv_log_file   = "";  // empty → no redirect
};
extern VerilatorRunConfig g_verilator_config;
#endif  // VERILATOR_BUILD_ENABLED

#endif  // VTA_DEVICE_BACKEND_H_
