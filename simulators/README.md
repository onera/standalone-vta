# VTA Simulators

This directory contains the functional (C++) and cycle-accurate (CHISEL) simulators for the VTA.

## Subdirectories

*   `functional_simulator/`:  The C++ functional simulator.
*   `cycle_accurate_simulator/`: The CHISEL cycle-accurate simulator.

## Using the Simulators

The functional simulator takes raw binary files as input, but the cycle-accurate simulator does not take them yet. JSON file must be emitted to execute the cycle-accurate simulator.
Refer to the individual `README.md` files within each subdirectory for detailed instructions on building, running, and using the specific simulator.
