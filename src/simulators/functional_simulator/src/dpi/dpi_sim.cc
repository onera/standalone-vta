/*!
 * \file dpi_sim.cc
 * \brief Standalone VTASimDPI implementation.
 *
 * Controls simulation termination.  VerilatedDevice sets g_sim_exit = 1
 * when the accelerator finishes or times out.
 */

#include "dpi_sim.h"

static uint8_t g_sim_exit = 0;

void VTASimDPI_SetExit() {
  g_sim_exit = 1;
}

void VTASimDPI_Reset() {
  g_sim_exit = 0;
}

uint8_t VTASimDPI_GetExit() {
  return g_sim_exit;
}
