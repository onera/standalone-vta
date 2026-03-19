#ifndef DPI_SIM_H_
#define DPI_SIM_H_

#include <cstdint>

typedef unsigned char dpi8_t;

/** Signal simulation end — called by dpi_host.cc when finish bit is seen. */
void VTASimDPI_SetExit();

/** Reset exit flag — called before starting a new run. */
void VTASimDPI_Reset();

/** Returns non-zero when simulation should terminate. */
uint8_t VTASimDPI_GetExit();

// VTASimDPI() itself is declared extern "C" in dpi_sim.cc and linked
// automatically by the DPI framework.

#endif  // DPI_SIM_H_
