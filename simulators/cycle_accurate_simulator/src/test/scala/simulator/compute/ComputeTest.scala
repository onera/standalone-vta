package simulator.compute

import chisel3._
import chisel3.util._
import chiseltest._
import chiseltest.formal._
import chiseltest.experimental.observe
import chiseltest.simulator.WriteVcdAnnotation
import org.scalatest.flatspec.AnyFlatSpec
import _root_.circt.stage.ChiselStage

import chiseltest.iotesters._
import com.fasterxml.jackson.databind.ObjectMapper
import com.fasterxml.jackson.module.scala.DefaultScalaModule
import scala.io._
import scala.language.postfixOps

import unittest.GenericTest
import vta.core._
import vta.shell.VMEReadMaster
import vta.util.config.Parameters

class ComputeTest(c: Compute, fn: String = "/x.json", doCompare: Boolean = false)
  extends PeekPokeTester(c) {

  // Print the test name
  print("\nTEST NAME: \n\t ComputeInvestigation (take a JSON in input)\n")
  print(s"\tJSON: ${fn} \n\n")


  /* COMMON PART - MANAGE VIRTUAL MEMORIES */
  // READ the JSON file
  val bufferedSource = Source.fromURL(getClass.getResource(fn))
  val mapper = new ObjectMapper()
  mapper.registerModule(DefaultScalaModule)
  val archState = mapper.readValue(bufferedSource.reader(), classOf[Map[String, Object]])
  bufferedSource.close

  // DECODE the INSTRUCTIONS
  def instruction_scratchpad(tag: String): Map[String, BigInt] = {
    // Read the JSON file
    val instMap = archState(tag).asInstanceOf[Map[String, String]]
    // Associate each instruction to a key
    instMap.map { case (key, value) =>
      key -> BigInt(value, 16)
    }
  }
  // Create the instruction scratchpad
  val inst = instruction_scratchpad("inst")
  // Order the keys of the instructions (to have I0 before I1, ...)
  val sortedInst = inst.keys.toList.sortBy(key => key.substring(1).toInt)
//  for (key <- sortedInst) {
//    print(s"$key \n")
//  }

  // Scratchpad memory (emulate the buffers / registers)
  def build_scratchpad(tag: String): Map[BigInt, Array[BigInt]] = {
    val arr = archState(tag).asInstanceOf[Seq[Map[String, Object]]]
    (
      for {m <- arr} yield {
        val idx = BigInt(m("idx").asInstanceOf[String], 16)
        val vec = m("vec").asInstanceOf[Seq[String]]
        idx -> (
          for {v <- vec} yield {
            BigInt(v, 16)
          }
          ).toArray
      }
      ).toMap
  }

  // Print scratchpad
  def print_scratchpad(scratchpad: Map[BigInt, Array[BigInt]], index: BigInt, name : String = "?"): Unit = {
    print(s"\n ${name} scratchpad (index: ${index}) = \n (")
    for {i <- scratchpad(index).indices} {
      print(s"${scratchpad(index)(i).toByte}")
      if (i != scratchpad(index).size - 1) {
        print(", ")
      }
    }
    print(") \n\n")
  }

  // Compare scratchpad
  def compare_scratchpad(reference: Map[BigInt, Array[BigInt]], scratchpadUnderTest: Map[BigInt, Array[BigInt]]): Unit = {
    val availableIndexes = reference.keySet.toSeq.sorted
    var noDifference = true
    for (index <- availableIndexes) {
      for (i <- reference(index).indices) {
        if (reference(index)(i).toByte != scratchpadUnderTest(index)(i).toByte) {
          noDifference = false
          print(s"\n\nERROR: difference between result and expectation at index:${index} position:${i}\n")
          print(s"\t Expected = ${reference(index)(i).toByte}, Obtained = ${scratchpadUnderTest(index)(i).toByte}")
        }
      }
    }
    assert(noDifference)
    print("\n\t Output match expectation!\n")
  }

  /* DEFINE GLOBAL VARIABLE */
  // Set the cycle counter to 0
  var cycle_counter = 0
  /* END GLOBAL VARIABLE */

  /* REDEFINE THE STEP FUNCTION */
  // cycle_step function
  def cycle_step() = {
    cycle_counter = cycle_counter + 1
    print(s"\n\nCycle ${cycle_counter}:\n")
    step(1)
  }

  /* Function to loop for each instructions */
  def loop(prev_signal: Boolean, next_signal: Boolean): Unit = {
    val end = 10000 // Timeout
    var count = 0
    // Set the input semaphore
    poke(c.io.i_post(0), prev_signal)
    poke(c.io.i_post(1), next_signal)
    // Loop (step + 1)
    while (peek(c.io.finish) == 0 && count < end) {
      mocks.logical_step()
      poke(c.io.inst.valid, 0)
      count += 1
    }
    // Check if operation is done or if it is a timeout
    expect(c.io.finish, 1) // Operation is done
    // Add a step to execute the finish state
    cycle_step()
  }

  /* DEFINE THE MOCKS */
  // Emulate a READ access to the data buffer
  class TensorMasterMockRd(tm: TensorMaster, scratchpad: Map[BigInt, Array[BigInt]]) {
    // Unset the data validity signal
    poke(tm.rd(0).data.valid, 0)

    // Check the index validity
    var valid = peek(tm.rd(0).idx.valid)
    var idx: Int = 0

    def logical_step(): Unit = {
      // If index is valid
      if (valid == 1) {
        // Set the data validity signal
        poke(tm.rd(0).data.valid, 1)

//        print(s"\n\nDEBUG: READ SCRATCHPAD IDX: ${idx}\n\n")

        // Go through the scratchpad and send the data
        val cols = tm.rd(0).data.bits(0).size
        for {
          i <- 0 until tm.rd(0).data.bits.size
          j <- 0 until cols
        } {
          poke(tm.rd(0).data.bits(i)(j), scratchpad(idx)(i * cols + j))
        }
      } else { // If index is not valid => data is not valid
        poke(tm.rd(0).data.valid, 0)
      }
      // Update the values
      valid = peek(tm.rd(0).idx.valid)
      idx = peek(tm.rd(0).idx.bits).toInt
    }
  }

  // Emulate a WRITE access to the OUTPUT buffer (scratchpad)
  class TensorMasterMockWr(tm: TensorMaster, scratchpad: Map[BigInt, Array[BigInt]]) {
    def logical_step(): Unit = {
      // If data is valid
      if (peek(tm.wr(0).valid) == 1) {
        // Write into the scratchpad the signal
        val idx = peek(tm.wr(0).bits.idx).toInt
        val cols = tm.wr(0).bits.data(0).size
        for {
          i <- 0 until tm.wr(0).bits.data.size
          j <- 0 until cols
        } {
          scratchpad(idx)(i * cols + j) = peek(tm.wr(0).bits.data(i)(j))
        }
        // Print the scratchpad after the update
        print_scratchpad(out_scratchpad, idx, "OUT")
      }
    }
  }

  // Emulate a READ access to the DRAM by the LoadUop
  class DramUopMockRd(dm: VMEReadMaster, scratchpad: Map[BigInt, Array[BigInt]]) {
    // Store VME_RD information
    var tag = BigInt("00", 16)
    var len = BigInt("00", 16)
    var addr = BigInt("00000000", 16)

    // Exchange data
    var uop_exchange = false
    var nb_uop = 0

    // Exchange between DRAM (slave) and LoadUop (master)
    def logical_step() : Unit = {
      //  Data is not valid yet
      poke(dm.data.valid, 0)
      // Check if command is ready
      var valid = peek(dm.cmd.valid)

      // Configure if DRAM is ready to receive the command
      if (!uop_exchange){ // No exchange in progress, DRAM is ready
        poke(dm.cmd.ready, 1)
      }
      else { // Exchange in progress, DRAM not ready
        poke(dm.cmd.ready, 0)
      }
      // Check if command is ready to receive the data
      var ready = peek(dm.data.ready)

//      print(s"\n\nDEBUG: (UOP) CMD VALID: ${valid}, DATA READY: ${ready}")
//      print(s"\nDEBUG: tag: ${peek(dm.cmd.bits.tag)}, len: ${peek(dm.cmd.bits.len)}, addr: ${peek(dm.cmd.bits.addr)}\n\n")

      // Read the command if command is valid and DRAM ready to receive (no exchange in progress)
      if (valid == 1 && !uop_exchange) {
        // Store the command
        tag = peek(dm.cmd.bits.tag)
        len = peek(dm.cmd.bits.len)
        addr = peek(dm.cmd.bits.addr)

//        print(s"\n\nDEBUG: (UOP) STORE TAG, LEN, ADDR\n\n")

        // Start the exchange
        uop_exchange = true
      }

      // Send data if command is ready to receive and exchange is started
      if (ready == 1 && uop_exchange) {
        // Return the tag to link the data to the command
        poke(dm.data.bits.tag, tag)

//        print(s"\n\nDEBUG: uop_exchange (${nb_uop}) with: tag=${tag}, len=${len}, addr=${addr}" +
//          s"\n (Current addr: ${addr + 8 * nb_uop})\n\n")

        // Read the data from the scratchpad (2 UOP read at once)
        val uop_acc_0 = scratchpad(addr + 8 * nb_uop)(0) // 11 bits
        val uop_inp_0 = scratchpad(addr + 8 * nb_uop)(1) // 11 bits
        val uop_wgt_0 = scratchpad(addr + 8 * nb_uop)(2) // 10 bits
        // Read the second UOP
        val uop_acc_1 = scratchpad(addr + 8 * nb_uop + 4)(0)
        val uop_inp_1 = scratchpad(addr + 8 * nb_uop + 4)(1)
        val uop_wgt_1 = scratchpad(addr + 8 * nb_uop + 4)(2)

        // Assemble the data in one 64-word // uop_val = 64-bit ("FEDCBA9876543210")
        val uop_val = (// 64 bits = 2 x 32-bit UOP
          // Extend uop_wgt_1 to 64 bits, keep the 10 LSB (& 0x3FF), and shift it to the right position
          ((uop_wgt_1.toLong & 0x3FF) << 54) |
            ((uop_inp_1.toLong & 0x7FF) << 43) |
            ((uop_acc_1.toLong & 0x7FF) << 32) |
            ((uop_wgt_0.toLong & 0x3FF) << 22) |
            ((uop_inp_0.toLong & 0x7FF) << 11) |
            (uop_acc_0.toLong & 0x7FF)
          )

        // Send the data and increment the number of exchange
        poke(dm.data.bits.data, uop_val)
        nb_uop = nb_uop + 1

        // If number of exchange is greater than LEN, then end of the exchange
        if (nb_uop > len) {
          // Last data
          poke(dm.data.bits.last, 1)
          // End of the exchange
          uop_exchange = false

//          print(s"\n\nDEBUG: END UOP EXCHANGE: nb_uop=${nb_uop}\n\n")

          // Reset the number of exchange
          nb_uop = 0
        }
        else { // Exchange in progress, not the last data
          poke(dm.data.bits.last, 0)
        }
        // Data is valid
        poke(dm.data.valid, 1)
      } // End case send data
      else{ // No data send, data not valid
        poke(dm.data.valid, 0)
      }
    }

  }

  // Emulate a READ access to the DRAM by the TensorAcc
  class DramAccMockRd(dm: VMEReadMaster, scratchpad: Map[BigInt, Array[BigInt]]) {
    // Store VME_RD information
    var tag = BigInt("00", 16)
    var len = BigInt("00", 16)
    var addr = BigInt("00000000", 16)

    // Exchange data
    var acc_exchange = false
    var nb_acc = 0

    // Exchange between DRAM (slave) and TensorAcc (master)
    def logical_step(): Unit = {
      // Data is not valid yet
      poke(dm.data.valid, 0)
      // Check if command is ready
      var valid = peek(dm.cmd.valid)

      // Configure if DRAM is ready to receive the command
      if (!acc_exchange) { // No exchange in progress, DRAM is ready
        poke(dm.cmd.ready, 1)
      }
      else { // Exchange in progress, DRAM not ready
        poke(dm.cmd.ready, 0)
      }
      // Check if command is ready to receive the data
      var ready = peek(dm.data.ready)

//      print(s"\n\nDEBUG: (ACC) CMD VALID: ${valid}, DATA READY: ${ready}")
//      print(s"\nDEBUG: tag: ${peek(dm.cmd.bits.tag)}, len: ${peek(dm.cmd.bits.len)}, addr: ${peek(dm.cmd.bits.addr)}\n\n")

      // Read the command if command is valid and DRAM ready to receive (no exchange in progress)
      if (valid == 1 && !acc_exchange) {
        // Store the command
        tag = peek(dm.cmd.bits.tag)
        len = peek(dm.cmd.bits.len)
        addr = peek(dm.cmd.bits.addr)

//        print(s"\n\nDEBUG: (ACC) STORE TAG, LEN, ADDR\n\n")

        // Start the exchange
        acc_exchange = true
      }

      // Send data if command is ready to receive and exchange is started
      if (ready == 1 && acc_exchange) {
        // Return the tag to link the data to the command
        poke(dm.data.bits.tag, tag)

//        print(s"\n\nDEBUG: acc_exchange (${nb_acc}) with: tag=${tag}, len=${len}, addr=${addr}" +
//          s"\n (Current addr: ${addr + 64*(nb_acc/8)}, current idx: ${2*(nb_acc%8)} and ${1 + 2*(nb_acc%8)}) \n\n")

        // Read the data from the scratchpad
        val acc_0 = scratchpad(addr + 64*(nb_acc/8))(0 + 2*(nb_acc%8)) // 32 bits
        val acc_1 = scratchpad(addr + 64*(nb_acc/8))(1 + 2*(nb_acc%8))

        // Assemble the data in one 64-word
        val acc_val = (
          ((acc_1.toLong & 0xFFFFFFFFL) << 32) | // L after the mask to cast mask in long
            (acc_0.toLong & 0xFFFFFFFFL)
          )

        // Send the data and increment the number of exchange
        poke(dm.data.bits.data, acc_val)
        nb_acc = nb_acc + 1

        // If number of exchange is greater than LEN, then end of the exchange
        if (nb_acc > len) {
          // Last data
          poke(dm.data.bits.last, 1)
          // End of the exchange
          acc_exchange = false

//          print(s"\n\nDEBUG: END ACC EXCHANGE: nb_acc=${nb_acc}\n\n")

          // Reset the number of exchange
          nb_acc = 0
        }
        else { // Exchange in progress, not the last data
          poke(dm.data.bits.last, 0)
        }
        // Data is valid
        poke(dm.data.valid, 1)
      } // End case send data
      else { // No data send, data not valid
        poke(dm.data.valid, 0)
      }
    }

  }

  // Emulate memory behaviour
  class Mocks {
    val dram_uop_mock = new DramUopMockRd(c.io.vme_rd(0), dram_scratchpad)
    val dram_acc_mock = new DramAccMockRd(c.io.vme_rd(1), dram_scratchpad)
    val inp_mock = new TensorMasterMockRd(c.io.inp, inp_scratchpad)
    val wgt_mock = new TensorMasterMockRd(c.io.wgt, wgt_scratchpad)
    val out_mock = new TensorMasterMockRd(c.io.out, out_scratchpad)
    val out_mock_wr = new TensorMasterMockWr(c.io.out, out_scratchpad)

    // Emulate the clock
    // Print the data in this function!
    def logical_step() : Unit = {
      // Increment the clock
      cycle_step()

      // Perform the action of each element
      dram_acc_mock.logical_step()
      dram_uop_mock.logical_step()
      inp_mock.logical_step()
      wgt_mock.logical_step()
      out_mock.logical_step()
      out_mock_wr.logical_step()

      // Unset valid signal
      poke(c.io.inst.valid, 0)
    }
  }
  /* END COMMON PART - MANAGE VIRTUAL MEMORIES */

  /* BEGIN USER CUSTOMABLE SECTION */
  // Build memory
  val dram_scratchpad = build_scratchpad("dram")
  val inp_scratchpad = build_scratchpad("inp")
  val wgt_scratchpad = build_scratchpad("wgt")
  val out_scratchpad = build_scratchpad("out")
  val out_expect_scratchpad = build_scratchpad("out_expect") // Expected

  // Create the mocks
  val mocks = new Mocks

  // Define the base addresses of UOP and ACC in DRAM (addr: idx*data_size + baddr)
  val uop_baddr = BigInt("00000000",16) // We do not take any offset
  poke(c.io.uop_baddr, uop_baddr)
  val acc_baddr = BigInt("00000000", 16) // We do not take any offset
  poke(c.io.acc_baddr, acc_baddr)

  // Print cycle 0
  print(s"\nCycle ${cycle_counter}:\n")

  // Send instructions
  for (key <- sortedInst) {
    // Send the instruction
    poke(c.io.inst.bits, inst(key))
    // Instruction is valid
    poke(c.io.inst.valid, 1)
    print(s"Send instruction: ${key}\n")
    // Increment the step
    mocks.logical_step()
  }

  // Loop until is finish
  loop(true, true)

  // Check the result
  if (doCompare) {
    compare_scratchpad(out_expect_scratchpad, out_scratchpad)
  }

  print(s"\n\t END COMPUTE TESTS! \n\t (done in ${cycle_counter} cycles)\n\n")
}


