/*!
 * \file verilated_device.cc
 * \brief VTADeviceBackend that drives the Verilated Test top via real DPI.
 *
 * Architecture:
 *   Test.sv (Verilated top)
 *     ├── VTAShell  — the DUT
 *     └── SimShell
 *           ├── VTASim    → VTASimDPI.v   → VTASimDPI()   (dpi_sim.cc)
 *           ├── VTAHost   → VTAHostDPI.v  → VTAHostDPI()  (dpi_host.cc)
 *           │              → VTAHostDPIToAXI.sv  (AXI-Lite master, in SV)
 *           └── VTAMem    → VTAMemDPI.v   → VTAMemDPI()   (dpi_mem.cc)
 *                          → VTAMemDPIToAXI.sv   (AXI4 slave,   in SV)
 *
 * verilated_device.cc only:
 *   1. Enqueues VCR register writes via VTAHostDPI_QueueWrite().
 *   2. Runs the clock loop (both clock + sim_clock together, per tsim_device.cc).
 *   3. Detects completion via Verilated::gotFinish() set by vl_finish().
 *
 * All AXI protocol handling is in SV.  The three DPI-C functions
 * (VTAHostDPI, VTAMemDPI, VTASimDPI) are called automatically by the
 * Verilated model during eval().
 *
 * Compile with -DVL_USER_FINISH so that VTASimDPI.v's $finish is intercepted
 * by vl_finish() below rather than exiting the process.
 */

#ifdef VERILATOR_BUILD_ENABLED

#include "../include/vta_device_backend.h"
#include "dpi/dpi_host.h"   // VTAHostDPI_Reset / VTAHostDPI_QueueWrite
#include "dpi/dpi_mem.h"    // VTAMemDPI_Reset
#include "dpi/dpi_sim.h"    // VTASimDPI_Reset

// Verilator-generated header produced by `make verilate_vtashell`
// (--top-module Test generates VTest.h)
#include "VTest.h"
#include "verilated.h"

#ifdef TRACE_FORMAT_VCD
#include "verilated_vcd_c.h"
using TraceType = VerilatedVcdC;
static constexpr const char *DEFAULT_TRACE_FILE = "vtashell.vcd";
#else
#include "verilated_fst_c.h"
using TraceType = VerilatedFstC;
static constexpr const char *DEFAULT_TRACE_FILE = "vtashell.fst";
#endif

#include <cstdint>
#include <cstdio>
#include <memory>
#include <unistd.h>

// VCR register byte addresses (AXI-Lite, 32-bit registers, 4-byte stride)
static constexpr uint8_t VCR_CTRL     = 0x00;  // ctrl: bit[0]=launch, bit[1]=finish
static constexpr uint8_t VCR_VALS0    = 0x08;  // vals[0] = instruction count
static constexpr uint8_t VCR_PTR_INSN = 0x0C;  // ptrs[0] = insn base address
static constexpr uint8_t VCR_PTR_UOP  = 0x10;  // ptrs[1] = uop  base address
static constexpr uint8_t VCR_PTR_INP  = 0x14;  // ptrs[2] = inp  base address
static constexpr uint8_t VCR_PTR_WGT  = 0x18;  // ptrs[3] = wgt  base address
static constexpr uint8_t VCR_PTR_ACC  = 0x1C;  // ptrs[4] = acc  base address
static constexpr uint8_t VCR_PTR_OUT  = 0x20;  // ptrs[5] = out  base address

static constexpr uint32_t RESET_CYCLES = 10;

// ---------------------------------------------------------------------------
// $finish override
// ---------------------------------------------------------------------------
// VTASimDPI.v fires $finish when sim_exit=1.  Without this override,
// Verilator would call exit().  We intercept it and set gotFinish() so the
// simulation loop can return cleanly.
// Requires -DVL_USER_FINISH at compile time (see Makefile).
void vl_finish(const char * /*filename*/, int /*linenum*/, const char * /*hier*/) {
  Verilated::gotFinish(true);
}

