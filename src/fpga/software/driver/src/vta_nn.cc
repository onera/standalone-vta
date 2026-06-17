#include "../include/vta_nn.h"
#include "../include/vta_cpu_ops.h"
#include "../include/vta_ctrl.h"
#include "vta_hw_config.h"

#include <cstdlib>
extern "C" {
#include "sleep.h"
#include "xil_cache.h"
#include "xil_printf.h"
#include "xparameters.h"
}

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

bool find_input(const NnExecStep *steps, unsigned num_steps,
                std::uint32_t *raw_addr, std::uint32_t *input_n_bytes) {
  for (unsigned i = 0; i < num_steps; ++i) {
    if (steps[i].type == NN_STEP_FORMAT_INPUT) {
      const auto &fi = steps[i].format_input;
      *raw_addr = fi.raw_addr;
      *input_n_bytes = fi.tensor_ch * fi.tensor_h * fi.tensor_w;
      return true;
    }
  }
  return false;
}

float *run_nn(std::uintptr_t vcr_base, const NnExecStep *steps,
              unsigned num_steps, const LayerDesc *layers, unsigned num_layers,
              std::uint32_t *float_bytes_out, bool *ok) {
  *ok = true;
  *float_bytes_out = 0;
  float *float_buf = nullptr;

  // Loader-provided static data (INSN/UOP/WGT/ACC) is placed in DRAM by an
  // external loader (.incbin section / JTAG download) that bypasses the PS
  // D-cache.  The VTA reads DRAM directly over AXI, so any stale/uninitialised
  // cache line for these regions must be reconciled with DRAM before the first
  // launch.  Do it once up front (like apps/test_gemm/test_gemm.cc):
  // Xil_DCacheFlushRange is clean+invalidate on Zynq, which both pushes any
  // cached copy to DRAM and drops stale lines.  CPU-produced INP is handled by
  // CPU-produced INP/OUT is flushed per-step in the dispatch loop below.
  for (unsigned L = 0u; L < num_layers; ++L) {
    const LayerDesc &ld = layers[L];
    Xil_DCacheFlushRange(static_cast<UINTPTR>(ld.insn_addr),
                         static_cast<INTPTR>(ld.insn_count * 16u));
    if (ld.uop_bytes > 0u)
      Xil_DCacheFlushRange(static_cast<UINTPTR>(ld.uop_phys),
                           static_cast<INTPTR>(ld.uop_bytes));
    if (ld.wgt_bytes > 0u)
      Xil_DCacheFlushRange(static_cast<UINTPTR>(ld.wgt_phys),
                           static_cast<INTPTR>(ld.wgt_bytes));
    if (ld.acc_bytes > 0u)
      Xil_DCacheFlushRange(static_cast<UINTPTR>(ld.acc_phys),
                           static_cast<INTPTR>(ld.acc_bytes));
  }

  for (unsigned i = 0u; i < num_steps; ++i) {
    const NnExecStep &s = steps[i];
    xil_printf("[vta] step %u/%u: %s\r\n", i, num_steps - 1u, s.name);

    switch (s.type) {
    case NN_STEP_VTA:
      if (s.vta.layer_idx < 0 ||
          s.vta.layer_idx >= static_cast<int>(num_layers)) {
        xil_printf("=== bad layer_idx %d at step %u ===\r\n", s.vta.layer_idx,
                   i);
        std::free(float_buf);
        *ok = false;
        return nullptr;
      }
      if (run_layer(vcr_base, layers[s.vta.layer_idx]) != 0) {
        xil_printf("=== VTA layer failed at step %u ===\r\n", i);
        std::free(float_buf);
        *ok = false;
        return nullptr;
      }
      break;

    case NN_STEP_QADD:
      run_qadd(s.qadd);
      Xil_DCacheFlushRange(static_cast<UINTPTR>(s.qadd.out),
                           static_cast<INTPTR>(s.qadd.n_elems));
      break;

    case NN_STEP_CONCAT:
      run_concat(s.concat);
      Xil_DCacheFlushRange(
          static_cast<UINTPTR>(s.concat.out),
          static_cast<INTPTR>(s.concat.n_rows * s.concat.n_ch_per_inp *
                              static_cast<std::uint32_t>(s.concat.nb_inp)));
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
      Xil_DCacheFlushRange(static_cast<UINTPTR>(s.quant.out_addr),
                           static_cast<INTPTR>(s.quant.n_elems));
      std::free(float_buf);
      float_buf = nullptr;
      *float_bytes_out = 0;
      break;

    case NN_STEP_FORMAT_INPUT:
      Xil_DCacheFlushRange(static_cast<UINTPTR>(s.format_input.raw_addr),
                           static_cast<INTPTR>(s.format_input.tensor_ch *
                                               s.format_input.tensor_h *
                                               s.format_input.tensor_w));
      run_format_input(s.format_input);
      Xil_DCacheFlushRange(
          static_cast<UINTPTR>(s.format_input.inp_addr),
          static_cast<INTPTR>(s.format_input.out_h * s.format_input.out_w *
                              s.format_input.tensor_ch * s.format_input.kh *
                              s.format_input.kw * sizeof(vta_inp_t)));
      break;

    case NN_STEP_IM2ROW:
      run_im2row(s.im2row);
      Xil_DCacheFlushRange(static_cast<UINTPTR>(s.im2row.dst_addr),
                           static_cast<INTPTR>(s.im2row.out_h * s.im2row.out_w *
                                               s.im2row.tensor_ch *
                                               s.im2row.kh * s.im2row.kw *
                                               sizeof(vta_inp_t)));
      break;

    case NN_STEP_RESCALE:
      run_rescale(s.rescale);
      Xil_DCacheFlushRange(static_cast<UINTPTR>(s.rescale.addr),
                           static_cast<INTPTR>(s.rescale.n_elems));
      break;

    case NN_STEP_INT32_CHAIN:
      run_int32_chain(s.int32_chain);
      Xil_DCacheFlushRange(
          static_cast<UINTPTR>(s.int32_chain.dst_addr),
          static_cast<INTPTR>(s.int32_chain.n_elems * sizeof(vta_acc_t)));
      break;

    case NN_STEP_CONVTRANSPOSE: {
      // Float deconvolution: consumes the live float_buf (produced by a prior
      // dequant) and produces a new, larger float_buf consumed by the next
      // quant - same plumbing as dequant/quant, but the element count changes.
      const NnConvTransposeStep &ct = s.convtranspose;
      // Weights/bias were placed in DRAM by the loader (.incbin / JTAG dow),
      // bypassing the PS D-cache; reconcile before the CPU reads them.
      Xil_DCacheFlushRange(static_cast<UINTPTR>(ct.wgt_addr),
                           static_cast<INTPTR>(ct.tensor_ch * ct.out_ch *
                                               ct.kh * ct.kw * sizeof(float)));
      if (ct.has_bias)
        Xil_DCacheFlushRange(static_cast<UINTPTR>(ct.bias_addr),
                             static_cast<INTPTR>(ct.out_ch * sizeof(float)));
      float *ct_out =
          static_cast<float *>(std::malloc(ct.n_out_elems * sizeof(float)));
      if (!ct_out) {
        xil_printf("=== malloc failed at step %u ===\r\n", i);
        std::free(float_buf);
        *ok = false;
        return nullptr;
      }
      run_convtranspose(ct, float_buf, ct_out);
      std::free(float_buf);
      float_buf = ct_out;
      *float_bytes_out = ct.n_out_elems * sizeof(float);
      // ct_out is CPU-only float scratch (consumed by the next quant step); no
      // DDR flush needed, like the dequant output.
      break;
    }
    }
  }

  return float_buf;
}

} // namespace vta
