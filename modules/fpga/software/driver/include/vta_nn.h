#ifndef VTA_NN_H_
#define VTA_NN_H_

#include "vta.h"
#include "vta_cpu_ops.h"
#include <cstdint>

namespace vta {

/**
 * Describes one VTA layer execution: what to write into the VCR registers
 * and the physical buffer addresses needed for cache management.
 *
 * VCR register mapping:
 *   ptr[0] = insn_addr   (absolute address of the instruction stream)
 *   ptr[1] = ddr_base    (UOP base - offset encoded in instructions)
 *   ptr[2] = ddr_base    (INP base - offset encoded in instructions)
 *   ptr[3] = ddr_base    (WGT base - offset encoded in instructions)
 *   ptr[4] = ddr_base    (ACC base - offset encoded in instructions)
 *   ptr[5] = ddr_base    (OUT base - offset encoded in instructions)
 *   vals   = insn_count
 */
struct LayerDesc {
  // --- VCR register values ---
  std::uint32_t
      ddr_base; // ptr[1..5]: base DDR address shared by all buffer types
  std::uint32_t
      insn_addr; // ptr[0]:    absolute address of the instruction buffer
  std::uint32_t
      insn_count; // vals:      number of 128-bit (16-byte) instructions

  // --- Buffer physical addresses and sizes (for cache operations) ---
  // Each physical address = ddr_base + buffer_offset (offset baked into
  // instructions)
  std::uint32_t uop_phys, uop_bytes;
  std::uint32_t inp_phys, inp_bytes;
  std::uint32_t wgt_phys, wgt_bytes;
  std::uint32_t acc_phys, acc_bytes;
  std::uint32_t out_phys, out_bytes;
};

/**
 * Run a single layer:
 *   1. Flush cache for all input regions (insn, uop, inp, wgt, acc)
 *   2. Program VCR registers and launch VTA
 *   3. Poll finish flag with a timeout
 *   4. Invalidate cache for the output region
 *
 * @param vcr_base  AXI base address of the VTA VCR peripheral
 * @param layer     Layer descriptor (addresses and sizes)
 * @param timeout   Maximum poll iterations before giving up (0 = unlimited)
 * @return 0 on success, -1 on timeout
 */
int run_layer(std::uintptr_t vcr_base, const LayerDesc &layer,
              int timeout = 500000);

// Scans the supplied step array for the FORMAT_INPUT step.  Fills *raw_addr
// with the scratch DDR address and *input_n_bytes with tensor_ch * tensor_h *
// tensor_w.  Returns false if no FORMAT_INPUT step is present.
bool find_input(const NnExecStep *steps, unsigned num_steps,
                std::uint32_t *raw_addr, std::uint32_t *input_n_bytes);

// Runs the full inference pipeline over the supplied step array.  VTA steps
// dispatch through the supplied layer table (indexed by step.vta.layer_idx).
// Returns a malloc'd float* when the last output is floating-point (DEQUANT
// not followed by QUANT); *float_bytes_out is set to the byte count in that
// case.  Returns nullptr for INT8 output (caller already knows where it
// lives).  Sets *ok = false and frees any intermediate allocation on fatal
// error.
//
// CPU-op verification is not part of this production path; the standalone
// isolation runner (apps/run_nn_cpu_debug.cc → run_nn_cpu_debug) checks the
// host CPU ops against fsim goldens instead.
float *run_nn(std::uintptr_t vcr_base, const NnExecStep *steps,
              unsigned num_steps, const LayerDesc *layers, unsigned num_layers,
              std::uint32_t *float_bytes_out, bool *ok);

} // namespace vta

#endif // VTA_NN_H_
