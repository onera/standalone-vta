/*!
 * \file verilated_device.cc
 * \brief VTADeviceBackend that drives the Verilated Test top via real DPI.
 *
 * Architecture:
 *   Test.sv (Verilated top)
 *     ├── VTAShell  - the DUT
 *     └── SimShell
 *           ├── VTASim    → VTASimDPI.v   → VTASimDPI()   (dpi_sim.cc)
 *           ├── VTAHost   → VTAHostDPI.v  → VTAHostDPI()  (dpi_host.cc)
 *           │              → VTAHostDPIToAXI.sv  (AXI-Lite master, in SV)
 *           └── VTAMem    → VTAMemDPI.v   → VTAMemDPI()   (dpi_mem.cc)
 *                          → VTAMemDPIToAXI.sv   (AXI4 slave,   in SV)
 *
 * verilated_device.cc only:
 *   1. Enqueues VCR register writes via VTAHostDPI_QueueWrite().
 *   2. Runs the clock loop (both clock + sim_clock together, per
 * tsim_device.cc).
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
#include "dpi/dpi_host.h" // VTAHostDPI_Reset / VTAHostDPI_QueueWrite
#include "dpi/dpi_mem.h"  // VTAMemDPI_Reset
#include "dpi/dpi_sim.h"  // VTASimDPI_Reset

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
#include <fcntl.h>
#include <filesystem>
#include <memory>
#include <system_error>
#include <unistd.h>

// VCR register byte addresses (AXI-Lite, 32-bit registers, 4-byte stride)
static constexpr uint8_t VCR_CTRL = 0x00;  // ctrl: bit[0]=launch, bit[1]=finish
static constexpr uint8_t VCR_VALS0 = 0x08; // vals[0] = instruction count
static constexpr uint8_t VCR_PTR_INSN = 0x0C; // ptrs[0] = insn base address
static constexpr uint8_t VCR_PTR_UOP = 0x10;  // ptrs[1] = uop  base address
static constexpr uint8_t VCR_PTR_INP = 0x14;  // ptrs[2] = inp  base address
static constexpr uint8_t VCR_PTR_WGT = 0x18;  // ptrs[3] = wgt  base address
static constexpr uint8_t VCR_PTR_ACC = 0x1C;  // ptrs[4] = acc  base address
static constexpr uint8_t VCR_PTR_OUT = 0x20;  // ptrs[5] = out  base address

static constexpr uint32_t RESET_CYCLES = 10;

// ---------------------------------------------------------------------------
// $finish override
// ---------------------------------------------------------------------------
// VTASimDPI.v fires $finish when sim_exit=1.  Without this override,
// Verilator would call exit().  We intercept it and set gotFinish() so the
// simulation loop can return cleanly.
// Requires -DVL_USER_FINISH at compile time (see Makefile).
void vl_finish(const char * /*filename*/, int /*linenum*/,
               const char * /*hier*/) {
  Verilated::gotFinish(true);
}

