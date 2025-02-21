# Cycle-Accurate Simulator (CHISEL)

This directory contains the CHISEL cycle-accurate simulator for the VTA.  This simulator provides a detailed, cycle-by-cycle model of the VTA's hardware behaviour.

## Prerequisites

*   **Java Development Kit (JDK):** Required for running Scala and SBT.
*   **Scala Build Tool (SBT):** Used for building and running the CHISEL project.
*   **CHISEL 6.0**
*   **Scala 2.13.12**

## Directory Structure

*   `src/main/scala/`: Contains the CHISEL hardware description of the VTA.
*   `src/test/scala/`: Contains the simulation testbenches.
    *   `src/test/scala/formal/`: Formal verification code.
    *   `src/test/scala/simulator/`: Simulation code for executing JSON test files and obtaining step-by-step execution traces.
    *   `src/test/scala/unittest/`: Simple functional unit tests.
*   `src/test/resources/`: JSON files used as input for the simulator.

## Building

1.  **Navigate to the `cycle_accurate_simulator` directory.**
2.  **Run SBT:**
    ```
    sbt compile
    ```

## Running Simulations

1.  **Choose a test case:**  The `src/test/scala/simulator/` directory contains simulation testbenches that execute JSON files located in `src/test/resources/`.
2.  **Execute the test:**  Use SBT to run the desired test.

    ```
    sbt "testOnly <test_name>"
    ```

    Replace `<test_name>` with the fully qualified name of the test you want to run.  For example:

    ```
    sbt "testOnly simulator.ComputeApp"
    ```

## Example

The `ComputeTest.scala` test runs a simulation of the Compute module using a JSON input file.  The JSON file specifies the input data, weights, and expected output.  The simulation output provides a cycle-by-cycle trace of the Compute module's operation.
