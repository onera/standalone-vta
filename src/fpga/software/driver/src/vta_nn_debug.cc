#include "../include/vta_nn_debug.h"
#include "../include/vta_pl_reset.h"
#include "vta_hw_config.h"

#include <cstring>

extern "C" {
#include "xil_cache.h"
#include "xil_printf.h"
}

namespace vta {

int check_layer_output(const LayerDesc &layer, std::uint32_t ref_phys,
                       std::uint32_t ref_bytes, const char *name) {
#ifndef NN_CHECK_LAYERS
  (void)layer;
  (void)ref_phys;
  (void)ref_bytes;
  (void)name;
  return 0;
#else
  // Number of mismatching elements to print in detail per layer.
  constexpr unsigned kMaxReported = 8u;

  if (ref_bytes == 0u || ref_phys == 0u) {
    xil_printf("[chk] %s: no reference - skipped\r\n", name);
    return 0;
  }
  if (ref_bytes > layer.out_bytes) {
    xil_printf("[chk] %s: ref_bytes %u > out_bytes %u - skipped\r\n", name,
               ref_bytes, layer.out_bytes);
    return -1;
  }

  // Compare the raw OUT region element-wise as vta_out_t.  run_layer() already
  // invalidated layer.out_phys; the golden region is reconciled once in
  // run_nn_debug() before the loop.
  const auto *got = reinterpret_cast<const vta_out_t *>(
      static_cast<std::uintptr_t>(layer.out_phys));
  const auto *exp = reinterpret_cast<const vta_out_t *>(
      static_cast<std::uintptr_t>(ref_phys));
  const unsigned n = ref_bytes / static_cast<std::uint32_t>(sizeof(vta_out_t));

  int mismatches = 0;
  for (unsigned k = 0u; k < n; ++k) {
    if (got[k] != exp[k]) {
      if (static_cast<unsigned>(mismatches) < kMaxReported)
        xil_printf("[chk] %s: elem %u got %d expected %d\r\n", name, k,
                   static_cast<int>(got[k]), static_cast<int>(exp[k]));
      ++mismatches;
    }
  }

  if (mismatches == 0)
    xil_printf("[chk] %s: PASS (%u elems)\r\n", name, n);
  else
    xil_printf("[chk] %s: FAIL %d/%u mismatches\r\n", name, mismatches, n);
  return mismatches;
#endif
}

namespace {

// Byte-compare one live stream against its golden copy, reporting up to
// kMaxReported differing bytes.  `golden_bytes` is the *actual* stream length
// (the compiler .bin size); `live_cap` is the byte capacity of the live buffer
// (insn_count*16 for INSN; the page-padded uop_bytes for UOP, whose tail the
// VTA never fetches and we never compare).  `live_phys`/`golden_phys` are
// physical DDR addresses; the compared live bytes are D-cache-invalidated first
// so any PL-side write (corruption) is observed instead of a stale cached copy.
// Returns the number of mismatching bytes; 0 = identical, -1 = unusable golden.
int compare_stream(const char *name, const char *stream,
                   std::uint32_t live_phys, std::uint32_t live_cap,
                   std::uint32_t golden_phys, std::uint32_t golden_bytes) {
  constexpr unsigned kMaxReported = 8u;

  if (golden_bytes == 0u || golden_phys == 0u) {
    xil_printf("[chk] %s %s: no golden - skipped\r\n", name, stream);
    return 0;
  }
  if (golden_bytes > live_cap) {
    // Codegen guards against this, but never read past the live buffer.
    xil_printf("[chk] %s %s: golden %u B > live capacity %u B - skipped\r\n",
               name, stream, golden_bytes, live_cap);
    return -1;
  }

  // Pull the compared live bytes back from DDR: this is static data the CPU
  // never writes, so dropping any cache line is safe and reveals PL-side
  // corruption.
  Xil_DCacheInvalidateRange(static_cast<UINTPTR>(live_phys),
                            static_cast<INTPTR>(golden_bytes));

  const auto *got = reinterpret_cast<const std::uint8_t *>(
      static_cast<std::uintptr_t>(live_phys));
  const auto *exp = reinterpret_cast<const std::uint8_t *>(
      static_cast<std::uintptr_t>(golden_phys));

  int mismatches = 0;
  for (std::uint32_t k = 0u; k < golden_bytes; ++k) {
    if (got[k] != exp[k]) {
      if (static_cast<unsigned>(mismatches) < kMaxReported)
        xil_printf("[chk] %s %s: byte %u got 0x%02x expected 0x%02x\r\n", name,
                   stream, k, got[k], exp[k]);
      ++mismatches;
    }
  }

  if (mismatches == 0)
    xil_printf("[chk] %s %s: PASS (%u bytes)\r\n", name, stream, golden_bytes);
  else
    xil_printf("[chk] %s %s: FAIL %d/%u bytes corrupted\r\n", name, stream,
               mismatches, golden_bytes);
  return mismatches;
}

} // namespace

int check_layer_insn_uop(const LayerDesc &layer, const DebugLayerDesc &d) {
#ifndef NN_CHECK_LAYERS
  (void)layer;
  (void)d;
  return 0;
#else
  // Live INSN capacity is exactly insn_count fixed 128-bit (16-byte) words; the
  // live UOP buffer is page-padded (uop_bytes) but only the golden-length head
  // is fetched and compared.
  const int insn =
      compare_stream(d.name, "insn", layer.insn_addr, layer.insn_count * 16u,
                     d.insn_ref_phys, d.insn_ref_bytes);
  const int uop = compare_stream(d.name, "uop", layer.uop_phys, layer.uop_bytes,
                                 d.uop_ref_phys, d.uop_ref_bytes);
  // Treat a size-mismatch (-1) as a single failure so the caller still flags
  // it.
  const int insn_bad = insn < 0 ? 1 : insn;
  const int uop_bad = uop < 0 ? 1 : uop;
  return insn_bad + uop_bad;
#endif
}

bool run_nn_debug(std::uintptr_t vcr_base, const LayerDesc *layers,
                  unsigned num_layers, const DebugLayerDesc *dbg,
                  unsigned num_dbg) {
#ifndef NN_CHECK_LAYERS
  (void)vcr_base;
  (void)layers;
  (void)num_layers;
  (void)dbg;
  (void)num_dbg;
  xil_printf(
      "[chk] run_nn_debug: built without NN_CHECK_LAYERS - nothing to do\r\n");
  return true;
#else
  xil_printf("=== VTA per-layer isolation check: %u layer(s) ===\r\n", num_dbg);

  // Golden input/output regions are placed in DRAM by the ELF loader (.incbin
  // sections) bypassing the PS D-cache.  Reconcile every region once up front
  // so CPU reads (memcpy of input, compare of output) see DRAM-resident data,
  // the same treatment run_nn() gives static model data.
  for (unsigned i = 0u; i < num_dbg; ++i) {
    const DebugLayerDesc &d = dbg[i];
    if (d.in_ref_bytes > 0u)
      Xil_DCacheInvalidateRange(static_cast<UINTPTR>(d.in_ref_phys),
                                static_cast<INTPTR>(d.in_ref_bytes));
    if (d.out_ref_bytes > 0u)
      Xil_DCacheInvalidateRange(static_cast<UINTPTR>(d.out_ref_phys),
                                static_cast<INTPTR>(d.out_ref_bytes));
    if (d.insn_ref_bytes > 0u)
      Xil_DCacheInvalidateRange(static_cast<UINTPTR>(d.insn_ref_phys),
                                static_cast<INTPTR>(d.insn_ref_bytes));
    if (d.uop_ref_bytes > 0u)
      Xil_DCacheInvalidateRange(static_cast<UINTPTR>(d.uop_ref_phys),
                                static_cast<INTPTR>(d.uop_ref_bytes));
  }

  bool all_ok = true;
  for (unsigned i = 0u; i < num_dbg; ++i) {
    const DebugLayerDesc &d = dbg[i];
    if (d.layer_idx >= num_layers) {
      xil_printf("[chk] entry %u: bad layer_idx %u - skipped\r\n", i,
                 d.layer_idx);
      all_ok = false;
      continue;
    }
    const LayerDesc &layer = layers[d.layer_idx];
    xil_printf("[chk] layer %u/%u: %s\r\n", i, num_dbg - 1u, d.name);

#ifdef NN_PL_RESET_BETWEEN_LAYERS
    // 0. Pulse the PL-only fabric reset so each layer starts from pristine VTA
    //    hardware state (FSMs / semaphores / VCR cleared).  DDR - including the
    //    golden input we copy in next - is untouched, and run_layer()
    //    reprograms the VCR, so no extra setup is needed.  A failed reset is
    //    non-fatal: we warn and run the layer against whatever state the PL was
    //    left in.
    if (pl_reset() != 0)
      xil_printf("[chk] %s: pl_reset FAILED - running without PL reset\r\n",
                 d.name);
#endif

    // 1. Overwrite the layer's input buffer with the golden fsim input so the
    //    VTA executes on known-good data (breaks the cross-layer cascade).
    //    run_layer() flushes inp/acc to DRAM before launch, so a plain copy
    //    into the cached mapping is sufficient.
    if (d.in_ref_bytes > 0u && d.in_dst_phys != 0u) {
      std::memcpy(
          reinterpret_cast<void *>(static_cast<std::uintptr_t>(d.in_dst_phys)),
          reinterpret_cast<const void *>(
              static_cast<std::uintptr_t>(d.in_ref_phys)),
          d.in_ref_bytes);
    } else {
      xil_printf("[chk] %s: no golden input - using preloaded buffer\r\n",
                 d.name);
    }

    // 1b. Verify the static instruction / micro-op streams the VTA is about to
    //     fetch still match their golden copies.  A mismatch here means an
    //     earlier layer (the prime MaxPool suspect) overwrote this layer's
    //     insn/uop bytes in DDR - distinct from a wrong-data cascade, which the
    //     golden-input load above already neutralises.
    if (check_layer_insn_uop(layer, d) != 0)
      all_ok = false;

    // 2. Run the layer through the unmodified driver path.
    if (run_layer(vcr_base, layer) != 0) {
      xil_printf("[chk] %s: run_layer FAILED\r\n", d.name);
      all_ok = false;
      continue; // continue to the next layer for a full picture
    }

    // 3. Compare the raw OUT region against the golden output.
    if (check_layer_output(layer, d.out_ref_phys, d.out_ref_bytes, d.name) != 0)
      all_ok = false;
  }

  xil_printf("=== isolation check %s ===\r\n", all_ok ? "PASS" : "FAIL");
  return all_ok;
#endif
}

} // namespace vta
