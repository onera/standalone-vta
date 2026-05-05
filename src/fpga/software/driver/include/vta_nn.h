#ifndef VTA_NN_H_
#define VTA_NN_H_

#include <cstdint>
#include "vta.h"

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
    std::uint32_t ddr_base;    // ptr[1..5]: base DDR address shared by all buffer types
    std::uint32_t insn_addr;   // ptr[0]:    absolute address of the instruction buffer
    std::uint32_t insn_count;  // vals:      number of 128-bit (16-byte) instructions

    // --- Buffer physical addresses and sizes (for cache operations) ---
    // Each physical address = ddr_base + buffer_offset (offset baked into instructions)
    std::uint32_t uop_phys,  uop_bytes;
    std::uint32_t inp_phys,  inp_bytes;
    std::uint32_t wgt_phys,  wgt_bytes;
    std::uint32_t acc_phys,  acc_bytes;
    std::uint32_t out_phys,  out_bytes;

    // --- Optional post-layer output relocation (reloc_bytes == 0 → disabled) ---
    // When non-zero: copies [reloc_src, reloc_src+reloc_bytes) to reloc_dst after done.
    // Use this when the next layer's input is not co-located with this layer's output.
    std::uint32_t reloc_src;
    std::uint32_t reloc_dst;
    std::uint32_t reloc_bytes;
};

/**
 * Run a single layer:
 *   1. Flush cache for all input regions (insn, uop, inp, wgt, acc)
 *   2. Program VCR registers and launch VTA
 *   3. Poll finish flag with a timeout
 *   4. Invalidate cache for the output region
 *   5. Optionally relocate output if reloc_bytes > 0
 *
 * @param vcr_base  AXI base address of the VTA VCR peripheral
 * @param layer     Layer descriptor (addresses, sizes, optional reloc)
 * @param timeout   Maximum poll iterations before giving up (0 = unlimited)
 * @return 0 on success, -1 on timeout
 */
int run_layer(std::uintptr_t vcr_base, const LayerDesc &layer,
              int timeout = 500000);

/**
 * Run all layers in sequence.
 *
 * @param vcr_base  AXI base address of the VTA VCR peripheral
 * @param layers    Array of layer descriptors
 * @param n_layers  Number of layers
 * @return 0 on full success, -(layer_index + 1) on failure
 */
int run_nn(std::uintptr_t vcr_base, const LayerDesc *layers, int n_layers);

} // namespace vta

#endif // VTA_NN_H_
