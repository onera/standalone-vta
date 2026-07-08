#ifndef DPI_MEM_H_
#define DPI_MEM_H_

/** Reset internal DRAM DPI state - call before each new simulation run. */
void VTAMemDPI_Reset();

// VTAMemDPI() is declared extern "C" in dpi_mem.cc and linked
// automatically by the DPI framework.

#endif  // DPI_MEM_H_