// ---------------------------------------------------------------------------
// VerilatedDevice
// ---------------------------------------------------------------------------
class VerilatedDevice : public VTADeviceBackend {
public:
  VerilatedDevice()
      : top_(std::make_unique<VTest>()), bufAddrs_{}, tfp_(nullptr), cycle_(0),
        sv_log_stderr_backup_(-1), did_first_reset_(false) {

    // --sv-log redirects only the SystemVerilog $display/$fwrite output.
    // firtool emits SV printfs as $fwrite(32'h80000002, ...) which Verilator
    // routes to the C stderr stream (fd 2). Redirecting fd 2 to the log file
    // keeps the console clean (the C++ stdout stream is untouched, so a pipe
    // on the binary still captures only C++ logs).
    if (!g_verilator_config.sv_log_file.empty()) {
      // Ensure parent directory exists (auto-default targets simulators_output/
      // which may not exist yet on a fresh clone).
      auto parent =
          std::filesystem::path(g_verilator_config.sv_log_file).parent_path();
      if (!parent.empty()) {
        std::error_code ec;
        std::filesystem::create_directories(parent, ec);
      }
      std::fflush(stderr);
      sv_log_stderr_backup_ = dup(STDERR_FILENO);
      int log_fd = open(g_verilator_config.sv_log_file.c_str(),
                        O_WRONLY | O_CREAT | O_TRUNC, 0644);
      if (log_fd < 0 ||
          dup2(log_fd, STDERR_FILENO) < 0) {
        // dup() succeeded but the file open or dup2 failed; restore stderr.
        if (sv_log_stderr_backup_ >= 0) {
          dup2(sv_log_stderr_backup_, STDERR_FILENO);
          close(sv_log_stderr_backup_);
          sv_log_stderr_backup_ = -1;
        }
        if (log_fd >= 0)
          close(log_fd);
        fprintf(stderr,
                "[VerilatedDevice] Warning: could not open sv-log '%s'\n",
                g_verilator_config.sv_log_file.c_str());
        // Clear so the final-summary banner in fsim_main doesn't lie about
        // a file that isn't actually being written to.
        g_verilator_config.sv_log_file.clear();
      } else {
        close(log_fd);
        // The "SV log: <path>" banner is printed by fsim_main at the very
        // end of the run, alongside the "Tensor successfully written ..."
        // summary, so the user reads it last instead of scrolling for it.
      }
    }

    if (g_verilator_config.trace_enabled)
      Verilated::traceEverOn(true);
  }

  ~VerilatedDevice() override {
    CloseTrace();
    if (sv_log_stderr_backup_ >= 0) {
      std::fflush(stderr);
      dup2(sv_log_stderr_backup_, STDERR_FILENO);
      close(sv_log_stderr_backup_);
    }
  }

  void SetBufferAddresses(const VTABufferAddrs &addrs) override {
    bufAddrs_ = addrs;
  }

