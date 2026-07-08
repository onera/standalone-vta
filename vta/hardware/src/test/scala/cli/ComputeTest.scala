package cli

import vta.configs.DefaultPynqConfig
import vta.core._
import vta.tags
import vta.util.AnyFlatSpecSim
import vta.util.config.Parameters

trait ComputeTest extends AnyFlatSpecSim {

  implicit val param: Parameters = new DefaultPynqConfig
  def computeSimulation(
    insn: String,
    uop: String,
    input: String,
    weight: String,
    out: String,
    acc: String,
    expected: String,
    memoryAddr: String,
    doCompare: Boolean = false,
    debug: Boolean = false,
    fromResources: Boolean = true
  ) = {

    // The 32x32 tests rely on the acc scratchpad (a memory) powering up zeroed,
    // so only memory randomization is disabled; register randomization stays on.
    // FIXME: proper fix is to reset/load the acc buffer in those fixtures.
    simulate(new Compute, firtoolOpts = Array("--disable-mem-randomization")) {
      c =>
        new ComputeSimulator(
          c,
          insn,
          uop,
          input,
          weight,
          out,
          acc,
          expected_out = expected,
          memoryAddr,
          doCompare,
          debug,
          fromResources
        )
    }
  }
}

@tags.UnitTests
class ComputeTests extends ComputeTest {
  behavior of "Compute"

  it should "execute a simple vector matrix multiplication" in computeSimulation(
    insn = "examples_compute/smm/instructions.bin",
    uop = "examples_compute/smm/uop.bin",
    input = "examples_compute/smm/input.bin",
    weight = "examples_compute/smm/weight.bin",
    out = "examples_compute/smm/out.bin",
    acc = "examples_compute/smm/accumulator.bin",
    expected = "examples_compute/smm/expected_out.bin",
    memoryAddr = "examples_compute/smm/memory_addresses.csv",
    doCompare = false,
    debug = false
  )

  it should "execute a 16x16 matrix multiplication" in computeSimulation(
    insn = "examples_compute/16x16/instructions.bin",
    uop = "examples_compute/16x16/uop.bin",
    input = "examples_compute/16x16/input.bin",
    weight = "examples_compute/16x16/weight.bin",
    out = "examples_compute/16x16/out.bin",
    acc = "examples_compute/16x16/accumulator.bin",
    expected = "examples_compute/16x16/expected_out.bin",
    memoryAddr = "examples_compute/16x16/memory_addresses.csv",
    doCompare = true,
    debug = false
  )

  it should "execute a 32x32 matrix multiplication" in computeSimulation(
    insn = "examples_compute/32x32/instructions.bin",
    uop = "examples_compute/32x32/uop.bin",
    input = "examples_compute/32x32/input.bin",
    weight = "examples_compute/32x32/weight.bin",
    out = "examples_compute/32x32/out.bin",
    acc = "examples_compute/32x32/accumulator.bin",
    expected = "examples_compute/32x32/expected_out.bin",
    memoryAddr = "examples_compute/32x32/memory_addresses.csv",
    doCompare = true,
    debug = false,
    fromResources = true
  )

  it should "execute a ReLU" in computeSimulation(
    insn = "examples_compute/relu/instructions.bin",
    uop = "examples_compute/relu/uop.bin",
    input = "examples_compute/relu/input.bin",
    weight = "examples_compute/relu/weight.bin",
    out = "examples_compute/relu/out.bin",
    acc = "examples_compute/relu/accumulator.bin",
    expected = "examples_compute/relu/expected_out.bin",
    memoryAddr = "examples_compute/relu/memory_addresses.csv",
    doCompare = true
  )

