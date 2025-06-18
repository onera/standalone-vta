package cli

import chiseltest.iotesters.PeekPokeTester
import util.Reshape.{reshape, vector_to_map}
import util.{GenericSim, Reshape}
import vta.core.Compute
import vta.util.config.Parameters

class ComputeLenet5(c: Compute, doCompare: Boolean = false, debug: Boolean = true, fromResources: Boolean = false)
  extends PeekPokeTester(c) {

  val computeSimulatorL1 = new ComputeSimulator(c,
    "instructions_L1.bin",
    "uop_L1.bin",
    "input.bin",
    "weight_L1.bin",
    "out_init_L1.bin",
    "accumulator.bin",
    "expected_out.bin", // à générer
    "base_addr_L1.csv", // à générer
    doCompare, debug, fromResources)

  val outL1_vec = computeSimulatorL1.getOutScratchpad.toSeq.sortBy(_._1).flatMap {
    case (_, array) => array
  }.toArray
  val reshaped_outL1 = reshape(outL1_vec, 1, 16, 196, 6, 1, 6, 14, 14, (5, 5), 1, isSquare = true)
  val base_addr_inpL2 = ComputeSimulator.getBaseAddr("base_addr_L2.csv", fromResources = false)
  val reshaped_mapL1 = vector_to_map(reshaped_outL1, base_addr_inpL2("inp"))

  val computeSimulatorL2 = new ComputeSimulator(c,
    "instructions_L2.bin",
    "uop_L2.bin",
    reshaped_mapL1,
    "weight_L2.bin",
    "out_init_L2.bin",
    "accumulator.bin",
    "expected_out.bin", // à générer
    "base_addr_L2.csv", // à générer
    doCompare, debug, fromResources)
}

class ComputeLeNet5_L1_L2 extends GenericSim("ComputeLeNet5_L1_L2", (p:Parameters) =>
  new Compute(false)(p), (c: Compute) => new ComputeLenet5(c))