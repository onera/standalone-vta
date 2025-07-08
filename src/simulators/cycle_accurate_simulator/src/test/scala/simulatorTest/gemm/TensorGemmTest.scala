package simulatorTest.gemm

import chisel3._
import chisel3.util._
import chiseltest._
import chiseltest.iotesters._
import unittest.util._
import vta.core._
import vta.util.config._

import scala.io._
import scala.language.postfixOps
import com.fasterxml.jackson.databind.ObjectMapper
import com.fasterxml.jackson.module.scala.DefaultScalaModule

import unittest.{GenericTest, TensorGemmJsonTester}

/**
 * Similar to unittest.TensorGemmJsonTest
 * with adaptation
 */

class TensorGemmTest(c: TensorGemmPipelinedSplit, fn : String = "/x.json",
                     debug: Boolean = false)
  extends PeekPokeTester(c) {

  // Print the test name
  if(debug) {
    print("TEST NAME: \n\t TensorGemmTester (take a JSON in input)\n")
    print(s"\tJSON: ${fn} \n\n")
  }

  // Read the JSON file
  val bufferedSource = Source.fromURL(getClass.getResource(fn))
  val mapper = new ObjectMapper()
  mapper.registerModule(DefaultScalaModule)
  val archState = mapper.readValue(bufferedSource.reader(), classOf[Map[String, Object]])
  bufferedSource.close

  // Decode the instruction
  val inst = archState("inst").asInstanceOf[Map[String,String]]

  // Scratchpad memory (emulate the buffers / registers)
  def build_scratchpad(tag: String): Map[BigInt, Array[BigInt]] = {
    val arr = archState(tag).asInstanceOf[Seq[Map[String, Object]]]
    (
      for {m <- arr} yield {
        val idx = BigInt(m("idx").asInstanceOf[String], 16)
        val vec = m("vec").asInstanceOf[Seq[String]]
        idx -> (
          for {v <- vec} yield {
            val value = BigInt(v, 16)
            // Sign conversion
            if (value > 127) {value - 256}
            else {value}
          }
          ).toArray
      }
      ).toMap
  }

  // Print scratchpad
  def print_scratchpad(scratchpad: Map[BigInt, Array[BigInt]], index: BigInt, name: String = "?"): Unit = {
    print(s"\n ${name} scratchpad (index: ${index}) = \n (")
    for {i <- scratchpad(index).indices} {
      print(s"${scratchpad(index)(i).toInt}")
      if (i != scratchpad(index).size - 1) {
        print(", ")
      }
    }
    print(") \n\n")
  }

  // Compare scratchpad
  def compare_scratchpad(reference: Map[BigInt, Array[BigInt]], scratchpadUnderTest: Map[BigInt, Array[BigInt]]): Unit = {
    val availableIndexes = reference.keySet
    for (index <- availableIndexes){
      for (i <- reference(index).indices) {
        if (reference(index)(i).toInt != scratchpadUnderTest(index)(i).toInt) {
          print(s"\n\nERROR: difference between result and expectation at index:${index} position:${i}\n")
          print(s"\t Expected = ${reference(index)(i).toInt}, Obtained = ${scratchpadUnderTest(index)(i).toInt}")
        }
        assert(reference(index)(i).toInt == scratchpadUnderTest(index)(i).toInt)
      }
    }
  }

  // Print counter to avoid multiple printing of a same scratchpad
  var count_print_flag = 0

  // Build memory
  val inp_scratchpad = build_scratchpad("inp")
  val wgt_scratchpad = build_scratchpad("wgt")
  val uop_scratchpad = build_scratchpad("uop")
  val acc_scratchpad = build_scratchpad("acc_i")
  val acc_o_scratchpad = build_scratchpad("acc_o") // Expected

  // Unset start value (block computation -> sIdle)
  poke(c.io.start, 0)

  // Instruction fields with base conversion (hexadecimal)
  val dec_reset = BigInt(inst("reset"), 16)
  val uop_begin = BigInt(inst("uop_begin"), 16)
  val uop_end = BigInt(inst("uop_end"), 16)
  assert(uop_begin < uop_end)
  val lp_0 = BigInt(inst("lp_0"), 16)
  val lp_1 = BigInt(inst("lp_1"), 16)
  val acc_0 = BigInt(inst("acc_0"), 16)
  val inp_0 = BigInt(inst("inp_0"), 16)
  val wgt_0 = BigInt(inst("wgt_0"), 16)
  val acc_1 = BigInt(inst("acc_1"), 16)
  val inp_1 = BigInt(inst("inp_1"), 16)
  val wgt_1 = BigInt(inst("wgt_1"), 16)

  // Read instructions
  // Reset signal
  poke(c.io.dec.reset, dec_reset)
  // UOP_BGN
  poke(c.io.dec.uop_begin, uop_begin)
  // UOP_END
  poke(c.io.dec.uop_end, uop_end)
  // LOOP_EXTENT_0
  poke(c.io.dec.lp_0, lp_0)
  // LOOP_EXTENT_1
  poke(c.io.dec.lp_1, lp_1)
  // ACC_IDX_FACTOR_0 (X0)
  poke(c.io.dec.acc_0, acc_0)
  // ACC_IDX_FACTOR_1 (X1)
  poke(c.io.dec.acc_1, acc_1)
  // INP_IDX_FACTOR_0 (Y0)
  poke(c.io.dec.inp_0, inp_0)
  // INP_IDX_FACTOR_1 (Y1)
  poke(c.io.dec.inp_1, inp_1)
  // WGT_IDX_FACTOR_0 (Z0)
  poke(c.io.dec.wgt_0, wgt_0)
  // WGT_IDX_FACTOR_1 (Z1)
  poke(c.io.dec.wgt_1, wgt_1)

  if (debug) {
    print("Read instructions: \n")
    print(s"\t RESET: ${peek(c.io.dec.reset)} \n")
    print(s"\t UOP_BEGIN: ${peek(c.io.dec.uop_begin)} \n")
    print(s"\t UOP_END: ${peek(c.io.dec.uop_end)} \n")
    print(s"\t LP_0: ${peek(c.io.dec.lp_0)} \n")
    print(s"\t LP_1: ${peek(c.io.dec.lp_1)} \n")
    print(s"\t ACC_0: ${peek(c.io.dec.acc_0)} \n")
    print(s"\t ACC_1: ${peek(c.io.dec.acc_1)} \n")
    print(s"\t INP_0: ${peek(c.io.dec.inp_0)} \n")
    print(s"\t INP_1: ${peek(c.io.dec.inp_1)} \n")
    print(s"\t WGT_0: ${peek(c.io.dec.wgt_0)} \n")
    print(s"\t WGT_1: ${peek(c.io.dec.wgt_1)} \n\n")
  }


  // Read scratchpad
  class TensorMasterMock(tm: TensorMaster, scratchpad: Map[BigInt, Array[BigInt]]) {
    poke(tm.rd(0).data.valid, 0)
    var valid = peek(tm.rd(0).idx.valid)
    var idx: Int = 0

    def logical_step(): Unit = {
      if (valid == 1) {
        poke(tm.rd(0).data.valid, 1)
        val cols = tm.rd(0).data.bits(0).size
        for {i <- 0 until tm.rd(0).data.bits.size
             j <- 0 until cols
             } {
          poke(tm.rd(0).data.bits(i)(j), scratchpad(idx)(i * cols + j))
        }
      } else {
        poke(tm.rd(0).data.valid, 0)
      }
      valid = peek(tm.rd(0).idx.valid)
      idx = peek(tm.rd(0).idx.bits).toInt
    }
  }

  // Write scratchpad
  class TensorMasterMockWr(tm: TensorMaster, scratchpad: Map[BigInt, Array[BigInt]]) {
    def logical_step(): Unit = {
      if (peek(tm.wr(0).valid) == 1) {
        val idx = peek(tm.wr(0).bits.idx).toInt
        val cols = tm.wr(0).bits.data(0).size
        for {
          i <- 0 until tm.wr(0).bits.data.size
          j <- 0 until cols
        } {
          scratchpad(idx)(i * cols + j) = peek(tm.wr(0).bits.data(i)(j))
        }
      }
    }
  }

  // Write UOP buffer scratchpad
  class UopMasterMock(um: UopMaster, scratchpad: Map[BigInt,Array[BigInt]]) {
    poke(um.data.valid, 0)
    var valid = peek(um.idx.valid)
    var idx : Int = 0
    def logical_step() : Unit = {
      if (valid == 1) {
        poke(um.data.valid, 1)
        poke(um.data.bits.u0, scratchpad(idx)(0))
        poke(um.data.bits.u1, scratchpad(idx)(1))
        poke(um.data.bits.u2, scratchpad(idx)(2))
      } else {
        poke(um.data.valid, 0)
      }
      valid = peek(um.idx.valid)
      idx = peek(um.idx.bits).toInt
    }
  }

  // Emulate memory behaviour
  class Mocks {
    val uop_mock = new UopMasterMock(c.io.uop, uop_scratchpad)
    val inp_mock = new TensorMasterMock(c.io.inp, inp_scratchpad)
    val wgt_mock = new TensorMasterMock(c.io.wgt, wgt_scratchpad)
    val acc_mock = new TensorMasterMock(c.io.acc, acc_scratchpad)
    val acc_mock_wr = new TensorMasterMockWr(c.io.acc, acc_scratchpad)

    val uop_indices = new scala.collection.mutable.Queue[BigInt]
    val acc_indices = new scala.collection.mutable.Queue[BigInt]
    val inp_indices = new scala.collection.mutable.Queue[BigInt]
    val wgt_indices = new scala.collection.mutable.Queue[BigInt]
    val accout_indices = new scala.collection.mutable.Queue[BigInt]
    val out_indices = new scala.collection.mutable.Queue[BigInt]

    // Emulate the clock
    def logical_step() : Unit = {
      step(1)
      // Perform the defined operations for each emulated memory
      uop_mock.logical_step()
      inp_mock.logical_step()
      wgt_mock.logical_step()
      acc_mock.logical_step()
      acc_mock_wr.logical_step()

      if (peek(c.io.uop.idx.valid) == 1) {
        expect(c.io.uop.idx.bits, uop_indices.dequeue())
      }
      if (peek(c.io.acc.rd(0).idx.valid) == 1) {
        expect(c.io.acc.rd(0).idx.bits, acc_indices.dequeue())
      }
      if (peek(c.io.inp.rd(0).idx.valid) == 1) {
        expect(c.io.inp.rd(0).idx.bits, inp_indices.dequeue())
        if (debug) {
          // Print INPUT vector
          print(s"\n\nThe input vector (offset: ${peek(c.io.inp.rd(0).idx.bits)}): \n")
          print_scratchpad(inp_scratchpad, peek(c.io.inp.rd(0).idx.bits), "INP")
        }
      }
      if (peek(c.io.wgt.rd(0).idx.valid) == 1) {
        expect(c.io.wgt.rd(0).idx.bits, wgt_indices.dequeue())
        if (debug) {
          // Print WEIGHT tensor
          print(s"\n\nThe weight tensor (offset: ${peek(c.io.wgt.rd(0).idx.bits)}): \n")
          print_scratchpad(wgt_scratchpad, peek(c.io.wgt.rd(0).idx.bits), "WGT")
        }
      }
      if (peek(c.io.acc.wr(0).valid) == 1) {
        expect(c.io.acc.wr(0).bits.idx, accout_indices.dequeue())
      }
      if (peek(c.io.out.wr(0).valid) == 1) {
        expect(c.io.out.wr(0).bits.idx, out_indices.dequeue())
        if (debug) {
          // Print the result
          print(s"\n\nThe output vector (offset: ${peek(c.io.out.wr(0).bits.idx)}): \n") // Call acc and not out (???)
          print_scratchpad(acc_scratchpad, peek(c.io.out.wr(0).bits.idx), "ACC")
        }
      }
    }

    // Check if all the UOP are used
    def test_if_done() : Unit = {
      print("\nSpecification:  \n")
      print(s"\t uop_indices should be empty ${uop_indices.size} \n")
      print(s"\t acc_indices should be empty ${acc_indices.size} \n")
      print(s"\t inp_indices should be empty ${inp_indices.size} \n")
      print(s"\t wgt_indices should be empty ${wgt_indices.size} \n")
      print(s"\t accout_indices should be empty ${accout_indices.size} \n")
      print(s"\t out_indices should be empty ${out_indices.size} \n")
    }

    // Assertion
    def check() = {
      compare_scratchpad(acc_o_scratchpad, acc_scratchpad)
    }
  }

  val mocks = new Mocks

  // Perform all the required operations (cf. GeMM pseudo-code)
  for {
    cnt_o <- BigInt(0) until lp_0
    cnt_i <- BigInt(0) until lp_1
    uop_idx <- uop_begin until uop_end
  } {
    val u0 = uop_scratchpad(uop_idx.toInt)(0)
    val u1 = uop_scratchpad(uop_idx.toInt)(1)
    val u2 = uop_scratchpad(uop_idx.toInt)(2)

    mocks.uop_indices.enqueue(uop_idx)
    mocks.acc_indices.enqueue(u0 + acc_0*cnt_o + acc_1*cnt_i)
    mocks.inp_indices.enqueue(u1 + inp_0*cnt_o + inp_1*cnt_i)
    mocks.wgt_indices.enqueue(u2 + wgt_0*cnt_o + wgt_1*cnt_i)
    mocks.accout_indices.enqueue(u0 + acc_0*cnt_o + acc_1*cnt_i)

    if (dec_reset == 0) {
      mocks.out_indices.enqueue(u0 + acc_0*cnt_o + acc_1*cnt_i)
    }
  }

  // Unset (again ?) start signal
  poke(c.io.start, 0)
  mocks.logical_step()
  expect(c.io.state, c.sIdle)

  // Set start signal (execute!)
  poke(c.io.start, 1)

  // Specification
  val total_steps = (uop_end-uop_begin)*lp_0*lp_1

  // Timeout
  val max_count = 100 + 4*total_steps

  // Count time to complete execuion
  var count = 0
  while (peek(c.io.done) == 0 && count < max_count) {
    if (debug) {
      print(s"DEBUG: Logical step: counter = $count \n")
    }
    mocks.logical_step()
    if (count == 0) {
      poke(c.io.start, 0)
    }
    count += 1
  }

  // Execution is done
  assert(peek(c.io.done) == 1, s"Signal done never high even after $count steps.")
  if (debug) {
    print(s"DEBUG: Signal done high after $count steps. \n")
  }

  // Reset signals (?)
  mocks.logical_step()
  expect(c.io.done, 0)

  if (debug) {
    print(s"DEBUG: Total active steps: ${total_steps} \n")
    mocks.test_if_done()
  }

  // Assertion (acc_o is the reference!)
  val cc = mocks.check()

  if (debug) {
    // Everything is okay
    print("\n\t MATCH EXPECTATON! \n\n")
  }
}


