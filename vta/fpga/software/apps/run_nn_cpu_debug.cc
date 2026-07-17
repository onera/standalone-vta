/**
 * run_nn_cpu_debug.cc - Per-CPU-op isolation check (debug, XSCT method).
 *
 * Sibling of run_nn_debug.cc, but for the *host* side of the pipeline.  Each
 * CPU op (format_input / im2row / int32_chain) is executed in isolation on a
 * known-good upstream golden, and its output buffer is compared against the
 * downstream VTA layer's golden input dump (input<SUFFIX>.bin) - by
 * construction equal, since the CPU op writes that buffer.  No new fsim
 * dumps are needed: the same goldens that --emit-layer-check already embeds
 * via .incbin are reused.
 *
 * Build with NN_CHECK_CPU_OPS_ISO defined; otherwise run_nn_cpu_debug() is a
 * no-op.
 *
 * Data loading: with the elf loader the static model and golden refs are
 * embedded via .incbin; with the SD loader (NN_SD_LOADER) they (plus the raw
 * input_nn.bin the format_input op replays) are read from the FAT32 card into
 * the same DDR addresses by vta::sd_load_files() below.
 *
 * To regenerate headers (from software/):
 *   make gen-sd-debug CONFIG=../../../config/vta_config.json \
 *       DDR_BASE=0x10000000 REF_DIR=<repo>/simulators_output \
 *       [SD_DIR=<model>]   # for the SD loader
 *   (gen-sd-debug sets --emit-layer-check --emit-cpu-check)
 */

#include "nn_cpu_debug_map.h"
#include "nn_ddr_map.h"
#include "nn_exec_plan.h"
#include "vta_board.h"
#include "vta_cpu_ops_debug.h"
#include "vta_hw_config.h"
#include "vta_nn.h"
extern "C" {
#include "xil_printf.h"
}
#ifdef NN_SD_LOADER
#include "nn_sd_manifest.h"
#include "vta_sd.h"
#ifndef NN_SD_DIR // older manifest without a subfolder -> card root
#define NN_SD_DIR ""
#endif
#endif

int main() {
  vta::board_init();
  xil_printf("=== VTA CPU-op isolation runner: %u step(s) ===\r\n",
             static_cast<unsigned>(NN_NUM_CPU_DEBUG));

#ifdef NN_SD_LOADER
  // Load the static model, the raw network input (format_input's golden source),
  // and the per-layer goldens from the SD card into DDR. They land at the same
  // addresses nn_cpu_debug[] / nn_debug[] reference, so the checker is unchanged.
  if (vta::sd_load_files("0:/" NN_SD_DIR, nn_sd_static_files,
                         NN_SD_NUM_STATIC) != 0) {
    xil_printf("ERROR: SD static-model load failed\r\n");
    return -1;
  }
#if NN_SD_HAS_INPUT
  if (vta::sd_load_files("0:/" NN_SD_DIR, &nn_sd_input_file, 1) != 0) {
    xil_printf("ERROR: SD input load failed\r\n");
    return -1;
  }
#endif
#if NN_SD_HAS_REFS
  if (vta::sd_load_files("0:/" NN_SD_DIR, nn_sd_ref_files, NN_SD_NUM_REF) != 0) {
    xil_printf("ERROR: SD golden-ref load failed\r\n");
    return -1;
  }
#endif
#endif

  bool ok = vta::run_nn_cpu_debug(VTA_VCR_BASE, nn_exec_steps, NN_NUM_STEPS,
                                  nn_layers, NN_NUM_LAYERS, nn_cpu_debug,
                                  NN_NUM_CPU_DEBUG);

  if (!ok)
    return -1;
  xil_printf("=== CPU-op isolation check done ===\r\n");
  return 0;
}
