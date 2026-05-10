#include "../include/vta_nn.h"
#include "../include/vta_cpu_ops.h"
#include "../include/vta_ctrl.h"
#include "nn_ddr_map.h"
#include "nn_exec_plan.h"
#include <cstdlib>
extern "C" {
#include "sleep.h"
#include "xil_cache.h"
#include "xil_printf.h"
#include "xparameters.h"
}

static constexpr std::uintptr_t VTA_VCR_BASE = XPAR_VTA_0_BASEADDR;

namespace vta {

int run_layer(std::uintptr_t vcr_base, const LayerDesc &layer, int timeout) {
  // 1. Program VCR registers.
  //    ptr[0] = insn_addr (absolute), ptr[1..5] = ddr_base (offsets in
  //    instructions).
  // !!   Assumption: all data are loaded with the same DDR offset
  VTARegs config{};
  config.vals = layer.insn_count;
  config.ptr[0] = layer.insn_addr;
  config.ptr[1] = layer.ddr_base;
  config.ptr[2] = layer.ddr_base;
  config.ptr[3] = layer.ddr_base;
  config.ptr[4] = layer.ddr_base;
  config.ptr[5] = layer.ddr_base;
  write_config(vcr_base, config);

  // 2. Flush static input regions to DDR so VTA (AXI HP port) sees fresh data.
  //    Covers ELF-embedded sections.
  Xil_DCacheFlushRange(static_cast<UINTPTR>(layer.insn_addr),
                       static_cast<INTPTR>(layer.insn_count * 16u));
  if (layer.uop_bytes > 0u)
    Xil_DCacheFlushRange(static_cast<UINTPTR>(layer.uop_phys),
                         static_cast<INTPTR>(layer.uop_bytes));
  if (layer.inp_bytes > 0u)
    Xil_DCacheFlushRange(static_cast<UINTPTR>(layer.inp_phys),
                         static_cast<INTPTR>(layer.inp_bytes));
  if (layer.wgt_bytes > 0u)
    Xil_DCacheFlushRange(static_cast<UINTPTR>(layer.wgt_phys),
                         static_cast<INTPTR>(layer.wgt_bytes));
  if (layer.acc_bytes > 0u)
    Xil_DCacheFlushRange(static_cast<UINTPTR>(layer.acc_phys),
                         static_cast<INTPTR>(layer.acc_bytes));

  // 3. Launch the VTA by writing 0x1 to the ctrl register.
  launch(vcr_base);

  // 4. Poll finish flag (CTRL_DONE bit).  timeout==0 means unlimited.
  bool done = false;
  for (int count = 0; timeout == 0 || count < timeout; ++count) {
    // sleep before polling
    usleep(100);
    if (read_reg(vcr_base, REG_CTRL) & CTRL_DONE) {
      xil_printf("[vta] done after %d polls\r\n", count);
      // Get the number of compute cycles from the VTA
      print_cycles(vcr_base);
      done = true;
      break;
    }
  }
  if (!done) {
    xil_printf("[vta] run_layer: TIMEOUT after %d polls - VCR dump:\r\n",
               timeout);
    dump_config(vcr_base);
    return -1;
  }

  // 5. Invalidate output cache so the CPU sees VTA-written DDR contents.
  Xil_DCacheInvalidateRange(static_cast<UINTPTR>(layer.out_phys),
                            layer.out_bytes);

  return 0;
}

bool find_input(std::uint32_t *raw_addr, std::uint32_t *input_n_bytes) {
  for (unsigned i = 0; i < NN_NUM_STEPS; ++i) {
    if (nn_exec_steps[i].type == NN_STEP_FORMAT_INPUT) {
      const auto &fi = nn_exec_steps[i].format_input;
      *raw_addr = fi.raw_addr;
      *input_n_bytes = fi.tensor_ch * fi.tensor_h * fi.tensor_w;
      return true;
    }
  }
  return false;
}

float *run_nn(std::uint32_t *float_bytes_out, bool *ok) {
  *ok = true;
  *float_bytes_out = 0;
  float *float_buf = nullptr;

  for (unsigned i = 0u; i < NN_NUM_STEPS; ++i) {
    const NnExecStep &s = nn_exec_steps[i];
    xil_printf("[vta] step %u/%u: %s\r\n", i, NN_NUM_STEPS - 1u, s.name);

    switch (s.type) {
    case NN_STEP_VTA:
      if (s.vta.layer_idx < 0 ||
          s.vta.layer_idx >= static_cast<int>(NN_NUM_LAYERS)) {
        xil_printf("=== bad layer_idx %d at step %u ===\r\n", s.vta.layer_idx,
                   i);
        std::free(float_buf);
        *ok = false;
        return nullptr;
      }
      if (run_layer(VTA_VCR_BASE, nn_layers[s.vta.layer_idx]) != 0) {
        xil_printf("=== VTA layer failed at step %u ===\r\n", i);
        std::free(float_buf);
        *ok = false;
        return nullptr;
      }
      break;

    case NN_STEP_QADD:
      run_qadd(s.qadd);
      break;

    case NN_STEP_CONCAT:
      run_concat(s.concat);
      break;

    case NN_STEP_DEQUANT:
      float_buf =
          static_cast<float *>(std::malloc(s.dequant.n_elems * sizeof(float)));
      if (!float_buf) {
        xil_printf("=== malloc failed at step %u ===\r\n", i);
        *ok = false;
        return nullptr;
      }
      *float_bytes_out = s.dequant.n_elems * sizeof(float);
      run_dequant(s.dequant, float_buf);
      break;

    case NN_STEP_QUANT:
      run_quant(s.quant, float_buf);
      std::free(float_buf);
      float_buf = nullptr;
      *float_bytes_out = 0;
      break;

    case NN_STEP_FORMAT_INPUT:
      run_format_input(s.format_input);
      break;

    case NN_STEP_IM2ROW:
      run_im2row(s.im2row);
      break;

    case NN_STEP_RESCALE:
      run_rescale(s.rescale);
      break;
    }
  }

  return float_buf;
}

} // namespace vta
