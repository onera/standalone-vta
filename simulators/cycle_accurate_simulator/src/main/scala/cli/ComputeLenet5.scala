package cli

import chiseltest.iotesters.PeekPokeTester
import util.GenericSim
import vta.core.Compute
import vta.util.config.Parameters

class ComputeLenet5(c: Compute, doCompare: Boolean = false, debug: Boolean = true, fromResources: Boolean = false)
  extends PeekPokeTester(c) {

  val computeSimulatorL1 = new ComputeSimulator(c,
    "instructions_L1.bin",
    "uop_L1.bin",
    "inputL1.bin",
    "weightL1.bin",
    "outL1.bin",
    "accumulator.bin",
    "expected_outL1.bin", // à générer
    "base_addressesL1.csv", // à générer
    doCompare, debug, fromResources)

  val computeSimulatorL2 = new ComputeSimulator(c,
    "instructions_L2.bin",
    "uop_L2.bin",
    computeSimulatorL1.getOutScratchpad,
    "weightL2.bin",
    "outL2.bin",
    "accumulator.bin",
    "expected_outL2.bin", // à générer
    "base_addressesL2.csv", // à générer
    doCompare, debug, fromResources)
}

class ComputeLeNet5_L1_L2 extends GenericSim("ComputeLeNet5_L1_L2", (p:Parameters) =>
  new Compute(false)(p), (c: Compute) => new ComputeLenet5(c))