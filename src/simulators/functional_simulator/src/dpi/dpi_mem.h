#ifndef DPI_MEM_H_
#define DPI_MEM_H_

// VTAMemDPI() operates fully autonomously — it is called by the SV DPI
// framework each clock cycle and services DRAM read/write requests using
// VirtualMemoryManager directly.  No public C++ API is needed.

// VTAMemDPI() is declared extern "C" in dpi_mem.cc and linked
// automatically by the DPI framework.

#endif  // DPI_MEM_H_
