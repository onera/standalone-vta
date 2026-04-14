#include "../include/vta.h"
#include "../include/vta_ctrl.h"
namespace vta {

void write_reg(std::uintptr_t base, std::uint32_t offset, std::uint32_t value) {
  Xil_Out32(static_cast<UINTPTR>(base + offset), value);
}

std::uint32_t read_reg(std::uintptr_t base, std::uint32_t offset) {
  return Xil_In32(static_cast<UINTPTR>(base + offset));
}

void write_config(std::uintptr_t base, const VTARegs &r) {
  write_reg(base, REG_VALS, r.vals);

  for (std::size_t i = 0; i < 6; ++i) {
    write_reg(base, REG_PTR(i), r.ptr[i]);
  }
}
void launch(std::uintptr_t base) { write_reg(base, REG_CTRL, 0x01); }

void dump_config(std::uintptr_t base) {
  xil_printf("ctrl = 0x%08lx\r\n",
             static_cast<unsigned long>(read_reg(base, REG_CTRL)));
  xil_printf("ecnt = 0x%08lx\r\n",
             static_cast<unsigned long>(read_reg(base, REG_ECNT)));
  xil_printf("vals = 0x%08lx\r\n",
             static_cast<unsigned long>(read_reg(base, REG_VALS)));

  for (std::size_t i = 0; i < 6; ++i) {
    xil_printf("ptr[%lu]  = 0x%08lx\r\n", static_cast<unsigned long>(i),
               static_cast<unsigned long>(read_reg(base, REG_PTR(i))));
  }

  xil_printf("ucnt = 0x%08lx\r\n",
             static_cast<unsigned long>(read_reg(base, REG_UCNT)));
}
void print_cycles(std::uintptr_t base){
  xil_printf("Number of cycles: %d\r\n",static_cast<unsigned long>(read_reg(base, REG_ECNT)));
  xil_printf("Number of compute cycles: %d\r\n",static_cast<unsigned long>(read_reg(base, REG_UCNT)));
}
}