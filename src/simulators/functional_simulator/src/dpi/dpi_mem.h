#ifndef DPI_MEM_H_
#define DPI_MEM_H_

#include <cstdint>
#include <deque>

/**
 * AXI memory slave state machine serving the VTAShell `io_mem_*` port.
 *
 * VTAShell is an AXI master (reads and writes DRAM); we implement the
 * corresponding slave using the VirtualMemoryManager (DRAM::Global()).
 *
 * The mem interface (from VTAShell.sv) is a simplified single-channel AXI4:
 *   Read  : ar_valid/ar_ready/ar_addr/ar_len, r_valid/r_ready/r_data/r_last/r_id
 *   Write : aw_valid/aw_ready/aw_addr/aw_len, w_valid/w_ready/w_data/w_last,
 *           b_valid/b_ready
 *
 * Data bus width: 64 bits (8 bytes per beat).
 * Address / length encoding: AXI4 (len = number_of_beats - 1).
 *
 * Supports multiple outstanding read transactions (different IDs) via an
 * internal FIFO queue so the master can pipeline AR requests while beats from
 * a previous burst are still being returned.
 */

class DPIMem {
 public:
  DPIMem();

  /**
   * Advance the AXI slave by one clock cycle.
   * Call before dut->eval().
   */
  void Tick(
    // Read address channel (VTAShell drives these, we accept)
    uint8_t   ar_valid,
    uint32_t  ar_addr,
    uint8_t   ar_len,
    uint8_t   ar_id,
    uint8_t&  ar_ready,
    // Read data channel (we drive these)
    uint8_t&  r_valid,
    uint64_t& r_data,
    uint8_t&  r_last,
    uint8_t&  r_id,
    uint8_t   r_ready,
    // Write address channel
    uint8_t   aw_valid,
    uint32_t  aw_addr,
    uint8_t   aw_len,
    uint8_t&  aw_ready,
    // Write data channel
    uint8_t   w_valid,
    uint64_t  w_data,
    uint8_t   w_last,
    uint8_t&  w_ready,
    // Write response channel
    uint8_t&  b_valid,
    uint8_t   b_ready);

 private:
  static const int kMaxOutstandingReads = 8;

  struct RdTxn {
    uint32_t addr;  ///< current byte address for next beat
    uint8_t  len;   ///< beats remaining (0 = last beat not yet sent)
    uint8_t  id;
  };

  enum WState { W_IDLE, W_DATA, W_RESP };

  std::deque<RdTxn> rq_;   ///< FIFO of pending / in-progress read transactions

  WState   wstate_;
  uint32_t w_addr_;
  uint8_t  w_len_;
};

#endif  // DPI_MEM_H_
