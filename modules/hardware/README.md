# Cycle-Accurate Simulator (CHISEL)

This directory contains the CHISEL cycle-accurate simulator for the VTA. This simulator provides a detailed, cycle-by-cycle model of the VTA's hardware behaviour.

## Prerequisites

There are two options to build the project: SBT or mill

### SBT

In order to build with SBT, you need to install:

- a **Java Development Kit (JDK):** Required for running Scala and SBT.
- the **Scala Build Tool (SBT):** Used for building and running the CHISEL project.

### Mill

Alternatively, to use mill, you don't need to install other dependencies, as the mill script will automatically bootstrap everything (java, mill, dependencies).

## Directory Structure

- `src/main/scala/`: Contains the CHISEL hardware description of the VTA.
  - `core/`: The VTA core - `ISA.scala`, `Decode.scala`, `Fetch.scala`, `Load.scala`,
    `Store.scala`, `Compute.scala`, `TensorGemm.scala`, `TensorAlu.scala`, etc.
    `core/ISA.scala` is the on-chip ISA decoder reference.
  - `shell/`: Shells and the host/memory interfaces (`VTAShell`, `VCR`, `VME`).
  - `configs/`: Configuration classes (e.g. `DefaultPynqConfig`).
  - `exporters/`: SystemVerilog / IP emitters. These are the main classes behind the
    `emitVta*` tasks below.
  - `cli/`: Runnable simulator entry points (`VTAShellSimulator`, `ComputeSimulator`).
  - `interface/`, `models/`, `parsers/`, `dpi/`, `util/`: AXI interfaces, behavioural
    models, DRAM-init parsing, DPI glue, and shared utilities.
- `src/test/scala/`: Contains the simulation testbenches.
  - `src/test/scala/cli/`: Simulation code for executing JSON test files and obtaining step-by-step execution traces (`ComputeTest`, `VTAShellSimulatorTest`).
  - `src/test/scala/simulatorTest/`: JSON-driven `alu/` and `gemm/` integration tests.
  - `src/test/scala/unittest/`: Simple functional unit tests. This is what CI runs.
  - `src/test/scala/shell/`: Shell-level tests (`VCRSpec`, `VMESpec`, `SyncDramAxiSpec`).
  - `src/test/scala/formal/`: Formal verification code. Every test in it is currently
    `ignore`d, so the suite does not run - see the caveat in `formal/README.md`.
- `src/test/resources/`: JSON files used as input for the simulator.

## Building

1. **Run Mill from the repository root** (paths below are relative to this
   module, `modules/hardware/`).

```sh
sbt compile
```

```sh
./mill vta.hardware.compile
```

## Running Simulations

1. **Choose a test case:** The `src/test/scala/simulatorTest` directory contains simulation testbenches that execute JSON files located in `src/test/resources/`.
2. **Execute the test:**

   ```bash
   sbt "testOnly <test_name>"
   ```

   ```bash
   ./mill vta.hardware.test.testOnly <test_name>
   ```

   Replace `<test_name>` with the fully qualified name of the test you want to run. For example:

   ```bash
   sbt "testOnly cli.ComputeTests"
   ```

   ```bash
   ./mill vta.hardware.test.testOnly cli.ComputeTests
   ```

To run the unit-test suite (what CI runs):

   ```bash
   ./mill vta.hardware.test.unittest
   ```

## Chisel VTA simulation

A simulation can be run on the entire VTA (VCR+VME+Core) that initializes an external memory (mocking the external DRAM) by providing a DRAM initialization file in a JSON format (for example [dram_state.json](src/test/resources/examples_shell/dram_state.json))

To execute this simulation, run:

```bash
./mill vta.hardware.runMain cli.VTAShellSimulator <mem init file> <output dir>
```

```bash
sbt "runMain cli.VTAShellSimulator <mem init file> <output dir>"
```

The [VTAShellSimulatorTest.scala](src/test/scala/cli/VTAShellSimulatorTest.scala) file contains a simulation test driven by `src/test/resources/examples_shell/dram_state.json`

## VTA configs emission

There are several configurations and shells available for the VTA that you can emit as SystemVerilog for synthesis or simulation.

For DPI simulation:

```bash
./mill vta.hardware.emitVtaSimConfig
```

This runs the `vta.exporters.TestDefaultPynqConfigEmitter` main class and copies
the result to `build/emitted/vta-sim-shell/`, which is where the functional
simulator's Verilated build expects to find it. It takes no destination
argument.

For FPGA Xilinx IP flow:
To emit the SystemVerilog and tcl script, run the command below; you can specify a custom output directory by passing a path as argument (it defaults to `build/emitted/vta-xilinx-shell/`):
```bash
./mill vta.hardware.emitVtaFpgaConfig <destpath>
```

This runs the `vta.exporters.DefaultXilinxConfigEmitter` main class. The
emitters live in `src/main/scala/exporters/`; use `runMain` (not `run`) if you
need to invoke one directly, since `run` would pass the class name as an
argument to the default main class `cli.VTAShellSimulator`.
You can pass a different configuration (ex: <project_root>/config/your_config.json):

```bash
./mill -Dvta.config.file=your_config.json vta.hardware.emitVtaFpgaConfig <destpath>
```
Then run vivado on the package_ip.tcl script:
```bash
cd <destpath>
vivado -mode batch -script package_ip.tcl
```
You can specify a custom repo path and ip name by passing TCL arguments:
```bash
cd <destpath>
vivado -mode batch -script package_ip.tcl -tclargs --ip_root <ip repo path> --ip_name <vta ip name>
```
## Example

The `ComputeTest.scala` test runs a simulation of the Compute module using a JSON input file. The JSON file specifies the input data, weights, and expected output. The simulation output provides a cycle-by-cycle trace of the Compute module's operation.
