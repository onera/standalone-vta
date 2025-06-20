package cli

import chiseltest.iotesters.PeekPokeTester
import util.Reshape.{reshape, vector_to_map}
import util.{GenericSim, Reshape}
import vta.core.Compute
import vta.util.config.Parameters

class ComputeLenet5(c: Compute, doCompare: Boolean = true, debug: Boolean = true, fromResources: Boolean = false)
  extends PeekPokeTester(c) {

  // Executing layer1 of LeNet-5
  val computeSimulatorL1 = new ComputeSimulator(c,
    "instructions_L1.bin",
    "uop_L1.bin",
    "input.bin",
    "weight_L1.bin",
    "out_init_L1.bin",
    "accumulator.bin",
    "outL1_sram.bin",
    "base_addr_L1.csv", // à générer
    doCompare, debug, fromResources)

  // Reshaping output layer1
  val outL1_vec = computeSimulatorL1.getOutScratchpad.toSeq.sortBy(_._1).flatMap {
    case (_, array) => array
  }.toArray
  val reshaped_outL1 = reshape(outL1_vec, 1, 16, 196, 6, 1, 6, 14, 14, (5, 5), 1, isSquare = true)
  val base_addr_inpL2 = ComputeSimulator.getBaseAddr("base_addr_L2.csv", fromResources = false)
  val reshaped_mapL1 = vector_to_map(reshaped_outL1, base_addr_inpL2("inp"))

  // test pour checker si reshaped_out = inpL2 ? mettre dans computeSimulator et utiliser un get ou un compare

  // Executing layer2 of LeNet-5
  val computeSimulatorL2 = new ComputeSimulator(c,
    "instructions_L2.bin",
    "uop_L2.bin",
    reshaped_mapL1,
    "weight_L2.bin",
    "out_init_L2.bin",
    "accumulator.bin",
    "outL2_sram.bin",
    "base_addr_L2.csv", // à générer
    doCompare, debug, fromResources)

  // Reshaping output layer2
  val outL2_vec = computeSimulatorL2.getOutScratchpad.toSeq.sortBy(_._1).flatMap {
    case (_, array) => array
  }.toArray
  val reshaped_outL2 = reshape(outL2_vec, 1, 16, 25, 16, 1, 16, 5, 5, (5, 5), 1, isSquare = false)
  val base_addr_inpL3 = ComputeSimulator.getBaseAddr("base_addr_L3.csv", fromResources = false)
  val reshaped_mapL2 = vector_to_map(reshaped_outL2, base_addr_inpL3("inp"))

  // test pour checker si reshaped_out = inpL3 ?

  // Executing layer3 of LeNet-5
  val computeSimulatorL3 = new ComputeSimulator(c,
    "instructions_L3.bin",
    "uop_L3.bin",
    reshaped_mapL2,
    "weight_L3.bin",
    "out_init_L3.bin",
    "accumulator.bin",
    "outL3.bin",
    "base_addr_L3.csv", // à générer
    doCompare, debug, fromResources)

  val output_L3 = computeSimulatorL3.getOutScratchpad

  // Executing layer4 of LeNet-5
  val computeSimulatorL4 = new ComputeSimulator(c,
    "instructions_L4.bin",
    "uop_L4.bin",
    output_L3,
    "weight_L4.bin",
    "out_init_L4.bin",
    "accumulator.bin",
    "outL4.bin",
    "base_addr_L4.csv", // à générer
    doCompare, debug, fromResources)

  val output_L4 = computeSimulatorL4.getOutScratchpad

  // Executing layer5 of LeNet-5
  val computeSimulatorL5 = new ComputeSimulator(c,
    "instructions_L5.bin",
    "uop_L5.bin",
    output_L4,
    "weight_L5.bin",
    "out_init_L5.bin",
    "accumulator.bin",
    "outL5.bin",
    "base_addr_L5.csv", // à générer
    doCompare, debug, fromResources)

}

class ComputeLeNet5_L1_L2 extends GenericSim("ComputeLeNet5_L1_L2", (p:Parameters) =>
  new Compute(false)(p), (c: Compute) => new ComputeLenet5(c))