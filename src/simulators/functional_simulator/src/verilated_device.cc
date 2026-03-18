/*!
 * \file verilated_device.cc
 * \brief VTADeviceBackend implementation that drives Verilated VTAShell RTL.
 *
 * Only compiled when VERILATOR_BUILD_ENABLED is defined (make verilated
 * target). Requires Verilator >= 5.x and a generated VVTAShell.h /
 * libVVTAShell.a.
 *
 * VCR register map (32-bit regs, 4-byte stride, PynqConfig / 32-bit ptrs):
 *   0x00 : ctrl  – bit[0]=launch (write 1), bit[1]=finish (read)
 *   0x04 : ecnt[0]
 *   0x08 : vals[0] = instruction count
 *   0x0C : ptrs[0] = insn_baddr
 *   0x10 : ptrs[1] = uop_baddr
 *   0x14 : ptrs[2] = inp_baddr
 *   0x18 : ptrs[3] = wgt_baddr
 *   0x1C : ptrs[4] = acc_baddr
 *   0x20 : ptrs[5] = out_baddr
 */

#ifdef VERILATOR_BUILD_ENABLED

#include "../include/virtual_memory.h"
#include "../include/vta_device_backend.h"
#include "dpi/dpi_host.h"
#include "dpi/dpi_mem.h"
#include "dpi/dpi_sim.h"

// Verilator-generated header — produced by `make verilated` after
// `verilator --cc VTAShell.sv ...`
#include "VVTAShell.h"
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

using DRAM = vta::vmem::VirtualMemoryManager;

// VCR register offsets (byte addresses)
static constexpr uint16_t VCR_CTRL = 0x00;
static constexpr uint16_t VCR_ECNT0 = 0x04;
static constexpr uint16_t VCR_VALS0 = 0x08;    // instruction count
static constexpr uint16_t VCR_PTR_INSN = 0x0C; // ptrs[0]
static constexpr uint16_t VCR_PTR_UOP = 0x10;  // ptrs[1]
static constexpr uint16_t VCR_PTR_INP = 0x14;  // ptrs[2]
static constexpr uint16_t VCR_PTR_WGT = 0x18;  // ptrs[3]
static constexpr uint16_t VCR_PTR_ACC = 0x1C;  // ptrs[4]
static constexpr uint16_t VCR_PTR_OUT = 0x20;  // ptrs[5]

static constexpr uint32_t RESET_CYCLES = 10;

