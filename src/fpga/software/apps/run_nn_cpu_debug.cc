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
 * To regenerate headers:
 *   python3 host/gen_nn_baremetal.py <compiler_output_dir>      \
 *       --ddr-base    0x10000000                                \
 *       --outdir      gen                                       \
 *       --config-json ../../../config/vta_config.json           \
 *       --emit-layer-check --emit-cpu-check --ref-dir <repo>/simulators_output
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

int main() {
  vta::board_init();
  xil_printf("=== VTA CPU-op isolation runner: %u step(s) ===\r\n",
             static_cast<unsigned>(NN_NUM_CPU_DEBUG));

  bool ok = vta::run_nn_cpu_debug(VTA_VCR_BASE, nn_exec_steps, NN_NUM_STEPS,
                                  nn_layers, NN_NUM_LAYERS, nn_cpu_debug,
                                  NN_NUM_CPU_DEBUG);

  if (!ok)
    return -1;
  xil_printf("=== CPU-op isolation check done ===\r\n");
  return 0;
}
