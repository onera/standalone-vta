#ifndef VTA_CPU_OPS_DEBUG_H_
#define VTA_CPU_OPS_DEBUG_H_

#include "vta_cpu_ops.h"
#include <cstdint>

// -----------------------------------------------------------------------------
// Per-CPU-op verification checker (debug only).
//
// The baremetal pipeline interleaves VTA layers with host CPU ops
// (format_input, im2row, rescale, int32_chain, qadd, concat, dequant, quant).
// Today only VTA layers are checkable in isolation (vta_nn_debug.{h,cc}); this
// header adds the symmetric path for CPU ops, reusing the same fsim golden
// inputs (input<SUFFIX>.bin) the layer check already embeds.
//
// Key insight: a CPU op whose output feeds a VTA layer writes that layer's
// INP/ACC buffer, which is exactly the layer's golden input dump.  We don't
// need new fsim dumps - we just point each checkable CPU step at its consumer
// layer's golden input region.
//
// Enabled by NN_CHECK_CPU_OPS_ISO: a separate isolation pass (run_nn_cpu_debug,
// apps/run_nn_cpu_debug.cc) replays each CPU op alone on a known-good upstream
// golden.  This is kept out of the production run_nn path.
//
// When the macro is not set, every entry point is a no-op so the normal
// run_nn image links without any reference data.
// -----------------------------------------------------------------------------

namespace vta {

// Forward declaration (LayerDesc lives in vta_nn.h; we only need pointers).
struct LayerDesc;

// One entry per checkable CPU step in the NnExecStep[] array.  Steps whose
// output does not equal a VTA layer's INP/ACC golden (rescale, qadd, concat,
// dequant, quant) are simply absent from the table.
struct DebugCpuStep {
  std::uint32_t step_idx;  // index into nn_exec_steps[]
  std::uint32_t out_phys;  // op's output buffer (= consumer layer's INP/ACC)
  std::uint32_t out_bytes; // bytes to compare
  std::uint32_t ref_phys;  // golden = consumer layer's in_ref_phys
  std::uint32_t ref_bytes;
  std::uint16_t elem_bytes; // 1 (int8) or 4 (int32); used for the report
  std::uint16_t _pad;
  // --- isolation-mode only (set to 0 when not applicable) ---
  std::uint32_t
      src_ref_phys; // upstream golden (prev VTA layer OUT, or raw image)
  std::uint32_t src_ref_bytes;
  std::uint32_t
      src_dst_phys; // buffer the op reads from (overwritten with src_ref)
  const char *name;
};

// Compare `bytes` bytes at out_phys against ref_phys, element-wise as a signed
// integer of size elem_bytes.  Prints up to 8 mismatches and a per-step
// PASS/FAIL summary over UART.  Returns the mismatch count (0 on match, or no
// reference / NN_CHECK_CPU_OPS_ISO undefined).
int check_cpu_step_output(std::uint32_t out_phys, std::uint32_t out_bytes,
                          std::uint32_t ref_phys, std::uint32_t ref_bytes,
                          std::uint16_t elem_bytes, const char *name);

// One-shot invalidate of every golden region referenced by the table, so the
// PS D-cache picks up DRAM-resident reference data on its first read.
// Mirrors the up-front loop in vta_nn_debug.cc:81-89.  No-op when
// NN_CHECK_CPU_OPS_ISO is undefined.
void cpu_debug_invalidate_refs(const DebugCpuStep *table, unsigned table_len);

// Run each checkable CPU op in isolation: copy the upstream golden into the
// op's source buffer, dispatch the op via the standard run_* helpers, then
// compare the resulting output against the consumer-layer golden.  No layer
// runs depend on the previous op's output, so a single mismatch does not
// cascade.  Returns true if all entries pass; false on any mismatch / failure.
// No-op returning true when NN_CHECK_CPU_OPS_ISO is undefined.
bool run_nn_cpu_debug(std::uintptr_t vcr_base, const NnExecStep *steps,
                      unsigned num_steps, const LayerDesc *layers,
                      unsigned num_layers, const DebugCpuStep *cpu_dbg,
                      unsigned num_cpu_dbg);

} // namespace vta

#endif // VTA_CPU_OPS_DEBUG_H_
