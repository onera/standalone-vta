#ifndef DPI_HOST_H_
#define DPI_HOST_H_

#include "dpi_types.h"

/**
 * Public C++ API used by verilated_device.cc to enqueue VCR transactions
 * before the clock loop starts.  The actual AXI-Lite protocol is handled
 * entirely in SV (VTAHostDPI.v + VTAHostDPIToAXI.sv).
 *
 * After VTAHostDPI_QueueWrite(VCR_CTRL, 1) (the launch write), the DPI
 * function auto-polls the ctrl register every POLL_PERIOD cycles and calls
 * VTASimDPI_SetExit() when the finish bit is observed.
 */

/** Reset all internal state — call before each Run(). */
void VTAHostDPI_Reset();

/** Enqueue a VCR register write. */
void VTAHostDPI_QueueWrite(uint8_t addr, uint32_t value);

/** Retrieve counter values captured after the finish bit was observed.
 *  Valid only after a successful Run() returns. */
uint32_t VTAHostDPI_GetECnt();
uint32_t VTAHostDPI_GetUCnt();

// VTAHostDPI() is declared extern "C" in dpi_host.cc and linked
// automatically by the DPI framework.

#endif  // DPI_HOST_H_
