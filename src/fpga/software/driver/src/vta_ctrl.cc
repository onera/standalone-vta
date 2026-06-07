#include "../include/vta_ctrl.h"
#include "../include/vta.h"
extern "C" {
#include "xil_io.h" // dsb()/dmb()/isb() via xpseudo_asm.h
}
namespace vta {

void write_reg(std::uintptr_t base, std::uint32_t offset, std::uint32_t value) {
  Xil_Out32(static_cast<UINTPTR>(base + offset), value);
}

std::uint32_t read_reg(std::uintptr_t base, std::uint32_t offset) {
  return Xil_In32(static_cast<UINTPTR>(base + offset));
}

void write_config(std::uintptr_t base, const VTARegs &r) {
  // writes the number of instructions in the val reg
  write_reg(base, REG_VALS, r.vals);

  // writes each data type addresses offset to ptr register
  for (std::size_t i = 0; i < 6; ++i) {
    write_reg(base, REG_PTR(i), r.ptr[i]);
  }
}
void launch(std::uintptr_t base) {
  // explicit Data synchronization barrier
  dsb();
  write_reg(base, REG_CTRL, CTRL_LAUNCH);
}

void dump_config(std::uintptr_t base) {
  xil_printf("ctrl = 0x%08x\r\n", read_reg(base, REG_CTRL));
  xil_printf("ecnt = 0x%08x\r\n", read_reg(base, REG_ECNT));
  xil_printf("vals = 0x%08x\r\n", read_reg(base, REG_VALS));

  for (unsigned i = 0u; i < 6u; ++i) {
    xil_printf("ptr[%u] = 0x%08x\r\n", i, read_reg(base, REG_PTR(i)));
  }

  xil_printf("ucnt = 0x%08x\r\n", read_reg(base, REG_UCNT));
}
void print_cycles(std::uintptr_t base) {
  xil_printf("Number of cycles: %u\r\n", read_reg(base, REG_ECNT));
  xil_printf("Number of compute cycles: %u\r\n", read_reg(base, REG_UCNT));
}
} // namespace vta
