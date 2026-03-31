/*!
 * \file dpi_host.cc
 * \brief VTAHostDPI DPI-C implementation.
 *
 * Implements the DPI-C function imported by VTAHostDPI.v.  The SV side
 * (VTAHostDPIToAXI.sv) translates the DPI request/response protocol into
 * AXI-Lite transactions to VTAShell's VCR port — no AXI logic is needed here.
 *
 * Transaction model:
 *   - verilated_device.cc calls VTAHostDPI_QueueWrite() to pre-load VCR writes.
 *   - Once the launch write (ctrl=1) is dequeued, this function auto-inserts a
 *     VCR_CTRL read every POLL_PERIOD cycles.
 *   - When the finish bit (bit 1) appears in a ctrl read response, it calls
 *     VTASimDPI_SetExit(), triggering $finish via VTASimDPI.v.
 */

#include "dpi_host.h"
#include "dpi_sim.h"

#include <svdpi.h>
#include <deque>
#include <cstdio>

static constexpr uint8_t  VCR_CTRL_ADDR = 0x00;
static constexpr uint32_t POLL_PERIOD   = 16;

struct HostTxn {
  bool     is_write;
  uint8_t  addr;
  uint32_t value;
};

static std::deque<HostTxn> s_queue;
static bool     s_pending       = false;
static bool     s_awaiting_resp = false;
static HostTxn  s_current       = {};
static bool     s_launched      = false;
static uint32_t s_poll_counter  = 0;

void VTAHostDPI_Reset() {
  s_queue.clear();
  s_pending       = false;
  s_awaiting_resp = false;
  s_current       = {};
  s_launched      = false;
  s_poll_counter  = 0;
}

void VTAHostDPI_QueueWrite(uint8_t addr, uint32_t value) {
  s_queue.push_back({true, addr, value});
}

// DPI-C function called by VTAHostDPI.v on every rising clock edge.
extern "C" void VTAHostDPI(
    dpi8_t  *req_valid,  dpi8_t  *req_opcode,
    dpi8_t  *req_addr,   dpi32_t *req_value,
    dpi8_t   req_deq,
    dpi8_t   resp_valid, dpi32_t  resp_value)
{
  *req_valid = 0; *req_opcode = 0; *req_addr = 0; *req_value = 0;

  // -----------------------------------------------------------------------
  // 1. Handle pending read response
  // -----------------------------------------------------------------------
  if (s_awaiting_resp) {
    if (resp_valid) {
      if (resp_value & 0x2u) {  // finish bit set in ctrl register
        VTASimDPI_SetExit();
      }
      s_awaiting_resp = false;
      s_pending       = false;
    }
    // Cannot issue a new request until response arrives
    return;
  }

  // -----------------------------------------------------------------------
  // 2. Handle request acknowledgement (address channel accepted by SV)
  // -----------------------------------------------------------------------
  if (s_pending && req_deq) {
    if (s_current.is_write) {
      // Track when the launch write completes
      if (s_current.addr == VCR_CTRL_ADDR && s_current.value == 1u)
        s_launched = true;
      s_pending = false;
    } else {
      // Read address accepted — wait for read data response
      s_awaiting_resp = true;
      return;
    }
  }

  // -----------------------------------------------------------------------
  // 3. Auto-poll VCR_CTRL after launch when the explicit queue is drained
  // -----------------------------------------------------------------------
  if (s_launched && !s_pending && s_queue.empty()) {
    ++s_poll_counter;
    if (s_poll_counter >= POLL_PERIOD) {
      s_poll_counter = 0;
      s_queue.push_back({false, VCR_CTRL_ADDR, 0u});
    }
  }

  // -----------------------------------------------------------------------
  // 4. Load next transaction if idle
  // -----------------------------------------------------------------------
  if (!s_pending && !s_queue.empty()) {
    s_current = s_queue.front();
    s_queue.pop_front();
    s_pending = true;
  }

  // -----------------------------------------------------------------------
  // 5. Present current request to SV
  // -----------------------------------------------------------------------
  if (s_pending) {
    *req_valid  = 1;
    *req_opcode = s_current.is_write ? 1u : 0u;
    *req_addr   = s_current.addr;
    *req_value  = s_current.value;
  }
}