/*************************************************************************************************************
 * TEST EXECUTION
 *************************************************************************************************************/

/* Test JSON files */
class ComputeApp extends GenericTest("ComputeApp", (p:Parameters) =>
  new Compute(true)(p), (c: Compute) => new ComputeTest(c, "/examples_compute/compute_investigation.json", false))

/* Vector x matrix multiplication (Simple Matrix Multiply) */
class ComputeApp_Smm extends GenericTest("ComputeApp_Smm", (p:Parameters) =>
  new Compute(true)(p), (c: Compute) => new ComputeTest(c, "/examples_compute/compute_smm.json", true))

/* Matrix 16x16 multiply with matrix 16x16 */
class ComputeApp_Matrix_16x16 extends GenericTest("ComputeApp_Matrix_16x16", (p:Parameters) =>
  new Compute(true)(p), (c: Compute) => new ComputeTest(c, "/examples_compute/compute_matrix_16x16.json", true))

/* Matrix 32x32 multiply with matrix 32x32 */
class ComputeApp_Matrix_32x32 extends GenericTest("ComputeApp_Matrix_32x32", (p: Parameters) =>
  new Compute(true)(p), (c: Compute) => new ComputeTest(c, "/examples_compute/compute_matrix_32x32.json", true))

/* ALTERNATIVE INSTRUCTION INVESTIGATION:
 * Batches with 2 UOP and 1 GeMM loop */
