#ifndef VTA_NN_DEBUG_H_
#define VTA_NN_DEBUG_H_

#include "vta_nn.h"
#include <cstdint>

// -----------------------------------------------------------------------------
// Per-layer VTA isolation checker (debug only).
//
// Diagnoses the wrong-data path: instead of letting layer N consume the
// (possibly corrupted) output of layer N-1, each VTA layer is fed the
// fsim-precomputed *golden* input and its raw OUT (pre-rescale) is compared
// against the fsim-precomputed *golden* output.  The first layer that
// mismatches on golden inputs is the one whose VTA execution actually
// introduces corruption (not a cascade artifact).
//
// Golden input/output binaries (fsim VTA_DUMP_LAYERS=1: input<SUFFIX>.bin /
// output<SUFFIX>.bin) are embedded in the ELF and placed in a reserved DRAM
// region by host/gen_nn_baremetal.py --emit-layer-check.  The generated
// nn_debug_map.h provides the nn_debug[] table below.
//
// This whole path is compiled only when NN_CHECK_LAYERS is defined; otherwise
// the functions are no-ops so a normal image links without the reference data.
// run_nn / run_layer / LayerDesc are intentionally left untouched.
// -----------------------------------------------------------------------------

namespace vta {

// One isolation-test entry per VTA layer (parallel to nn_layers[]).
struct DebugLayerDesc {
  std::uint32_t layer_idx;     // index into nn_layers[]
  std::uint32_t in_ref_phys;   // golden input data (reserved DRAM region)
  std::uint32_t in_ref_bytes;  // golden input byte count (0 = skip input load)
  std::uint32_t in_dst_phys;   // destination buffer: inp_phys (im2row) or
                               // acc_phys (int32) of the layer
  std::uint32_t out_ref_phys;  // golden output data (reserved DRAM region)
  std::uint32_t out_ref_bytes; // golden output byte count (0 = skip compare)
  const char *name;            // layer suffix, for UART reports
};

// Compare the raw VTA OUT region (pre-rescale) of `layer` against the golden
// output at `ref_phys` (`ref_bytes` long), element-wise as vta_out_t.  Prints a
// per-layer summary over UART and returns the mismatch count (0 = match, or no
// reference / NN_CHECK_LAYERS undefined).
int check_layer_output(const LayerDesc &layer, std::uint32_t ref_phys,
                       std::uint32_t ref_bytes, const char *name);

// Run every VTA layer in isolation on golden inputs and compare each output.
// Reports per layer and continues past mismatches/timeouts so a single run
// surfaces the full picture.  Returns true if all layers matched, false if any
// mismatch or layer failure occurred.  No-op returning true when
// NN_CHECK_LAYERS is undefined.
bool run_nn_debug(std::uintptr_t vcr_base, const LayerDesc *layers,
                  unsigned num_layers, const DebugLayerDesc *dbg,
                  unsigned num_dbg);

} // namespace vta

#endif // VTA_NN_DEBUG_H_
