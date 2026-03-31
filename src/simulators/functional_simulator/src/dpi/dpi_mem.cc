/*!
 * \file dpi_mem.cc
 * \brief VTAMemDPI DPI-C implementation.
 *
 * Implements the DPI-C function imported by VTAMemDPI.v.  The SV side
 * (VTAMemDPIToAXI.sv) handles the full AXI4 burst protocol and presents
 * clean per-beat read/write signals here.  We only need to read/write the
 * VirtualMemoryManager (shared DRAM) beat by beat.
 *
 * For the default VTA configuration (DATA_BITS=64), blockNb=1 — each beat
 * is a single 64-bit word.  The svOpenArrayHandle wr_value / rd_value each
 * hold one element.
 */

#include "dpi_mem.h"
#include "dpi_types.h"
#include "../../include/virtual_memory.h"

#include <svdpi.h>
#include <deque>
#include <cstring>

using DRAM = vta::vmem::VirtualMemoryManager;

static const int kBytesPerBeat = 8;  // 64-bit data bus

struct RdTxn {
  uint32_t addr;  // current byte address for the next beat
  uint8_t  len;   // remaining beats after this one (AXI: len=0 → 1 beat)
  uint8_t  id;
};

static std::deque<RdTxn> s_rq;            // pending / in-progress read bursts
static uint32_t          s_wr_addr = 0;   // write burst current byte address
// NOTE: we assume VTAMemDPIToAXI.sv serialises AW and W such that a new
// wr_req_valid pulse never arrives before the previous burst's beats are
// all delivered.  This matches the current Chisel-generated implementation.

void VTAMemDPI_Reset() {
  s_rq.clear();
  s_wr_addr = 0;
}

// DPI-C function called by VTAMemDPI.v on every rising clock edge.
extern "C" void VTAMemDPI(
    dpi8_t  rd_req_valid, dpi8_t rd_req_len, dpi8_t rd_req_id,
    dpi64_t rd_req_addr,
    dpi8_t  wr_req_valid, dpi8_t wr_req_len, dpi64_t wr_req_addr,
    dpi8_t  wr_valid, const svOpenArrayHandle wr_value, dpi64_t wr_strb,
    dpi8_t  *rd_valid, dpi8_t *rd_id, const svOpenArrayHandle rd_value,
    dpi8_t  rd_ready)
{
  *rd_valid = 0;
  *rd_id    = 0;

  // Zero the output data array (blockNb=1 → single 64-bit element)
  dpi64_t *rd_ptr = static_cast<dpi64_t *>(svGetArrayPtr(rd_value));
  if (rd_ptr) *rd_ptr = 0;

  // -----------------------------------------------------------------------
  // 1. Enqueue new read burst request (pulsed for one cycle by SV)
  // -----------------------------------------------------------------------
  if (rd_req_valid) {
    RdTxn txn;
    txn.addr = static_cast<uint32_t>(rd_req_addr);
    txn.len  = rd_req_len;
    txn.id   = rd_req_id;
    s_rq.push_back(txn);
  }

  // -----------------------------------------------------------------------
  // 2. Capture write burst base address (pulsed for one cycle by SV)
  // -----------------------------------------------------------------------
  if (wr_req_valid)
    s_wr_addr = static_cast<uint32_t>(wr_req_addr);

  // -----------------------------------------------------------------------
  // 3. Write data beat to virtual memory
  // -----------------------------------------------------------------------
  if (wr_valid) {
    const dpi64_t *wr_ptr = static_cast<const dpi64_t *>(svGetArrayPtr(wr_value));
    uint8_t *mem = static_cast<uint8_t *>(
        DRAM::Global()->GetAddr(static_cast<uint64_t>(s_wr_addr)));
    memcpy(mem, wr_ptr, kBytesPerBeat);
    s_wr_addr += kBytesPerBeat;
  }

  // -----------------------------------------------------------------------
  // 4. Serve read data from virtual memory (one beat per cycle)
  // -----------------------------------------------------------------------
  if (!s_rq.empty()) {
    RdTxn &front = s_rq.front();

    uint8_t *mem = static_cast<uint8_t *>(
        DRAM::Global()->GetAddr(static_cast<uint64_t>(front.addr)));
    dpi64_t beat = 0;
    memcpy(&beat, mem, kBytesPerBeat);

    *rd_valid = 1;
    *rd_id    = front.id;
    if (rd_ptr) *rd_ptr = beat;

    if (rd_ready) {
      front.addr += kBytesPerBeat;
      if (front.len == 0) {
        s_rq.pop_front();  // burst complete
      } else {
        --front.len;
      }
    }
  }
}