class ComputeApp_Batches_2uop_1loop extends GenericTest("ComputeApp_Batches_2uop_1loop", (p:Parameters) =>
  new Compute(true)(p), (c: Compute) => new ComputeTest(c, "/examples_compute/alternative_instructions/batches_2uop_1loop.json", true))
/* Batches with 1 UOP and 2 GeMM loop */
class ComputeApp_Batches_1uop_2loops extends GenericTest("ComputeApp_Batches_1uop_2loops", (p: Parameters) =>
  new Compute(true)(p), (c: Compute) => new ComputeTest(c, "/examples_compute/alternative_instructions/batches_1uop_2loops.json", true))
/* Batches with 2 instructions */
class ComputeApp_Batches_2insn extends GenericTest("ComputeApp_Batches_2insn", (p: Parameters) =>
  new Compute(true)(p), (c: Compute) => new ComputeTest(c, "/examples_compute/alternative_instructions/batches_2insn.json", true))

/* ALTERNATIVE INSTRUCTION INVESTIGATION:
 * Load 4 UOP using 1 instruction */
class ComputeApp_LoadUop_1insn extends GenericTest("ComputeApp_LoadUop_1insn", (p: Parameters) =>
  new Compute(true)(p), (c: Compute) => new ComputeTest(c, "/examples_compute/alternative_instructions/loadUop_1insn.json"))
