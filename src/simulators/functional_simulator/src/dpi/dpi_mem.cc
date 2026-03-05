/*!
 * \file dpi_mem.cc
 * \brief AXI memory slave that serves VTAShell DRAM requests.
 *
 * Data comes from / goes to the VirtualMemoryManager (DRAM::Global())
 * that is shared with the functional model.
 */

#include "dpi_mem.h"
#include "../../include/virtual_memory.h"

#include <cstring>

using DRAM = vta::vmem::VirtualMemoryManager;

static const int kBytesPerBeat = 8;  // 64-bit data bus

DPIMem::DPIMem()
    : rstate_(R_IDLE), r_addr_(0), r_len_(0), r_id_(0),
      wstate_(W_IDLE), w_addr_(0), w_len_(0) {}

void DPIMem::Tick(
    uint8_t   ar_valid, uint32_t  ar_addr, uint8_t  ar_len, uint8_t ar_id,
    uint8_t&  ar_ready,
    uint8_t&  r_valid,  uint64_t& r_data,  uint8_t& r_last, uint8_t& r_id,
    uint8_t   r_ready,
    uint8_t   aw_valid, uint32_t  aw_addr, uint8_t  aw_len,
    uint8_t&  aw_ready,
    uint8_t   w_valid,  uint64_t  w_data,  uint8_t  w_last,
    uint8_t&  w_ready,
    uint8_t&  b_valid,  uint8_t   b_ready)
{
  // Defaults
  ar_ready = 0;
  r_valid  = 0; r_data = 0; r_last = 0; r_id = 0;
  aw_ready = 0;
  w_ready  = 0;
  b_valid  = 0;

  // -----------------------------------------------------------------------
  // Read channel state machine
  // -----------------------------------------------------------------------
  switch (rstate_) {
    case R_IDLE:
      ar_ready = 1;
      if (ar_valid) {
        r_addr_ = ar_addr;
        r_len_  = ar_len;   // number of remaining beats - 1 (AXI: len+1 beats)
        r_id_   = ar_id;    // echo back the AR transaction ID
        rstate_ = R_DATA;
      }
      break;

    case R_DATA: {
      // Serve one beat per cycle when r_ready is high
      uint8_t* ptr = static_cast<uint8_t*>(
          DRAM::Global()->GetAddr(static_cast<uint64_t>(r_addr_)));
      uint64_t beat = 0;
      memcpy(&beat, ptr, kBytesPerBeat);

      r_valid = 1;
      r_data  = beat;
      r_id    = r_id_;
      r_last  = (r_len_ == 0) ? 1 : 0;

      if (r_ready) {
        r_addr_ += kBytesPerBeat;
        if (r_len_ == 0) {
          rstate_ = R_IDLE;
        } else {
          --r_len_;
        }
      }
      break;
    }
  }

  // -----------------------------------------------------------------------
  // Write channel state machine
  // -----------------------------------------------------------------------
  switch (wstate_) {
    case W_IDLE:
      aw_ready = 1;
      if (aw_valid) {
        w_addr_ = aw_addr;
        w_len_  = aw_len;
        wstate_ = W_DATA;
      }
      break;

    case W_DATA:
      w_ready = 1;
      if (w_valid) {
        uint8_t* ptr = static_cast<uint8_t*>(
            DRAM::Global()->GetAddr(static_cast<uint64_t>(w_addr_)));
        memcpy(ptr, &w_data, kBytesPerBeat);
        w_addr_ += kBytesPerBeat;
        if (w_last) {
          wstate_ = W_RESP;
        }
      }
      break;

    case W_RESP:
      b_valid = 1;
      if (b_ready) {
        wstate_ = W_IDLE;
      }
      break;
  }
}
