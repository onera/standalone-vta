#include "../include/vta_cpu_ops_debug.h"
#include "../include/vta_nn.h"
#include "vta_hw_config.h"

#include <cstring>

extern "C" {
#include "xil_cache.h"
#include "xil_printf.h"
}

namespace vta {

// -----------------------------------------------------------------------------
// Compare helpers
// -----------------------------------------------------------------------------

namespace {

#ifdef NN_CHECK_CPU_OPS_ISO
constexpr unsigned kMaxReported = 8u;

// Print one mismatch entry, decoding bytes as the right signed integer width.
void report_mismatch(const char *name, unsigned k, const void *got,
                     const void *exp, std::uint16_t elem_bytes) {
  if (elem_bytes == 4u) {
    std::int32_t g, e;
    std::memcpy(&g, got, sizeof(g));
    std::memcpy(&e, exp, sizeof(e));
    xil_printf("[chk] %s: elem %u got %d expected %d\r\n", name, k,
               static_cast<int>(g), static_cast<int>(e));
  } else {
    std::int8_t g, e;
    std::memcpy(&g, got, 1u);
    std::memcpy(&e, exp, 1u);
    xil_printf("[chk] %s: elem %u got %d expected %d\r\n", name, k,
               static_cast<int>(g), static_cast<int>(e));
  }
}
#endif

} // namespace

int check_cpu_step_output(std::uint32_t out_phys, std::uint32_t out_bytes,
                          std::uint32_t ref_phys, std::uint32_t ref_bytes,
                          std::uint16_t elem_bytes, const char *name) {
#ifndef NN_CHECK_CPU_OPS_ISO
  (void)out_phys;
  (void)out_bytes;
  (void)ref_phys;
  (void)ref_bytes;
  (void)elem_bytes;
  (void)name;
  return 0;
#else
  if (ref_bytes == 0u || ref_phys == 0u || out_phys == 0u) {
    xil_printf("[chk] %s: no reference - skipped\r\n", name);
    return 0;
  }
  if (elem_bytes != 1u && elem_bytes != 4u) {
    xil_printf("[chk] %s: unsupported elem_bytes %u - skipped\r\n", name,
               static_cast<unsigned>(elem_bytes));
    return -1;
  }
  if (ref_bytes > out_bytes) {
    xil_printf("[chk] %s: ref_bytes %u > out_bytes %u - skipped\r\n", name,
               ref_bytes, out_bytes);
    return -1;
  }

  const auto *got = reinterpret_cast<const std::uint8_t *>(
      static_cast<std::uintptr_t>(out_phys));
  const auto *exp = reinterpret_cast<const std::uint8_t *>(
      static_cast<std::uintptr_t>(ref_phys));
  const unsigned n_elems = ref_bytes / elem_bytes;

  int mismatches = 0;
  for (unsigned k = 0u; k < n_elems; ++k) {
    const std::uint8_t *g = got + k * elem_bytes;
    const std::uint8_t *e = exp + k * elem_bytes;
    if (std::memcmp(g, e, elem_bytes) != 0) {
      if (static_cast<unsigned>(mismatches) < kMaxReported)
        report_mismatch(name, k, g, e, elem_bytes);
      ++mismatches;
    }
  }

  if (mismatches == 0)
    xil_printf("[chk] %s: PASS (%u elems)\r\n", name, n_elems);
  else
    xil_printf("[chk] %s: FAIL %d/%u mismatches\r\n", name, mismatches,
               n_elems);
  return mismatches;
#endif
}

void cpu_debug_invalidate_refs(const DebugCpuStep *table, unsigned table_len) {
#ifndef NN_CHECK_CPU_OPS_ISO
  (void)table;
  (void)table_len;
#else
  if (table == nullptr)
    return;
  for (unsigned i = 0u; i < table_len; ++i) {
    const DebugCpuStep &d = table[i];
    if (d.ref_bytes > 0u && d.ref_phys != 0u)
      Xil_DCacheInvalidateRange(static_cast<UINTPTR>(d.ref_phys),
                                static_cast<INTPTR>(d.ref_bytes));
    if (d.src_ref_bytes > 0u && d.src_ref_phys != 0u)
      Xil_DCacheInvalidateRange(static_cast<UINTPTR>(d.src_ref_phys),
                                static_cast<INTPTR>(d.src_ref_bytes));
  }
#endif
}

// -----------------------------------------------------------------------------
// Isolation-mode driver
// -----------------------------------------------------------------------------

#ifdef NN_CHECK_CPU_OPS_ISO

namespace {

// Dispatch a single CPU step in isolation.  Mirrors the switch in
// vta_nn.cc:144-212 but only handles the step types we check.  Returns true
// if the step was dispatched; false for unsupported types.
bool dispatch_cpu_step(const NnExecStep &s) {
  switch (s.type) {
  case NN_STEP_FORMAT_INPUT:
    Xil_DCacheFlushRange(
        static_cast<UINTPTR>(s.format_input.raw_addr),
        static_cast<INTPTR>(s.format_input.tensor_ch * s.format_input.tensor_h *
                            s.format_input.tensor_w));
    run_format_input(s.format_input);
    Xil_DCacheFlushRange(
        static_cast<UINTPTR>(s.format_input.inp_addr),
        static_cast<INTPTR>(s.format_input.out_h * s.format_input.out_w *
                            s.format_input.tensor_ch * s.format_input.kh *
                            s.format_input.kw * sizeof(vta_inp_t)));
    return true;
  case NN_STEP_IM2ROW:
    run_im2row(s.im2row);
    Xil_DCacheFlushRange(static_cast<UINTPTR>(s.im2row.dst_addr),
                         static_cast<INTPTR>(s.im2row.out_h * s.im2row.out_w *
                                             s.im2row.tensor_ch * s.im2row.kh *
                                             s.im2row.kw * sizeof(vta_inp_t)));
    return true;
  case NN_STEP_INT32_CHAIN:
    run_int32_chain(s.int32_chain);
    Xil_DCacheFlushRange(
        static_cast<UINTPTR>(s.int32_chain.dst_addr),
        static_cast<INTPTR>(s.int32_chain.n_elems * sizeof(vta_acc_t)));
    return true;
  default:
    return false; // rescale / qadd / concat / dequant / quant not checked here
  }
}

} // namespace

#endif // NN_CHECK_CPU_OPS_ISO

bool run_nn_cpu_debug(std::uintptr_t vcr_base, const NnExecStep *steps,
                      unsigned num_steps, const LayerDesc *layers,
                      unsigned num_layers, const DebugCpuStep *cpu_dbg,
                      unsigned num_cpu_dbg) {
#ifndef NN_CHECK_CPU_OPS_ISO
  (void)vcr_base;
  (void)steps;
  (void)num_steps;
  (void)layers;
  (void)num_layers;
  (void)cpu_dbg;
  (void)num_cpu_dbg;
  xil_printf("[chk] run_nn_cpu_debug: built without NN_CHECK_CPU_OPS_ISO -"
             " nothing to do\r\n");
  return true;
#else
  (void)vcr_base; // CPU ops never touch the VCR
  (void)layers;   // descriptors not needed: step carries its own addresses
  (void)num_layers;

  xil_printf("=== CPU-op per-step isolation check: %u step(s) ===\r\n",
             num_cpu_dbg);

  // Golden regions live in DRAM via .incbin (bypasses the PS D-cache); pull
  // them into a known state before our first CPU read.
  cpu_debug_invalidate_refs(cpu_dbg, num_cpu_dbg);

  bool all_ok = true;
  for (unsigned i = 0u; i < num_cpu_dbg; ++i) {
    const DebugCpuStep &d = cpu_dbg[i];
    if (d.step_idx >= num_steps) {
      xil_printf("[chk] entry %u: bad step_idx %u - skipped\r\n", i,
                 d.step_idx);
      all_ok = false;
      continue;
    }
    xil_printf("[chk] step %u/%u: %s\r\n", i, num_cpu_dbg - 1u, d.name);

    // 1. Overwrite the op's source buffer with the upstream golden so the
    //    op runs on a known-good input (breaks any cross-step cascade).  When
    //    src == dst (format_input: the raw image is already loaded at raw_phys)
    //    the copy is a no-op and only the cache invalidate in
    //    cpu_debug_invalidate_refs() matters - skip the redundant memcpy.
    if (d.src_ref_bytes > 0u && d.src_ref_phys != 0u && d.src_dst_phys != 0u &&
        d.src_dst_phys != d.src_ref_phys) {
      std::memcpy(
          reinterpret_cast<void *>(static_cast<std::uintptr_t>(d.src_dst_phys)),
          reinterpret_cast<const void *>(
              static_cast<std::uintptr_t>(d.src_ref_phys)),
          d.src_ref_bytes);
      Xil_DCacheFlushRange(static_cast<UINTPTR>(d.src_dst_phys),
                           static_cast<INTPTR>(d.src_ref_bytes));
    } else if (d.src_ref_bytes == 0u || d.src_ref_phys == 0u ||
               d.src_dst_phys == 0u) {
      xil_printf("[chk] %s: no upstream golden - using preloaded buffer\r\n",
                 d.name);
    }

    // 1b. Replay the producer's in-place rescale on the preloaded golden.  The
    //     producer out_ref is the pre-rescale OUT, but im2row / int32_chain
    //     read the OUT *after* its rescale.  The plan always emits that rescale
    //     as the step immediately before the reshape (VTA -> RESCALE ->
    //     reshape), so run it here to match the live pipeline (mirrors
    //     vta_nn.cc rescale dispatch). No preceding rescale (log_out_width == 3
    //     or format_input) -> nothing to do; producer OUT already equals
    //     out_ref.
    if (d.step_idx > 0u && steps[d.step_idx - 1u].type == NN_STEP_RESCALE) {
      const NnRescaleStep &rs = steps[d.step_idx - 1u].rescale;
      run_rescale(rs);
      Xil_DCacheFlushRange(static_cast<UINTPTR>(rs.addr),
                           static_cast<INTPTR>(rs.n_elems));
    }

    // 2. Dispatch the CPU op alone.
    if (!dispatch_cpu_step(steps[d.step_idx])) {
      xil_printf("[chk] %s: step type %d not checkable - skipped\r\n", d.name,
                 static_cast<int>(steps[d.step_idx].type));
      continue;
    }

    // 3. Make DRAM coherent for our compare read and check.
    if (d.out_bytes > 0u)
      Xil_DCacheInvalidateRange(static_cast<UINTPTR>(d.out_phys),
                                static_cast<INTPTR>(d.out_bytes));
    if (check_cpu_step_output(d.out_phys, d.out_bytes, d.ref_phys, d.ref_bytes,
                              d.elem_bytes, d.name) != 0)
      all_ok = false;
  }

  xil_printf("=== CPU-op isolation check %s ===\r\n", all_ok ? "PASS" : "FAIL");
  return all_ok;
#endif
}

} // namespace vta