/**
 * Execute the tests
 */
class TensorGemmTester_smm extends GenericTest("Simple Matrix Multiply", (p:Parameters) =>
  new TensorGemmPipelinedSplit()(p),
  (c:TensorGemmPipelinedSplit) => new TensorGemmTest(c, "/examples_gemm/b1_c1h1w16_c1h1w16_simple_matrix_multiply.json"))

class TensorGemmTester_oc extends GenericTest("Output Channel", (p:Parameters) =>
  new TensorGemmPipelinedSplit()(p),
  (c:TensorGemmPipelinedSplit) => new TensorGemmTest(c, "/examples_gemm/b1_c1h1w16_c2h1w16_output_channel.json"))

/* We must modify the configuration for this test */
//class TensorGemmTester_rows extends GenericTest("Rows", (p: Parameters) =>
//  new TensorGemmPipelinedSplit()(p),
//  (c: TensorGemmPipelinedSplit) => new TensorGemmTest(c, "/examples_gemm/b1_c1h2w16_c1h2w16_rows.json"))

class TensorGemmTester_ic extends GenericTest("Input Channel", (p: Parameters) =>
  new TensorGemmPipelinedSplit()(p),
  (c: TensorGemmPipelinedSplit) => new TensorGemmTest(c, "/examples_gemm/b1_c2h1w16_c1h1w16_input_channel.json"))

class TensorGemmTester_full extends GenericTest("Full", (p: Parameters) =>
  new TensorGemmPipelinedSplit()(p),
  (c: TensorGemmPipelinedSplit) => new TensorGemmTest(c, "/examples_gemm/b1_c16h1w16_c16h1w16_full.json"))

class TensorGemmTester_batches extends GenericTest("Batches", (p: Parameters) =>
  new TensorGemmPipelinedSplit()(p),
  (c: TensorGemmPipelinedSplit) => new TensorGemmTest(c, "/examples_gemm/b2_c1h1w16_c1h1w16_batches.json"))

/* Test for investigation */
class TensorGemmTester_test extends GenericTest("Test instructions", (p: Parameters) =>
  new TensorGemmPipelinedSplit()(p),
  (c: TensorGemmPipelinedSplit) => new TensorGemmTest(c, "/examples_gemm/test_instructions.json"))

