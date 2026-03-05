#ifndef DPI_SIM_H_
#define DPI_SIM_H_

#include <cstdint>

/** Signal simulation end — call from VerilatedDevice when done. */
void VTASimDPI_SetExit();

/** Reset exit flag — call before starting a new run. */
void VTASimDPI_Reset();

/** Returns non-zero when simulation should terminate. */
uint8_t VTASimDPI_GetExit();

#endif  // DPI_SIM_H_