  /* Matrix 16x16 multiply with matrix 16x16 followed by a ReLU (MAX with 0) */
  it should "execute a 16x16 matrix multiplication then a ReLU" in computeSimulation(
    insn = "examples_compute/16x16_relu/instructions.bin",
    uop = "examples_compute/16x16_relu/uop.bin",
    input = "examples_compute/16x16_relu/input.bin",
    weight = "examples_compute/16x16_relu/weight.bin",
    out = "examples_compute/16x16_relu/out.bin",
    acc = "examples_compute/16x16_relu/accumulator.bin",
    expected = "examples_compute/16x16_relu/expected_out.bin",
    memoryAddr = "examples_compute/16x16_relu/memory_addresses.csv",
    doCompare = true
  )

  /* Matrix 32x32 multiply with matrix 32x32 followed by a ReLU (MAX with 0) */
  it should "execute a 32x32 matrix multiplication then a ReLU" in computeSimulation(
    insn = "examples_compute/32x32_relu/instructions.bin",
    uop = "examples_compute/32x32_relu/uop.bin",
    input = "examples_compute/32x32_relu/input.bin",
    weight = "examples_compute/32x32_relu/weight.bin",
    out = "examples_compute/32x32_relu/out.bin",
    acc = "examples_compute/32x32_relu/accumulator.bin",
    expected = "examples_compute/32x32_relu/expected_out.bin",
    memoryAddr = "examples_compute/32x32_relu/memory_addresses.csv",
    doCompare = true
  )

  /* Average pooling (full - add + division), the division round down */
  it should "compute an average_pooling" in computeSimulation(
    insn = "examples_compute/average_pooling/instructions.bin",
    uop = "examples_compute/average_pooling/uop.bin",
    input = "examples_compute/average_pooling/input.bin",
    weight = "examples_compute/average_pooling/weight.bin",
    out = "examples_compute/average_pooling/out.bin",
    acc = "examples_compute/average_pooling/accumulator.bin",
    expected = "examples_compute/average_pooling/expected_out_sram.bin",
    memoryAddr = "examples_compute/average_pooling/memory_addresses.csv",
    doCompare = true
  )
}

/** ***********************************************************************************************************
  * TEST EXECUTION
  */

// LENET-5
@tags.LongTests
class ComputeTestLeNet5 extends ComputeTest {
  /* LeNet-5: Convolution 1 */
  it should "ComputeApp_lenet5_conv1" in computeSimulation(
    insn = "examples_compute/lenet5_conv1/instructions.bin",
    uop = "examples_compute/lenet5_conv1/uop.bin",
    input = "examples_compute/lenet5_conv1/input.bin",
    weight = "examples_compute/lenet5_conv1/weight.bin",
    out = "examples_compute/lenet5_conv1/out.bin",
    acc = "examples_compute/lenet5_conv1/accumulator.bin",
    expected = "examples_compute/lenet5_conv1/expected_out.bin",
    memoryAddr = "examples_compute/lenet5_conv1/memory_addresses.csv",
    doCompare = true
  )

  /* LeNet-5: Conv1 + ReLU */
  it should "ComputeApp_lenet5_conv1_relu" in computeSimulation(
    insn = "examples_compute/lenet5_conv1_relu/instructions.bin",
    uop = "examples_compute/lenet5_conv1_relu/uop.bin",
    input = "examples_compute/lenet5_conv1_relu/input.bin",
    weight = "examples_compute/lenet5_conv1_relu/weight.bin",
    out = "examples_compute/lenet5_conv1_relu/out.bin",
    acc = "examples_compute/lenet5_conv1_relu/accumulator.bin",
    expected = "examples_compute/lenet5_conv1_relu/expected_out.bin",
    memoryAddr = "examples_compute/lenet5_conv1_relu/memory_addresses.csv",
    doCompare = true
  )

  it should "ComputeApp_lenet5_layer1" in computeSimulation(
    insn = "examples_compute/lenet5_layer1/instructions.bin",
    uop = "examples_compute/lenet5_layer1/uop.bin",
    input = "examples_compute/lenet5_layer1/input.bin",
    weight = "examples_compute/lenet5_layer1/weight.bin",
    out = "examples_compute/lenet5_layer1/out.bin",
    acc = "examples_compute/lenet5_layer1/accumulator.bin",
    expected = "examples_compute/lenet5_layer1/expected_out_sram.bin",
    memoryAddr = "examples_compute/lenet5_layer1/memory_addresses.csv",
    doCompare = true
  )
}