class ComputeApp_LoadUop_2insn extends GenericTest("ComputeApp_LoadUop_2insn", (p: Parameters) =>
  new Compute(true)(p), (c: Compute) => new ComputeTest(c, "/examples_compute/alternative_instructions/loadUop_2insn.json"))

/* ALU
 * ReLU */
class ComputeApp_relu extends GenericTest("ComputeApp_relu", (p:Parameters) =>
  new Compute(true)(p), (c: Compute) => new ComputeTest(c, "/examples_compute/compute_relu.json", true))
/* ReLU - ReLU in one instruction */
class ComputeApp_relu_relu extends GenericTest("ComputeApp_relu_relu", (p: Parameters) =>
  new Compute(true)(p), (c: Compute) => new ComputeTest(c, "/examples_compute/compute_relu_relu.json", true))

/* Matrix 16x16 multiply with matrix 16x16 followed by a ReLU (MAX with 0) */
class ComputeApp_16x16_relu extends GenericTest("ComputeApp_16x16_relu", (p: Parameters) =>
  new Compute(true)(p), (c: Compute) => new ComputeTest(c, "/examples_compute/compute_16x16_relu.json", true))
/* Matrix 32x32 multiply with matrix 32x32 followed by a ReLU (MAX with 0) */
class ComputeApp_32x32_relu extends GenericTest("ComputeApp_32x32_relu", (p: Parameters) =>
  new Compute(true)(p), (c: Compute) => new ComputeTest(c, "/examples_compute/compute_32x32_relu.json", true))

