# VTA Simulators

This directory contains the functional (C++) and cycle-accurate (CHISEL) simulators for the VTA.

## Subdirectories

- `functional_simulator/`: The C++ functional simulator, extended to support verilated DPI backend.
- `cycle_accurate_simulator/`: The VTA hardware generator in CHISEL, with unit and integrations tests.

## Using the Simulators

The simulator (functional simulator) can run full NN model computational graph produced by the VTA compiler
where the cycle_accurate_simulator only runs parts of the VTA design on binary memory initialization files produced by the compiler (i.e. single VTA IR).

Refer to the individual `README.md` files within each subdirectory for detailed instructions on building, running, and using the specific simulator.

## Emitting SystemVerilog files

Using the CHISEL module, one can emit SystemVerilog for various backend among which the DPI Simulation wrapper that is taken by the functional simulator.
