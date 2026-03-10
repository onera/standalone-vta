# Cycle-Accurate Simulator (CHISEL)

This directory contains the CHISEL cycle-accurate simulator for the VTA. This simulator provides a detailed, cycle-by-cycle model of the VTA's hardware behaviour.

## Prerequisites

There are two options to build the project: SBT or mill

### SBT

In order to build with SBT, you need to install:

- a **Java Development Kit (JDK):** Required for running Scala and SBT.
- the **Scala Build Tool (SBT):** Used for building and running the CHISEL project.

### Mill

Alternatively, to use mill, you need to install:

- coursier [https://get-coursier.io/docs/cli-installation]

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
mill _.compile
```

## Running Simulations

1. **Choose a test case:** The `src/test/scala/simulatorTest` directory contains simulation testbenches that execute JSON files located in `src/test/resources/`.
2. **Execute the test:**

   ```bash
   sbt "testOnly <test_name>"
   ```

   ```bash
   mill test.testOnly <test_name>
   ```

   Replace `<test_name>` with the fully qualified name of the test you want to run. For example:

   ```bash
   sbt "testOnly simulator.ComputeApp"
   ```

   ```bash
   mill test.testOnly simulator.ComputeApp
   ```

## Full VTA simulation

A simulation can be run on the entire VTA (VCR+VME+Core) that initializes an external memory (mocking the external DRAM) by providing a DRAM initialization file in a JSON format (for example [dram_state.json](src/test/resouces/examples_shell/dram_state.json))

To execute this simulation, run:

```bash
mill runMain cli.VTAShellSimulator <mem init file> <output dir>
```

```bash
sbt "runMain cli.VTAShellSimulator <mem init file> <output dir>"
```

The [VTAShellSpec.scala](src/test/scala/shell/VTAShellSpec.scala) file contains a simulation test in `src/resources/examples_shell/dram_state.json`

## Example

The `ComputeTest.scala` test runs a simulation of the Compute module using a JSON input file. The JSON file specifies the input data, weights, and expected output. The simulation output provides a cycle-by-cycle trace of the Compute module's operation.
