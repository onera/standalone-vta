#pragma once
// Host-test stub for Xilinx's xil_printf (used by vta_cpu_ops.cc on warn/skip
// paths). Forwards to vprintf so messages still surface during the test.
#include <cstdarg>
#include <cstdio>

static inline int xil_printf(const char *fmt, ...) {
  va_list ap;
  va_start(ap, fmt);
  int r = vprintf(fmt, ap);
  va_end(ap);
  return r;
}
