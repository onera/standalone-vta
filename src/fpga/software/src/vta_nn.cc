#include "../include/vta_nn.h"
#include "../include/vta_ctrl.h"
#include <cstring>
extern "C" {
#include "sleep.h"
#include "xil_cache.h"
#include "xil_printf.h"
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
  //    Covers ELF-embedded sections and in-place restored backups.
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
    xil_printf("[vta] run_layer: TIMEOUT after %d polls\r\n", timeout);
    return -1;
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

} // namespace vta
