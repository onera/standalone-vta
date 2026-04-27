#include "../examples/init_dram.h"
#include "../include/vta.h"
#include "../include/vta_mem.h"
#include "../include/vta_ctrl.h"
#include "xil_cache.h"
#include "xil_printf.h"
#include <cstdint>
#include <xil_io.h>
#include <xparameters.h>


constexpr std::uintptr_t DDR_VTA_BASE = 0x10000000u;
constexpr std::uintptr_t DDR_UOP_BASE = DDR_VTA_BASE + 0x5000u;
constexpr std::uintptr_t DDR_INP_BASE = DDR_VTA_BASE + 0x1000u;
constexpr std::uintptr_t DDR_WGT_BASE = DDR_VTA_BASE + 0x2000u;
constexpr std::uintptr_t DDR_ACC_BASE = DDR_VTA_BASE + 0x3000u;
constexpr std::uintptr_t DDR_INSN_BASE = DDR_VTA_BASE + 0x6000u;
constexpr std::uintptr_t DDR_OUT_BASE = DDR_VTA_BASE + 0x4000u;

constexpr std::uintptr_t VTA_VCR_BASE = XPAR_VTADEFAULTSHELL_0_BASEADDR;

int main() {
  vta::init_ddr_region(DDR_UOP_BASE, uop, sizeof(uop) / sizeof(uop[0]), "uop");
  vta::init_ddr_region(DDR_INP_BASE, input, sizeof(input) / sizeof(input[0]),"input");
  vta::init_ddr_region(DDR_WGT_BASE, wgt, sizeof(wgt) / sizeof(wgt[0]), "weight");
  vta::init_ddr_region(DDR_ACC_BASE, acc, sizeof(acc) / sizeof(acc[0]), "accum");
  vta::init_ddr_region(DDR_OUT_BASE, acc, sizeof(acc) / sizeof(acc[0]), "output");
  auto *vta_insn = reinterpret_cast<volatile std::uint32_t *>(DDR_INSN_BASE);

  vta::copy_insns_to_vta(vta_insn, insn, sizeof(insn) / sizeof(insn[0]));

  Xil_DCacheInvalidateRange(DDR_INP_BASE, sizeof(input));
  Xil_DCacheInvalidateRange(DDR_UOP_BASE, sizeof(uop));
  Xil_DCacheInvalidateRange(DDR_WGT_BASE, sizeof(wgt));
  Xil_DCacheInvalidateRange(DDR_ACC_BASE, sizeof(acc));
  Xil_DCacheInvalidateRange(DDR_OUT_BASE, sizeof(acc));
  Xil_DCacheFlushRange(reinterpret_cast<UINTPTR>(DDR_INSN_BASE), sizeof(insn));
  Xil_DCacheInvalidateRange(reinterpret_cast<UINTPTR>(DDR_INSN_BASE),
                            sizeof(insn));

  vta::dump_words("uop", DDR_UOP_BASE, 4);
  vta::dump_words("input", DDR_INP_BASE, 4);
  vta::dump_words("weight", DDR_WGT_BASE, 4);
  vta::dump_words("accum", DDR_ACC_BASE, 4);
  vta::dump_insn("insn", vta_insn + 0);

  // program VTA registers with these DDR addresses, then launch

  VTARegs config{};
  config.ptr[0] = DDR_INSN_BASE;
  config.ptr[1] = DDR_VTA_BASE;
  config.ptr[2] = DDR_VTA_BASE;
  config.ptr[3] = DDR_VTA_BASE;
  config.ptr[4] = DDR_VTA_BASE;
  config.ptr[5] = DDR_VTA_BASE;
  config.vals = sizeof(insn) / sizeof(insn[0]);
  vta::write_config(VTA_VCR_BASE, config);
  vta::dump_config(VTA_VCR_BASE);
  vta::launch(VTA_VCR_BASE);
  int count = 0;
  int timeout = 200000;
  
  int countstep = 0;
  u32 status = 0x0u;
  while (1) {
    if (count >= 100) {
      count = 0;
      countstep++;
      status = vta::read_reg(VTA_VCR_BASE, 0x0);
      xil_printf("status: %d\n", status);
    }
    if (status == 2) {
      xil_printf("VTA reached finish state.\n");
      vta::print_cycles(VTA_VCR_BASE);
      return 0;
    }
    count++;
  }
  return -1;
}
