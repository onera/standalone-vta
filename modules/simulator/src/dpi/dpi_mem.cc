/*!
 * \file dpi_mem.cc
 * \brief VTAMemDPI DPI-C implementation.
 *
 * Implements the DPI-C function imported by VTAMemDPI.v.  The SV side
 * (VTAMemDPIToAXI.sv) handles the full AXI4 burst protocol and presents
 * clean per-beat read/write signals here.  We only need to read/write the
 * VirtualMemoryManager (shared DRAM) beat by beat.
 *
 * The data bus width is not fixed: VTAMemDPI.v declares wr_value / rd_value as
 * `longint unsigned [blockNb-1:0]` with blockNb = DATA_BITS/64, element j
 * carrying data[64*j +: 64] (element 0 = the least significant 64 bits).  So a
 * beat is blockNb consecutive 64-bit words, and this file discovers blockNb
 * from the open-array handle rather than assuming a 64-bit bus - a hardcoded
 * 8-byte beat silently truncates every transfer to its low 64 bits once
 * memParams.dataBits is widened past 64.
 */

#include "dpi_mem.h"
#include "dpi_types.h"
#include "../../include/virtual_memory.h"

#include <svdpi.h>
#include <deque>
#include <cstring>

using DRAM = vta::vmem::VirtualMemoryManager;

static const int kBytesPerWord = 8;  // one DPI array element = 64 bits

// Number of 64-bit words in a bus beat (DATA_BITS/64), read once from the DPI
// open array: it is fixed at elaboration, so the first call settles it.
static int s_block_nb = 0;

static inline int BlockNb(const svOpenArrayHandle h) {
  if (s_block_nb == 0) {
    const int n = svSize(h, 1);
    s_block_nb = (n > 0) ? n : 1;
  }
  return s_block_nb;
}

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

  const int blockNb      = BlockNb(rd_value);
  const int bytesPerBeat = blockNb * kBytesPerWord;

  // Zero the whole output beat, not just its low word.
  for (int j = 0; j < blockNb; ++j) {
    dpi64_t *w = static_cast<dpi64_t *>(svGetArrElemPtr1(rd_value, j));
    if (w) *w = 0;
  }

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
    uint8_t *mem = static_cast<uint8_t *>(
        DRAM::Global()->GetAddr(static_cast<uint64_t>(s_wr_addr)));
    // Honor the AXI write-strobe (byte-enable) mask. Dense stores drive an
    // all-ones strobe (full beat), but partial/sparse stores - e.g. the block-4
    // MaxPool output, where two 32-bit tensors share one 64-bit cacheline and
    // are written by separate single-tensor beats - drive strb=0x0f/0xf0. A
    // full memcpy would let each beat clobber the masked half (the other
    // tensor's bytes) with don't-care bus data, corrupting the neighbour.
    // Bit i of strb gates byte i of the beat, so word j covers strobe bits
    // [8j, 8j+8). VTAMemDPI.v caps STRB_BITS at 64, i.e. a 512-bit bus.
    const uint64_t strb = static_cast<uint64_t>(wr_strb);
    for (int j = 0; j < blockNb; ++j) {
      const dpi64_t *wp =
          static_cast<const dpi64_t *>(svGetArrElemPtr1(wr_value, j));
      if (!wp) continue;
      const uint8_t *src = reinterpret_cast<const uint8_t *>(wp);
      uint8_t *dst = mem + j * kBytesPerWord;
      for (int i = 0; i < kBytesPerWord; ++i) {
        const int bit = j * kBytesPerWord + i;
        if (strb & (uint64_t(1) << bit)) dst[i] = src[i];
      }
    }
    s_wr_addr += bytesPerBeat;
  }

  // -----------------------------------------------------------------------
  // 4. Serve read data from virtual memory (one beat per cycle)
  // -----------------------------------------------------------------------
  if (!s_rq.empty()) {
    RdTxn &front = s_rq.front();

    const uint8_t *mem = static_cast<const uint8_t *>(
        DRAM::Global()->GetAddr(static_cast<uint64_t>(front.addr)));

    *rd_valid = 1;
    *rd_id    = front.id;
    for (int j = 0; j < blockNb; ++j) {
      dpi64_t *w = static_cast<dpi64_t *>(svGetArrElemPtr1(rd_value, j));
      if (w) memcpy(w, mem + j * kBytesPerWord, kBytesPerWord);
    }

    if (rd_ready) {
      front.addr += bytesPerBeat;
      if (front.len == 0) {
        s_rq.pop_front();  // burst complete
      } else {
        --front.len;
      }
    }
  }
}
