#include "../include/vta_nn.h"
#include "../include/vta_ctrl.h"
#include "../include/vta_mem.h"
#include <cstring>
extern "C" {
#include "xil_cache.h"
#include "xil_printf.h"
}

namespace vta {

int run_layer(std::uintptr_t vcr_base, const LayerDesc &layer, int timeout) {
  // 1. Flush input regions so the VTA (AXI master) sees up-to-date DDR
  // contents.
  //    Instruction buffer: flush + invalidate.
  Xil_DCacheFlushRange(static_cast<UINTPTR>(layer.insn_addr),
                       layer.insn_count * 16u);
  Xil_DCacheInvalidateRange(static_cast<UINTPTR>(layer.insn_addr),
                            layer.insn_count * 16u);

  Xil_DCacheFlushRange(static_cast<UINTPTR>(layer.uop_phys), layer.uop_bytes);
  Xil_DCacheFlushRange(static_cast<UINTPTR>(layer.inp_phys), layer.inp_bytes);
  Xil_DCacheFlushRange(static_cast<UINTPTR>(layer.wgt_phys), layer.wgt_bytes);
  Xil_DCacheFlushRange(static_cast<UINTPTR>(layer.acc_phys), layer.acc_bytes);

  // 2. Program VCR registers.
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

  // 3. Launch the VTA by writing 0x1 to the ctrl register.
  launch(vcr_base);

  // 4. Poll finish flag (REG_CTRL = 0x2).
  int count = 0;
  while (timeout == 0 || count < timeout) {
    std::uint32_t status = read_reg(vcr_base, REG_CTRL);
    if (status & 0x2u) {
      xil_printf(
          "[vta] finish flag is set, computation is over, after %d polls\n",
          count);
      vta::print_cycles(vcr_base);
      break;
    }
    ++count;
    if (timeout != 0 && count >= timeout) {
      xil_printf("[vta] run_layer: TIMEOUT after %d polls\r\n", timeout);
      return -1;
    }
  }

  // 5. Invalidate output cache so the CPU sees VTA-written DDR contents.
  Xil_DCacheInvalidateRange(static_cast<UINTPTR>(layer.out_phys),
                            layer.out_bytes);

  // 6. Optional output relocation.
  if (layer.reloc_bytes > 0u) {
    auto *dst = reinterpret_cast<void *>(layer.reloc_dst);
    const auto *src = reinterpret_cast<const void *>(layer.reloc_src);
    std::memcpy(dst, src, layer.reloc_bytes);
    Xil_DCacheFlushRange(static_cast<UINTPTR>(layer.reloc_dst),
                         layer.reloc_bytes);
  }

  return 0;
}

int run_nn(std::uintptr_t vcr_base, const LayerDesc *layers, int n_layers) {
  for (int i = 0; i < n_layers; ++i) {
    xil_printf("[vta] layer %d / %d ...\r\n", i, n_layers - 1);
    int ret = run_layer(vcr_base, layers[i]);
    if (ret != 0) {
      xil_printf("[vta] layer %d FAILED (timeout)\r\n", i);
      return -(i + 1);
    }
    print_cycles(vcr_base);
  }
  return 0;
}

} // namespace vta
