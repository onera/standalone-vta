#ifndef _VTA_MEM_H_
#define _VTA_MEM_H_
namespace vta {
void init_ddr_region(std::uintptr_t dst_addr, const std::uint32_t *src,
                     std::size_t word_count, const char *name);

void copy_insns_to_vta(volatile std::uint32_t *dst, const VTAInsn *src,
                       std::size_t count);

void dump_words(const char *name, std::uintptr_t addr, std::size_t n);

void dump_insn(const char *name, const volatile std::uint32_t *p);
} // namespace vta
#endif