  int Run(vta_phy_addr_t insn_phy_addr, uint32_t insn_count,
          uint32_t /*wait_cycles*/) override {

    // Reset per-run state
    cycle_ = 0;
    VTASimDPI_Reset();
    VTAHostDPI_Reset();
    VTAMemDPI_Reset();

    // Open trace file for this run (read g_verilator_config.trace_file now,
    // so callers can update it per-run before calling Run())
    if (g_verilator_config.trace_enabled) {
      const std::string &path = g_verilator_config.trace_file.empty()
                                    ? DEFAULT_TRACE_FILE
                                    : g_verilator_config.trace_file;
      OpenTrace(path);
    }

    // VCR pointer base: mirror the baremetal driver, which sets all data base
    // pointers (UOP/INP/WGT/ACC/OUT) to ddr_base and lets the RTL add it to the
    // base-0 logical addresses in the instruction/uop streams.  insn_phy_addr is
    // already absolute (shifted by VTAMemGetPhyAddr after ReserveBase), like the
    // baremetal's absolute ptr[0]=insn_addr.  base==0 → unchanged behavior.
    const uint32_t base = static_cast<uint32_t>(VTAGetDramBase());

    // Enqueue VCR register writes (processed by VTAHostDPI() during eval())
    VTAHostDPI_QueueWrite(VCR_VALS0, insn_count);
    VTAHostDPI_QueueWrite(VCR_PTR_INSN, static_cast<uint32_t>(insn_phy_addr));
    VTAHostDPI_QueueWrite(VCR_PTR_UOP, base);
    VTAHostDPI_QueueWrite(VCR_PTR_INP, base);
    VTAHostDPI_QueueWrite(VCR_PTR_WGT, base);
    VTAHostDPI_QueueWrite(VCR_PTR_ACC, base);
    VTAHostDPI_QueueWrite(VCR_PTR_OUT, base);
    VTAHostDPI_QueueWrite(VCR_CTRL, 1u); // launch

    // Reset for RESET_CYCLES (follows tsim_device.cc pattern).
    // With reset_between_layers=false we reset only on the first layer and let
    // subsequent layers re-launch on the live core - reproducing the baremetal
    // run_layer() flow, which never resets the VTA between consecutive launches.
    if (g_verilator_config.reset_between_layers || !did_first_reset_) {
      top_->reset = 1;
      for (uint32_t i = 0; i < RESET_CYCLES; ++i)
        ClockEdge();
      top_->reset = 0;
      did_first_reset_ = true;
    } else {
      // Advance a few cycles so the new VCR launch is observed by the live core.
      for (uint32_t i = 0; i < RESET_CYCLES; ++i)
        ClockEdge();
    }

    // VTASimDPI.v has a $finish block that checks __exit every posedge.
    // __exit=1 can linger from the previous layer's end, and Verilator may
    // schedule the $finish block before the DPI/reset block that clears it,
    // causing a spurious gotFinish() during reset cycles.  Clearing AFTER
    // reset ensures any such spurious trigger is suppressed before the main
    // loop begins.  Reset cycles cannot produce a legitimate finish because
    // VTASimDPI() is gated by (reset|__reset) and g_sim_exit=0.
    Verilated::gotFinish(false);

    // Main simulation loop (timeout_cycles==0 means run until finish)
    const bool unlimited = (g_verilator_config.timeout_cycles == 0);
    for (uint32_t c = 0; unlimited || c < g_verilator_config.timeout_cycles;
         ++c) {
      ClockEdge();

      if (Verilated::gotFinish()) {
        CloseTrace();
        printf("[VerilatedDevice] ecnt (total cycles)   = %u\n",
               VTAHostDPI_GetECnt());
        printf("[VerilatedDevice] ucnt (compute cycles) = %u\n",
               VTAHostDPI_GetUCnt());
        return 0;
      }

      // sim_wait: VTASim requests host to pause the main clock.
      // Tick only sim_clock while holding clock=0 (follows tsim_device.cc).
      while (top_->sim_wait) {
        top_->clock = 0;
        top_->sim_clock = 0;
        top_->eval();
        top_->sim_clock = 1;
        top_->eval();
        ++cycle_;
        if (Verilated::gotFinish()) {
          CloseTrace();
          printf("[VerilatedDevice] ecnt (total cycles)   = %u\n",
                 VTAHostDPI_GetECnt());
          printf("[VerilatedDevice] ucnt (compute cycles) = %u\n",
                 VTAHostDPI_GetUCnt());
          return 0;
        }
      }
    }

    CloseTrace();
    printf("[VerilatedDevice] Timeout after %u cycles.\n",
           g_verilator_config.timeout_cycles);
    return 1;
  }

private:
  void OpenTrace(const std::string &path) {
    CloseTrace();
    // Ensure output directory exists
    auto parent = std::filesystem::path(path).parent_path();
    if (!parent.empty())
      std::filesystem::create_directories(parent);
    tfp_ = new TraceType();
    top_->trace(tfp_, 99);
    tfp_->open(path.c_str());
    printf("[VerilatedDevice] Trace: %s\n", path.c_str());
  }

  void CloseTrace() {
    if (tfp_) {
      tfp_->close();
      delete tfp_;
      tfp_ = nullptr;
    }
  }

  /**
   * One clock cycle: both clock and sim_clock rise and fall together.
   * Matches tsim_device.cc's clock scheme.
   */
  void ClockEdge() {
    top_->sim_clock = 0;
    top_->clock = 0;
    top_->eval();
    if (tfp_)
      tfp_->dump(static_cast<vluint64_t>(2 * cycle_));

    top_->sim_clock = 1;
    top_->clock = 1;
    top_->eval();
    if (tfp_)
      tfp_->dump(static_cast<vluint64_t>(2 * cycle_ + 1));

    ++cycle_;
  }

  std::unique_ptr<VTest> top_;
  VTABufferAddrs bufAddrs_;
  TraceType *tfp_;
  uint64_t cycle_;
  int sv_log_stderr_backup_;
  bool did_first_reset_;
};

VTADeviceBackend *CreateVerilatedDevice() { return new VerilatedDevice(); }

#endif // VERILATOR_BUILD_ENABLED
