#include "../include/vta_mem.h"
#include "../include/vta.h"
#include <cstddef>
#include <cstring>
extern "C" {
#include "xil_cache.h"
#include "xil_printf.h"
#include <xil_io.h>
}

namespace vta {
void init_ddr_region(std::uintptr_t dst_addr, const std::uint32_t *src,
                     std::size_t word_count, const char *name) {
  auto *dst = reinterpret_cast<void *>(dst_addr);
  const std::size_t bytes = word_count * sizeof(std::uint32_t);

  std::memcpy(dst, src, bytes);
  Xil_DCacheFlushRange(static_cast<UINTPTR>(dst_addr), bytes);

  xil_printf("%s init: dst=0x%08lx bytes=%lu\r\n", name,
             static_cast<unsigned long>(dst_addr),
             static_cast<unsigned long>(bytes));
}

void copy_insns_to_vta(volatile std::uint32_t *dst, const VTAInsn *src,
                       std::size_t count) {
  const auto *src_words = reinterpret_cast<const std::uint32_t *>(src);
  for (std::size_t i = 0; i < count * 4; ++i) {
    dst[i] = src_words[i];
  }
}

void dump_words(const char *name, std::uintptr_t addr, std::size_t n) {
  auto *p = reinterpret_cast<volatile std::uint32_t *>(addr);
  xil_printf("%s @ 0x%08lx\r\n", name, static_cast<unsigned long>(addr));
  for (std::size_t i = 0; i < n; ++i) {
    xil_printf("  [%lu] = 0x%08lx\r\n", static_cast<unsigned long>(i),
               static_cast<unsigned long>(p[i]));
  }
}

void dump_insn(const char *name, const volatile std::uint32_t *p) {
  xil_printf("%s : %08lx %08lx %08lx %08lx\r\n", name,
             static_cast<unsigned long>(p[0]), static_cast<unsigned long>(p[1]),
             static_cast<unsigned long>(p[2]),
             static_cast<unsigned long>(p[3]));
}
} // namespace vta
