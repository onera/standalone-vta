#include "vta.h"
namespace vta {

void write_reg(std::uintptr_t base, std::uint32_t offset, std::uint32_t value);

std::uint32_t read_reg(std::uintptr_t base, std::uint32_t offset);

void write_config(std::uintptr_t base, const VTARegs &r);
void launch(std::uintptr_t base);

void dump_config(std::uintptr_t base);
void print_cycles(std::uintptr_t base);
} // namespace vta
