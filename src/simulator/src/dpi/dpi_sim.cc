/*!
 * \file dpi_sim.cc
 * \brief VTASimDPI implementation.
 *
 * Implements the DPI-C function called by VTASimDPI.v every clock cycle,
 * plus helper functions used by verilated_device.cc to control exit state.
 *
 * When sim_exit=1 is returned to the SV side, VTASimDPI.v calls $finish.
 * vl_finish() (defined in verilated_device.cc) intercepts that and sets
 * Verilated::gotFinish(true) instead of exiting the process.
 */

#include "dpi_sim.h"

static uint8_t g_sim_exit = 0;

void VTASimDPI_SetExit() { g_sim_exit = 1; }
void VTASimDPI_Reset()   { g_sim_exit = 0; }
uint8_t VTASimDPI_GetExit() { return g_sim_exit; }

// DPI-C function called by VTASimDPI.v on every rising clock edge.
extern "C" void VTASimDPI(dpi8_t *sim_wait, dpi8_t *sim_exit) {
  *sim_wait = 0;
  *sim_exit = g_sim_exit;
}