class VerilatedDevice : public VTADeviceBackend {
public:
  VerilatedDevice()
      : dut_(std::make_unique<VVTAShell>()), bufAddrs_{}, tfp_(nullptr),
        cycle_(0), sv_log_stdout_backup_(-1) {
    // Redirect SV $display (stdout) before tracing setup so any init
    // $display messages are also captured.
    if (!g_verilator_config.sv_log_file.empty()) {
      sv_log_stdout_backup_ = dup(STDOUT_FILENO);
      if (freopen(g_verilator_config.sv_log_file.c_str(), "w", stdout) ==
          nullptr) {
        fprintf(stderr,
                "[VerilatedDevice] Warning: could not open sv-log '%s'\n",
                g_verilator_config.sv_log_file.c_str());
        sv_log_stdout_backup_ = -1;
      }
    }

    if (g_verilator_config.trace_enabled) {
      Verilated::traceEverOn(true);
      tfp_ = new TraceType();
      dut_->trace(tfp_, 99);
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
    // Restore stdout if we redirected it
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
    VTASimDPI_Reset();

    // -----------------------------------------------------------------------
    // 1. Reset
    // -----------------------------------------------------------------------
    dut_->reset = 1;
    for (uint32_t i = 0; i < RESET_CYCLES; ++i) {
      ClockEdge();
    }
    dut_->reset = 0;

    // -----------------------------------------------------------------------
    // 2. Enqueue VCR register writes via dpi_host
    // -----------------------------------------------------------------------
    // Use physical addresses supplied by SetBufferAddresses() (called by
    // functional_simulator.cc before Run()).  The VTA hardware adds the
    // per-buffer base address (VCR ptr) to each instruction's dram_offset
    // field to form the absolute DRAM address.
    host_.Write(VCR_VALS0, insn_count);
    host_.Write(VCR_PTR_INSN, static_cast<uint32_t>(insn_phy_addr));
    host_.Write(VCR_PTR_UOP, 0u);
    host_.Write(VCR_PTR_INP, 0u);
    host_.Write(VCR_PTR_WGT, 0u);
    host_.Write(VCR_PTR_ACC, 0u);
    host_.Write(VCR_PTR_OUT, 0u);

    // -----------------------------------------------------------------------
    // 3. Drain the write queue (clock cycles until host SM is idle)
    // -----------------------------------------------------------------------
    for (uint32_t c = 0; c < g_verilator_config.timeout_cycles && !host_.Idle();
         ++c) {
      ClockEdge();
    }
    if (!host_.Idle()) {
      fprintf(stderr, "[VerilatedDevice] Timeout writing VCR registers.\n");
      return 1;
    }

    // -----------------------------------------------------------------------
    // 4. Launch: write 1 to ctrl register
    // -----------------------------------------------------------------------
    host_.Write(VCR_CTRL, 1);
    while (!host_.Idle()) {
      ClockEdge();
    }

    // -----------------------------------------------------------------------
    // 5. Clock loop — run until finish or timeout
    // -----------------------------------------------------------------------
    for (uint32_t cycle = 0; cycle < g_verilator_config.timeout_cycles;
         ++cycle) {
      ClockEdge();

      // Poll ctrl register for finish bit
      if (!host_.Idle())
        continue; // still processing a transaction

      // Enqueue a read of the ctrl register every ~16 cycles
      if (cycle % 16 == 0) {
        host_.Read(VCR_CTRL);
        // run one more cycle to start the read
        ClockEdge();
        while (!host_.Idle()) {
          ClockEdge();
        }
        uint32_t ctrl = host_.LastReadValue();
        if (ctrl & 0x2u) {
          // Finish bit set
          VTASimDPI_SetExit();
          return 0;
        }
      }
    }

    // Debug: print last ctrl register value
    host_.Read(VCR_CTRL);
    ClockEdge();
    while (!host_.Idle())
      ClockEdge();
    fprintf(stderr,
            "[VerilatedDevice] Timeout waiting for finish (ctrl=0x%08X).\n",
            host_.LastReadValue());
    VTASimDPI_SetExit();
    return 1;
  }

private:
  /** One clock cycle:
   *  1. Rising edge eval  — DUT captures inputs that were stable since last
   * call
   *  2. Sample DUT outputs, advance state machines, drive new inputs
   *  3. Falling edge eval — propagate combinatorial logic with new inputs
   *
   *  This ensures inputs are stable before posedge captures them, so AXI
   *  handshake signals are seen correctly by the DUT.
   */
  void ClockEdge() {
    // --- Rising edge: DUT captures inputs from previous cycle ---
    dut_->clock = 1;
    dut_->eval();
    if (tfp_)
      tfp_->dump(2 * cycle_ + 1);

    // --- Sample outputs, advance state machines, drive new inputs ---
    DriveMemSlave();
    DriveHostMaster();

    // --- Falling edge: propagate combinatorial with new inputs ---
    dut_->clock = 0;
    dut_->eval();
    if (tfp_)
      tfp_->dump(2 * cycle_ + 2);

    ++cycle_;
  }

  /** Drive the AXI-Lite host signals (we are master). */
  void DriveHostMaster() {
    uint8_t aw_valid, w_valid, b_ready, ar_valid, r_ready;
    uint16_t aw_addr, ar_addr;
    uint32_t w_data;

    host_.Tick(aw_valid, aw_addr, w_valid, w_data, b_ready, ar_valid, ar_addr,
               r_ready,
               // sample VTAShell outputs
               static_cast<uint8_t>(dut_->io_host_aw_ready),
               static_cast<uint8_t>(dut_->io_host_w_ready),
               static_cast<uint8_t>(dut_->io_host_b_valid),
               static_cast<uint8_t>(dut_->io_host_ar_ready),
               static_cast<uint8_t>(dut_->io_host_r_valid),
               static_cast<uint32_t>(dut_->io_host_r_bits_data));

    dut_->io_host_aw_valid = aw_valid;
    dut_->io_host_aw_bits_addr = aw_addr;
    dut_->io_host_w_valid = w_valid;
    dut_->io_host_w_bits_data = w_data;
    dut_->io_host_b_ready = b_ready;
    dut_->io_host_ar_valid = ar_valid;
    dut_->io_host_ar_bits_addr = ar_addr;
    dut_->io_host_r_ready = r_ready;
  }

  /** Drive the AXI memory signals (we are slave). */
  void DriveMemSlave() {
    uint8_t ar_ready, r_valid, r_last, r_id;
    uint64_t r_data;
    uint8_t aw_ready, w_ready, b_valid;

    mem_.Tick(
        // read address (VTAShell drives)
        static_cast<uint8_t>(dut_->io_mem_ar_valid),
        static_cast<uint32_t>(dut_->io_mem_ar_bits_addr),
        static_cast<uint8_t>(dut_->io_mem_ar_bits_len),
        static_cast<uint8_t>(dut_->io_mem_ar_bits_id), ar_ready,
        // read data (we drive)
        r_valid, r_data, r_last, r_id,
        static_cast<uint8_t>(dut_->io_mem_r_ready),
        // write address (VTAShell drives)
        static_cast<uint8_t>(dut_->io_mem_aw_valid),
        static_cast<uint32_t>(dut_->io_mem_aw_bits_addr),
        static_cast<uint8_t>(dut_->io_mem_aw_bits_len), aw_ready,
        // write data
        static_cast<uint8_t>(dut_->io_mem_w_valid),
        static_cast<uint64_t>(dut_->io_mem_w_bits_data),
        static_cast<uint8_t>(dut_->io_mem_w_bits_last), w_ready,
        // write response
        b_valid, static_cast<uint8_t>(dut_->io_mem_b_ready));

    dut_->io_mem_ar_ready = ar_ready;
    dut_->io_mem_r_valid = r_valid;
    dut_->io_mem_r_bits_data = r_data;
    dut_->io_mem_r_bits_last = r_last;
    dut_->io_mem_r_bits_id = r_id;
    dut_->io_mem_aw_ready = aw_ready;
    dut_->io_mem_w_ready = w_ready;
    dut_->io_mem_b_valid = b_valid;

    // Debug: sample AR/AW valid signals periodically
    if (cycle_ % 50000 == 0) {
      fprintf(stderr,
              "[DriveMemSlave] cycle=%lu  ar_valid=%u ar_addr=0x%08X  "
              "aw_valid=%u aw_addr=0x%08X\n",
              (unsigned long)cycle_,
              (unsigned)dut_->io_mem_ar_valid,
              (unsigned)dut_->io_mem_ar_bits_addr,
              (unsigned)dut_->io_mem_aw_valid,
              (unsigned)dut_->io_mem_aw_bits_addr);
    }
  }

  std::unique_ptr<VVTAShell> dut_;
  DPIHost host_;
  DPIMem mem_;
  VTABufferAddrs bufAddrs_;
  TraceType *tfp_;
  uint64_t cycle_;
  int sv_log_stdout_backup_;
};

VTADeviceBackend *CreateVerilatedDevice() { return new VerilatedDevice(); }

#endif // VERILATOR_BUILD_ENABLED
