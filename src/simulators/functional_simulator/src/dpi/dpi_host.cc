/*!
 * \file dpi_host.cc
 * \brief AXI-Lite master state machine for VCR register access.
 *
 * Drives the VTAShell `io_host_*` AXI-Lite slave interface.
 * Transactions are enqueued by VerilatedDevice and consumed one per
 * state-machine traversal.
 */

#include "dpi_host.h"

DPIHost::DPIHost()
    : state_(IDLE), current_{false, 0, 0}, last_read_value_(0) {}

void DPIHost::Write(uint16_t addr, uint32_t value) {
  queue_.push_back({true, addr, value});
}

void DPIHost::Read(uint16_t addr) {
  queue_.push_back({false, addr, 0});
}

bool DPIHost::Idle() const {
  return state_ == IDLE && queue_.empty();
}

void DPIHost::Tick(
    uint8_t&  aw_valid, uint16_t& aw_addr,
    uint8_t&  w_valid,  uint32_t& w_data,
    uint8_t&  b_ready,
    uint8_t&  ar_valid, uint16_t& ar_addr,
    uint8_t&  r_ready,
    uint8_t   aw_ready,
    uint8_t   w_ready,
    uint8_t   b_valid,
    uint8_t   ar_ready,
    uint8_t   r_valid,
    uint32_t  r_data)
{
  // Default: deassert all master outputs
  aw_valid = 0; aw_addr = 0;
  w_valid  = 0; w_data  = 0;
  b_ready  = 0;
  ar_valid = 0; ar_addr = 0;
  r_ready  = 0;

  switch (state_) {
    case IDLE:
      if (!queue_.empty()) {
        current_ = queue_.front();
        queue_.pop_front();
        state_ = current_.is_write ? WR_ADDR : RD_ADDR;
      }
      break;

    case WR_ADDR:
      aw_valid = 1;
      aw_addr  = current_.addr;
      if (aw_ready) {
        state_ = WR_DATA;
      }
      break;

    case WR_DATA:
      w_valid = 1;
      w_data  = current_.value;
      if (w_ready) {
        state_ = WR_RESP;
      }
      break;

    case WR_RESP:
      b_ready = 1;
      if (b_valid) {
        state_ = IDLE;
      }
      break;

    case RD_ADDR:
      ar_valid = 1;
      ar_addr  = current_.addr;
      if (ar_ready) {
        state_ = RD_DATA;
      }
      break;

    case RD_DATA:
      r_ready = 1;
      if (r_valid) {
        last_read_value_ = r_data;
        state_ = IDLE;
      }
      break;
  }
}
