#ifndef __VTA_H__
#define __VTA_H__

#include <cstdint>
extern "C" {
#include "xil_cache.h"
#include "xil_io.h"
#include "xil_printf.h"
}

struct alignas(16) VTAInsn {
  std::uint32_t w[4];
};
struct VTARegs {
  std::uint32_t ctrl;
  std::uint32_t ecnt;
  std::uint32_t vals;
  std::uint32_t ptr[6];
  std::uint32_t ucnt;
};

namespace vta {
constexpr std::uint32_t REG_CTRL = 4u * 0u;
constexpr std::uint32_t REG_ECNT = 4u * 1u;
constexpr std::uint32_t REG_VALS = 4u * 2u;

constexpr std::uint32_t REG_PTR(std::size_t i) {
  return 4u * (3u + static_cast<std::uint32_t>(i));
}
constexpr std::uint32_t REG_UCNT = 4u * 9u;

constexpr std::uint32_t CTRL_LAUNCH = 0x1u;
constexpr std::uint32_t CTRL_DONE = 0x2u;

} // namespace vta
#endif