/* Average pooling (first part - add only) */
class ComputeApp_add_acc_vectors extends GenericTest("ComputeApp_add_acc_vectors", (p: Parameters) =>
  new Compute(true)(p), (c: Compute) => new ComputeTest(c, "/examples_compute/compute_add_acc_vectors.json", true))
/* Average pooling (full - add + division), the division round down */
class ComputeApp_average_pooling extends GenericTest("ComputeApp_average_pooling", (p: Parameters) =>
  new Compute(true)(p), (c: Compute) => new ComputeTest(c, "/examples_compute/compute_average_pooling.json", true))

/* CONVOLUTIONAL NEURAL NETWORK
 * LeNet-5: Convolution 1 */
class ComputeApp_lenet5_conv1 extends GenericTest("ComputeApp_lenet5_conv1", (p: Parameters) =>
  new Compute(true)(p), (c: Compute) => new ComputeTest(c, "/examples_compute/compute_lenet5_conv1.json", true), true)
/* LeNet-5: Conv1 + ReLU */
class ComputeApp_lenet5_conv1_relu extends GenericTest("ComputeApp_lenet5_conv1_relu", (p: Parameters) =>
  new Compute(true)(p), (c: Compute) => new ComputeTest(c, "/examples_compute/compute_lenet5_conv1_relu.json", true), true)
/* LeNet-5: Conv1 + ReLU + Average Pooling */
class ComputeApp_lenet5_conv1_relu_AvgPool extends GenericTest("ComputeApp_lenet5_conv1_relu_AvgPool", (p: Parameters) =>
  new Compute(true)(p), (c: Compute) => new ComputeTest(c, "/examples_compute/compute_lenet5_conv1_relu_average_pooling.json", false), true)