// PERFORMANCE TESTS: 16x16 GeMM
/* Binaries from VTA compiler */
@tags.LongTests
class PerformanceComputeTests extends ComputeTest {
  behavior of "ComputePerfo"

  /* LeNet-5: Conv1 + ReLU + Average Pooling */
  it should "PerfCompute0_gemm_16x16_vta_compiler" in computeSimulation(
    insn =
      "examples_compute/performance_tests/gemm_16x16_vta_compiler/instructions.bin",
    uop = "examples_compute/performance_tests/gemm_16x16_vta_compiler/uop.bin",
    input = "examples_compute/performance_tests/input.bin",
    weight = "examples_compute/performance_tests/weight.bin",
    out = "examples_compute/performance_tests/out_init.bin",
    acc = "examples_compute/performance_tests/accumulator.bin",
    expected = "examples_compute/performance_tests/expected_out_sram.bin",
    memoryAddr = "examples_compute/performance_tests/memory_addresses.csv",
    doCompare = false,
    debug = false
  )
  /* No reset, No loadAcc, 16 loadUop, 1 loop, 16 UOP */
  it should "PerfCompute1_gemm_16x16_with_1loop_16uop_16loaduop" in computeSimulation(
    insn =
      "examples_compute/performance_tests/gemm_16x16_with_1loop_16uop_16loaduop/instructions.bin",
    uop =
      "examples_compute/performance_tests/gemm_16x16_with_1loop_16uop_16loaduop/uop.bin",
    input = "examples_compute/performance_tests/input.bin",
    weight = "examples_compute/performance_tests/weight.bin",
    out = "examples_compute/performance_tests/out_init.bin",
    acc = "examples_compute/performance_tests/accumulator.bin",
    expected = "examples_compute/performance_tests/expected_out_sram.bin",
    memoryAddr = "examples_compute/performance_tests/memory_addresses.csv",
    doCompare = false,
    debug = false
  )

  /* No reset, No loadAcc, 16 loadUop, 16 loop, 1 UOP */
  it should "PerfCompute2_gemm_16x16_with_16loop_1uop_16loaduop" in computeSimulation(
    insn =
      "examples_compute/performance_tests/gemm_16x16_with_16loop_1uop_16loaduop/instructions.bin",
    uop =
      "examples_compute/performance_tests/gemm_16x16_with_16loop_1uop_16loaduop/uop.bin",
    input = "examples_compute/performance_tests/input.bin",
    weight = "examples_compute/performance_tests/weight.bin",
    out = "examples_compute/performance_tests/out_init.bin",
    acc = "examples_compute/performance_tests/accumulator.bin",
    expected = "examples_compute/performance_tests/expected_out_sram.bin",
    memoryAddr = "examples_compute/performance_tests/memory_addresses.csv",
    doCompare = false,
    debug = false
  )

  /* No reset, No loadAcc, 1 loadUop, 16 loop, 1 UOP */
  it should "PerfCompute3_gemm_16x16_with_16loop_1_uop_1loaduop" in computeSimulation(
    insn =
      "examples_compute/performance_tests/gemm_16x16_with_16loop_1_uop_1loaduop/instructions.bin",
    uop =
      "examples_compute/performance_tests/gemm_16x16_with_16loop_1_uop_1loaduop/uop.bin",
    input = "examples_compute/performance_tests/input.bin",
    weight = "examples_compute/performance_tests/weight.bin",
    out = "examples_compute/performance_tests/out_init.bin",
    acc = "examples_compute/performance_tests/accumulator.bin",
    expected = "examples_compute/performance_tests/expected_out_sram.bin",
    memoryAddr = "examples_compute/performance_tests/memory_addresses.csv",
    doCompare = false,
    debug = false
  )

}