// ---------------------------------------------------------------------------
// VerilatedDevice
// ---------------------------------------------------------------------------
class VerilatedDevice : public VTADeviceBackend {
 public:
  VerilatedDevice()
      : top_(std::make_unique<VTest>()), bufAddrs_{},
        tfp_(nullptr), cycle_(0), sv_log_stdout_backup_(-1) {

    if (!g_verilator_config.sv_log_file.empty()) {
      sv_log_stdout_backup_ = dup(STDOUT_FILENO);
      if (freopen(g_verilator_config.sv_log_file.c_str(), "w", stdout) == nullptr) {
        fprintf(stderr, "[VerilatedDevice] Warning: could not open sv-log '%s'\n",
                g_verilator_config.sv_log_file.c_str());
        sv_log_stdout_backup_ = -1;
      }
    }

    if (g_verilator_config.trace_enabled) {
      Verilated::traceEverOn(true);
      tfp_ = new TraceType();
      top_->trace(tfp_, 99);
      const std::string &path = g_verilator_config.trace_file.empty()
                                    ? DEFAULT_TRACE_FILE
                                    : g_verilator_config.trace_file;
      tfp_->open(path.c_str());
      fprintf(stderr, "[VerilatedDevice] Trace: %s\n", path.c_str());
    }
    if (sv_log_stdout_backup_ >= 0)
      fprintf(stderr, "[VerilatedDevice] SV log: %s\n",
              g_verilator_config.sv_log_file.c_str());
  }

  ~VerilatedDevice() override {
    if (tfp_) {
      tfp_->close();
      delete tfp_;
    }
    if (sv_log_stdout_backup_ >= 0) {
      fflush(stdout);
      dup2(sv_log_stdout_backup_, STDOUT_FILENO);
      close(sv_log_stdout_backup_);
    }
  }

  void SetBufferAddresses(const VTABufferAddrs &addrs) override {
    bufAddrs_ = addrs;
  }

  int Run(vta_phy_addr_t insn_phy_addr, uint32_t insn_count,
          uint32_t /*wait_cycles*/) override {

    // Reset DPI state
    VTASimDPI_Reset();
    VTAHostDPI_Reset();
    VTAMemDPI_Reset();
    Verilated::gotFinish(false);

    // Enqueue VCR register writes (processed by VTAHostDPI() during eval())
    VTAHostDPI_QueueWrite(VCR_VALS0,    insn_count);
    VTAHostDPI_QueueWrite(VCR_PTR_INSN, static_cast<uint32_t>(insn_phy_addr));
    VTAHostDPI_QueueWrite(VCR_PTR_UOP,  0u);
    VTAHostDPI_QueueWrite(VCR_PTR_INP,  0u);
    VTAHostDPI_QueueWrite(VCR_PTR_WGT,  0u);
    VTAHostDPI_QueueWrite(VCR_PTR_ACC,  0u);
    VTAHostDPI_QueueWrite(VCR_PTR_OUT,  0u);
    VTAHostDPI_QueueWrite(VCR_CTRL,     1u);  // launch

    // Reset for RESET_CYCLES (follows tsim_device.cc pattern)
    top_->reset = 1;
    for (uint32_t i = 0; i < RESET_CYCLES; ++i)
      ClockEdge();
    top_->reset = 0;

    // Main simulation loop
    for (uint32_t c = 0; c < g_verilator_config.timeout_cycles; ++c) {
      ClockEdge();

      if (Verilated::gotFinish())
        return 0;

      // sim_wait: VTASim requests host to pause the main clock.
      // Tick only sim_clock while holding clock=0 (follows tsim_device.cc).
      while (top_->sim_wait) {
        top_->clock     = 0;
        top_->sim_clock = 0; top_->eval();
        top_->sim_clock = 1; top_->eval();
        ++cycle_;
        if (Verilated::gotFinish())
          return 0;
      }
    }

    fprintf(stderr, "[VerilatedDevice] Timeout after %u cycles.\n",
            g_verilator_config.timeout_cycles);
    return 1;
  }

 private:
  /**
   * One clock cycle: both clock and sim_clock rise and fall together.
   * Matches tsim_device.cc's clock scheme.
   */
  void ClockEdge() {
    top_->sim_clock = 0;
    top_->clock     = 0;
    top_->eval();
    if (tfp_) tfp_->dump(static_cast<vluint64_t>(2 * cycle_));

    top_->sim_clock = 1;
    top_->clock     = 1;
    top_->eval();
    if (tfp_) tfp_->dump(static_cast<vluint64_t>(2 * cycle_ + 1));

    ++cycle_;
  }

  std::unique_ptr<VTest> top_;
  VTABufferAddrs         bufAddrs_;
  TraceType             *tfp_;
  uint64_t               cycle_;
  int                    sv_log_stdout_backup_;
};

VTADeviceBackend *CreateVerilatedDevice() { return new VerilatedDevice(); }

#endif  // VERILATOR_BUILD_ENABLED
