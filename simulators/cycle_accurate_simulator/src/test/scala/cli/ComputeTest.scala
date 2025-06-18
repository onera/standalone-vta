package cli

import chisel3._
import chiseltest.iotesters._
import unittest.GenericTest
import vta.core.ISA._
import vta.core._
import vta.shell.VMEReadMaster
import vta.util.config.Parameters

import scala.language.postfixOps

class ComputeTest(c: Compute, insn: String, uop: String, input: String, weight: String, out: String, acc: String, expected_out: String,
                  base_addresses: String, doCompare: Boolean = false, debug: Boolean = false, fromResources: Boolean = true)
  extends PeekPokeTester(c) {

  val computeSimulator = new ComputeSimulator(
    c, insn, uop, input, weight, out, acc, expected_out, base_addresses,
    doCompare, debug, fromResources = true)

  computeSimulator.getOutScratchpad.toSeq.sortBy(_._1).foreach { case (key, values) =>
    val hexKey = Integer.toHexString(key.toInt)
    println(s"Logical address (Hex) : ${"0" * (8 - hexKey.length)}$hexKey")
    println(s"Values : ${values.mkString(", ")}")
  }


}


/*************************************************************************************************************
 * TEST EXECUTION
 *************************************************************************************************************/
//class ComputeApp extends GenericTest("ComputeApp", (p:Parameters) =>
//  new Compute(true)(p), (c: Compute) => new ComputeTest(c, "/examples_compute/compute_investigation.json", false))

/* Vector x matrix multiplication (Simple Matrix Multiply) */
class ComputeApp_smm extends GenericTest("ComputeApp_smm", (p:Parameters) =>
  new Compute(false)(p), (c: Compute) => new ComputeTest(c,
  "examples_compute/smm/instructions.bin",
  "examples_compute/smm/uop.bin",
  "examples_compute/smm/input.bin",
  "examples_compute/smm/weight.bin",
  "examples_compute/smm/out.bin",
  "examples_compute/smm/accumulator.bin",
  "examples_compute/smm/expected_out.bin",
  "examples_compute/smm/memory_addresses.csv",
  true))

/* Matrix 16x16 multiply with matrix 16x16 */
class ComputeApp_16x16 extends GenericTest("ComputeApp_16x16", (p:Parameters) =>
  new Compute(false)(p), (c: Compute) => new ComputeTest(c,
  "examples_compute/16x16/instructions.bin",
  "examples_compute/16x16/uop.bin",
  "examples_compute/16x16/input.bin",
  "examples_compute/16x16/weight.bin",
  "examples_compute/16x16/out.bin",
  "examples_compute/16x16/accumulator.bin",
  "examples_compute/16x16/expected_out.bin",
  "examples_compute/16x16/memory_addresses.csv",
  true))

/* Matrix 32x32 multiply with matrix 32x32 */
class ComputeApp_32x32 extends GenericTest("ComputeApp_32x32", (p:Parameters) =>
  new Compute(false)(p), (c: Compute) => new ComputeTest(c,
  "examples_compute/32x32/instructions.bin",
  "examples_compute/32x32/uop.bin",
  "examples_compute/32x32/input.bin",
  "examples_compute/32x32/weight.bin",
  "examples_compute/32x32/out.bin",
  "examples_compute/32x32/accumulator.bin",
  "examples_compute/32x32/expected_out.bin",
  "examples_compute/32x32/memory_addresses.csv",
  true, debug = true, fromResources = true))


///* ALTERNATIVE INSTRUCTION INVESTIGATION:
// * Batches with 2 UOP and 1 GeMM loop */
//class ComputeApp_Batches_2uop_1loop extends GenericTest("ComputeApp_Batches_2uop_1loop", (p:Parameters) =>
//  new Compute(true)(p), (c: Compute) => new ComputeTest(c, "/examples_compute/alternative_instructions/batches_2uop_1loop.json", true))
///* Batches with 1 UOP and 2 GeMM loop */
//class ComputeApp_Batches_1uop_2loops extends GenericTest("ComputeApp_Batches_1uop_2loops", (p: Parameters) =>
//  new Compute(true)(p), (c: Compute) => new ComputeTest(c, "/examples_compute/alternative_instructions/batches_1uop_2loops.json", true))
///* Batches with 2 instructions */
//class ComputeApp_Batches_2insn extends GenericTest("ComputeApp_Batches_2insn", (p: Parameters) =>
//  new Compute(true)(p), (c: Compute) => new ComputeTest(c, "/examples_compute/alternative_instructions/batches_2insn.json", true))
//
///* ALTERNATIVE INSTRUCTION INVESTIGATION:
// * Load 4 UOP using 1 instruction */
//class ComputeApp_LoadUop_1insn extends GenericTest("ComputeApp_LoadUop_1insn", (p: Parameters) =>
//  new Compute(true)(p), (c: Compute) => new ComputeTest(c, "/examples_compute/alternative_instructions/loadUop_1insn.json"))
//class ComputeApp_LoadUop_2insn extends GenericTest("ComputeApp_LoadUop_2insn", (p: Parameters) =>
//  new Compute(true)(p), (c: Compute) => new ComputeTest(c, "/examples_compute/alternative_instructions/loadUop_2insn.json"))


