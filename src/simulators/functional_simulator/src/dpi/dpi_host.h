#ifndef DPI_HOST_H_
#define DPI_HOST_H_

#include <cstdint>
#include <deque>

/**
 * AXI-Lite master state machine that drives the VTAShell host interface.
 *
 * The VerilatedDevice enqueues write/read transactions before the clock loop.
 * Each call to Tick() advances the state machine by one cycle, driving the
 * correct AXI-Lite signals into the Verilated model.
 *
 * VTAShell host port (from VTAShell.sv):
 *   Outputs we drive  : aw_valid, aw_bits_addr, w_valid, w_bits_data,
 *                       b_ready, ar_valid, ar_bits_addr, r_ready
 *   Inputs we sample  : aw_ready, w_ready, b_valid, ar_ready, r_valid,
 *                       r_bits_data
 */

struct HostTxn {
  bool    is_write;   ///< true = write, false = read
  uint16_t addr;
  uint32_t value;     ///< write value (ignored for reads)
};

class DPIHost {
 public:
  DPIHost();

  /** Enqueue a VCR register write. */
  void Write(uint16_t addr, uint32_t value);

  /** Enqueue a VCR register read; result available via LastReadValue(). */
  void Read(uint16_t addr);

  /** Returns value from the most recently completed read transaction. */
  uint32_t LastReadValue() const { return last_read_value_; }

  /** True when the pending queue is empty and state machine is idle. */
  bool Idle() const;

  /**
   * Advance the AXI-Lite master by one clock cycle.
   * Call AFTER setting dut signals, BEFORE calling dut->eval().
   *
   * Parameters: pointers to the Verilated model's input/output signals.
   */
  void Tick(
    // outputs we set (VTAShell inputs)
    uint8_t&  aw_valid, uint16_t& aw_addr,
    uint8_t&  w_valid,  uint32_t& w_data,
    uint8_t&  b_ready,
    uint8_t&  ar_valid, uint16_t& ar_addr,
    uint8_t&  r_ready,
    // inputs we read (VTAShell outputs)
    uint8_t   aw_ready,
    uint8_t   w_ready,
    uint8_t   b_valid,
    uint8_t   ar_ready,
    uint8_t   r_valid,
    uint32_t  r_data);

 private:
  enum State { IDLE, WR_ADDR, WR_DATA, WR_RESP, RD_ADDR, RD_DATA };
  State    state_;
  HostTxn  current_;
  uint32_t last_read_value_;
  std::deque<HostTxn> queue_;
};

#endif  // DPI_HOST_H_
