#ifndef _VTA_MEM_H_
#define _VTA_MEM_H_
#include "vta.h"
#include <cstdint>
namespace vta {
void init_ddr_region(std::uintptr_t dst_addr, const void *src,
                     std::size_t bytes, const char *name);

// Fill a DDR region with a repeating 32-bit pattern (e.g. a 0xDEADBEEF
// sentinel) and flush it to DRAM.  Handles non-4-multiple sizes (int8 configs)
// via a byte tail.  Used to pre-stamp OUT regions so untouched bytes are
// obvious afterwards.
void fill_ddr_region(std::uintptr_t dst_addr, std::size_t bytes,
                     std::uint32_t pattern, const char *name);

void copy_insns_to_vta(volatile std::uint32_t *dst, const VTAInsn *src,
                       std::size_t count);

void dump_words(const char *name, std::uintptr_t addr, std::size_t n);

void dump_insn(const char *name, const volatile std::uint32_t *p);
} // namespace vta
#endif