//* ALU
/* ReLU */
class ComputeApp_relu extends GenericTest("ComputeApp_relu", (p:Parameters) =>
  new Compute(false)(p), (c: Compute) => new ComputeTest(c,
  "examples_compute/relu/instructions.bin",
  "examples_compute/relu/uop.bin",
  "examples_compute/relu/input.bin",
  "examples_compute/relu/weight.bin",
  "examples_compute/relu/out.bin",
  "examples_compute/relu/accumulator.bin",
  "examples_compute/relu/expected_out.bin",
  "examples_compute/relu/memory_addresses.csv",
  true))

/* Matrix 16x16 multiply with matrix 16x16 followed by a ReLU (MAX with 0) */
class ComputeApp_16x16_relu extends GenericTest("ComputeApp_16x16_relu", (p:Parameters) =>
  new Compute(false)(p), (c: Compute) => new ComputeTest(c,
  "examples_compute/16x16_relu/instructions.bin",
  "examples_compute/16x16_relu/uop.bin",
  "examples_compute/16x16_relu/input.bin",
  "examples_compute/16x16_relu/weight.bin",
  "examples_compute/16x16_relu/out.bin",
  "examples_compute/16x16_relu/accumulator.bin",
  "examples_compute/16x16_relu/expected_out.bin",
  "examples_compute/16x16_relu/memory_addresses.csv",
  true))

/* Matrix 32x32 multiply with matrix 32x32 followed by a ReLU (MAX with 0) */
class ComputeApp_32x32_relu extends GenericTest("ComputeApp_32x32_relu", (p:Parameters) =>
  new Compute(false)(p), (c: Compute) => new ComputeTest(c,
  "examples_compute/32x32_relu/instructions.bin",
  "examples_compute/32x32_relu/uop.bin",
  "examples_compute/32x32_relu/input.bin",
  "examples_compute/32x32_relu/weight.bin",
  "examples_compute/32x32_relu/out.bin",
  "examples_compute/32x32_relu/accumulator.bin",
  "examples_compute/32x32_relu/expected_out.bin",
  "examples_compute/32x32_relu/memory_addresses.csv",
  true))

///* Average pooling (first part - add only) */
//class ComputeApp_add_acc_vectors extends GenericTest("ComputeApp_add_acc_vectors", (p: Parameters) =>
//  new Compute(true)(p), (c: Compute) => new ComputeTest(c, "/examples_compute/compute_add_acc_vectors.json", true))

/* Average pooling (full - add + division), the division round down */
class ComputeApp_average_pooling extends GenericTest("ComputeApp_average_pooling", (p:Parameters) =>
  new Compute(false)(p), (c: Compute) => new ComputeTest(c,
  "examples_compute/average_pooling/instructions.bin",
  "examples_compute/average_pooling/uop.bin",
  "examples_compute/average_pooling/input.bin",
  "examples_compute/average_pooling/weight.bin",
  "examples_compute/average_pooling/out.bin",
  "examples_compute/average_pooling/accumulator.bin",
  "examples_compute/average_pooling/expected_out_sram.bin",
  "examples_compute/average_pooling/memory_addresses.csv",
  true))

//* CONVOLUTIONAL NEURAL NETWORK:
/* LeNet-5: Convolution 1 */
class ComputeApp_lenet5_conv1 extends GenericTest("ComputeApp_lenet5_conv1", (p:Parameters) =>
  new Compute(true)(p), (c: Compute) => new ComputeTest(c,
  "examples_compute/lenet5_conv1/instructions.bin",
  "examples_compute/lenet5_conv1/uop.bin",
  "examples_compute/lenet5_conv1/input.bin",
  "examples_compute/lenet5_conv1/weight.bin",
  "examples_compute/lenet5_conv1/out.bin",
  "examples_compute/lenet5_conv1/accumulator.bin",
  "examples_compute/lenet5_conv1/expected_out.bin",
  "examples_compute/lenet5_conv1/memory_addresses.csv",
  true),
  true)

/* LeNet-5: Conv1 + ReLU */
class ComputeApp_lenet5_conv1_relu extends GenericTest("ComputeApp_lenet5_conv1_relu", (p:Parameters) =>
  new Compute(true)(p), (c: Compute) => new ComputeTest(c,
  "examples_compute/lenet5_conv1_relu/instructions.bin",
  "examples_compute/lenet5_conv1_relu/uop.bin",
  "examples_compute/lenet5_conv1_relu/input.bin",
  "examples_compute/lenet5_conv1_relu/weight.bin",
  "examples_compute/lenet5_conv1_relu/out.bin",
  "examples_compute/lenet5_conv1_relu/accumulator.bin",
  "examples_compute/lenet5_conv1_relu/expected_out.bin",
  "examples_compute/lenet5_conv1_relu/memory_addresses.csv",
  true),
  true)

/* LeNet-5: Conv1 + ReLU + Average Pooling */
class ComputeApp_lenet5_layer1 extends GenericTest("ComputeApp_lenet5_layer1", (p:Parameters) =>
  new Compute(true)(p), (c: Compute) => new ComputeTest(c,
  "examples_compute/lenet5_layer1/instructions.bin",
  "examples_compute/lenet5_layer1/uop.bin",
  "examples_compute/lenet5_layer1/input.bin",
  "examples_compute/lenet5_layer1/weight.bin",
  "examples_compute/lenet5_layer1/out.bin",
  "examples_compute/lenet5_layer1/accumulator.bin",
  "examples_compute/lenet5_layer1/expected_out_sram.bin",
  "examples_compute/lenet5_layer1/memory_addresses.csv",
  true),
  true)