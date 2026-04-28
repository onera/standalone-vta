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
- `src/test/scala/`: Contains the simulation testbenches.
  - `src/test/scala/formal/`: Formal verification code. (broken in this version)
  - `src/test/scala/simulator/`: Simulation code for executing JSON test files and obtaining step-by-step execution traces.
  - `src/test/scala/unittest/`: Simple functional unit tests.
- `src/test/resources/`: JSON files used as input for the simulator.

## Building

1. **Navigate to the `cycle_accurate_simulator` directory.**
2. **Run SBT or mill**

```sh
sbt compile
```

```sh
./mill _.compile
```

## Running Simulations

1. **Choose a test case:** The `src/test/scala/simulatorTest` directory contains simulation testbenches that execute JSON files located in `src/test/resources/`.
2. **Execute the test:**

   ```bash
   sbt "testOnly <test_name>"
   ```

   ```bash
   ./mill test.testOnly <test_name>
   ```

   Replace `<test_name>` with the fully qualified name of the test you want to run. For example:

   ```bash
   sbt "testOnly simulator.ComputeApp"
   ```

   ```bash
   ./mill test.testOnly simulator.ComputeApp
   ```

## Chisel VTA simulation

A simulation can be run on the entire VTA (VCR+VME+Core) that initializes an external memory (mocking the external DRAM) by providing a DRAM initialization file in a JSON format (for example [dram_state.json](src/test/resouces/examples_shell/dram_state.json))

To execute this simulation, run:

```bash
./mill runMain cli.VTAShellSimulator <mem init file> <output dir>
```

```bash
sbt "runMain cli.VTAShellSimulator <mem init file> <output dir>"
```

The [VTAShellSpec.scala](src/test/scala/shell/VTAShellSpec.scala) file contains a simulation test in `src/resources/examples_shell/dram_state.json`

## VTA configs emission

There are several configurations and shells available for the VTA that you can emit as SystemVerilog for synthesis or simulation.

For DPI simulation (all those are equivalent):

```bash
./mill emitVtaSimConfig
./mill run vta.StandaloneSimConfig
sbt runMain "vta.StandaloneSimConfig"
```

For FPGA Xilinx IP flow:
To emit the SystemVerilog and tcl script, run one of this command; you can specify a custom output directory by passing a path as argument:
```bash
./mill emitVtaFpgaConfig <destpath>
./mill run vta.DefaultPynqConfig
sbt runMain "vta.DefaultPynqConfig"
```
You can pass a different configuration (ex: <project_root>/config/your_config.json):

```bash
./mill -Dvta.config.file=your_config.json emitVtaFpgaConfig <destpath>
```
Then run vivado on the package_ip.tcl script:
```bash
cd <destpath>
vivado -mode batch -script package_ip.tcl
```
You can specify a custom repo path and ip name by passing TCL arguments:
```bash
cd <destpath>
vivado -mode batch -script package_ip.tcl -tclargs ip_root <ip repo path> --ip_name <vta ip name>
```
## Example

The `ComputeTest.scala` test runs a simulation of the Compute module using a JSON input file. The JSON file specifies the input data, weights, and expected output. The simulation output provides a cycle-by-cycle trace of the Compute module's operation.
