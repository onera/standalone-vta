package simulatorTest.alu

import chisel3._
import chiseltest.iotesters.PeekPokeTester
import com.fasterxml.jackson.databind.ObjectMapper
import com.fasterxml.jackson.module.scala.DefaultScalaModule
import scala.io._
import scala.language.postfixOps
import vta.core._
import vta.util.config._
import unittest.GenericTest

class TensorAluJsonTest(c: TensorAlu, fn : String = "/x.json",
                        debug : Boolean = false)
  extends PeekPokeTester(c) {

  if (debug) {
    // Print the test name
    println("TEST NAME: \n\t TensorAluJsonTester (take a JSON in input)")
    print(s"\tJSON: ${fn} \n\n")
  }

  // READ the JSON file
  val bufferedSource = Source.fromURL(getClass.getResource(fn))
  val mapper = new ObjectMapper()
  mapper.registerModule(DefaultScalaModule)
  val archState = mapper.readValue(bufferedSource.reader(), classOf[Map[String, Object]])
  bufferedSource.close

  // Decode the instruction section
  val inst = archState("inst").asInstanceOf[Map[String,String]]

  // Scratchpad memory (emulate the buffers / registers)
  def build_scratchpad(tag: String) : Map[BigInt, Array[BigInt]] = {
    val arr = archState(tag).asInstanceOf[Seq[Map[String,Object]]]
    (
      for {m <- arr} yield {
        val idx = BigInt(m("idx").asInstanceOf[String], 16)
        val vec = m("vec").asInstanceOf[Seq[String]]
        idx ->(
          for {v <- vec} yield {
            BigInt(v, 16)
          }
        ).toArray
      }
    ).toMap
  }

  // Print scratchpad
  def print_scratchpad(scratchpad: Map[BigInt, Array[BigInt]], index: BigInt): Unit = {
    print("\n (")
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
    for (index <- availableIndexes) {
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
  //TODO: Missing "src" that is in the same memory space as "acc"
  val uop_scratchpad = build_scratchpad("uop")
  val acc_scratchpad = build_scratchpad("acc")
  val acc_expect_scratchpad = build_scratchpad("acc_expect") // Expected

  // Unset start value (block computation -> sIdle)
  poke(c.io.start, 0)

  // Instruction fields with base conversion (hexadecimal)
  val dec_reset = BigInt(inst("reset"), 16)
  val uop_begin = BigInt(inst("uop_begin"), 16)
  val uop_end = BigInt(inst("uop_end"), 16)
  assert(uop_begin < uop_end)
  val lp_0 = BigInt(inst("lp_0"), 16)
  val lp_1 = BigInt(inst("lp_1"), 16)
  val dst_0 = BigInt(inst("dst_0"), 16)
  val dst_1 = BigInt(inst("dst_1"), 16)
  val src_0 = BigInt(inst("src_0"), 16)
  val src_1 = BigInt(inst("src_1"), 16)
  val alu_op = BigInt(inst("alu_op"), 16)
  val use_imm = BigInt(inst("use_imm"), 16)
  val imm = BigInt(inst("imm"), 16)

  // Read instructions
  // RESET
  poke(c.io.dec.reset, dec_reset)
  // UOP_BGN
  poke(c.io.dec.uop_begin, uop_begin)
  // UOP_END
  poke(c.io.dec.uop_end, uop_end)
  // LOOP_EXTENT_0
  poke(c.io.dec.lp_0, lp_0)
  // LOOP_EXTENT_1
  poke(c.io.dec.lp_1, lp_1)
  // DST_IDX_FACTOR_0 (Y0)
  poke(c.io.dec.dst_0, dst_0)
  // DST_IDX_FACTOR_1 (Y1)
  poke(c.io.dec.dst_1, dst_1)
  // SRC_IDX_FACTOR_0 (X0)
  poke(c.io.dec.src_0, src_0)
  // SRC_IDX_FACTOR_1 (X1)
  poke(c.io.dec.src_1, src_1)
  // ALU_OP (opcode: min:0, max:1, add:2, shr:3, shl:4)
  poke(c.io.dec.alu_op, alu_op)
  // USE_IMM
  poke(c.io.dec.alu_use_imm, use_imm)
  // IMM
  poke(c.io.dec.alu_imm, imm)

  if (debug) {
    println("Read instructions:")
    print(s"\t RESET: ${peek(c.io.dec.reset)} \n")
    print(s"\t UOP_BEGIN: ${peek(c.io.dec.uop_begin)} \n")
    print(s"\t UOP_END: ${peek(c.io.dec.uop_end)} \n")
    print(s"\t LP_0: ${peek(c.io.dec.lp_0)} \n")
    print(s"\t LP_1: ${peek(c.io.dec.lp_1)} \n")
    print(s"\t DST_0: ${peek(c.io.dec.dst_0)} \n")
    print(s"\t DST_1: ${peek(c.io.dec.dst_1)} \n")
    print(s"\t SRC_0: ${peek(c.io.dec.src_0)} \n")
    print(s"\t SRC_1: ${peek(c.io.dec.src_1)} \n")
    print(s"\t ALU_OP: ${peek(c.io.dec.alu_op)} \t (0 = MIN / 1 = MAX / 2 = ADD / 3 = SHR / 4 = SHL) \n")
    print(s"\t USE_IMM: ${peek(c.io.dec.alu_use_imm)} \n")
    print(s"\t IMM: ${peek(c.io.dec.alu_imm)} \n\n")
  }

  // FIXME: comment - what is it???
  require(c.io.acc.splitWidth == 1, "-F- Test doesnt support acc data access split")
  require(c.io.acc.splitLength == 1, "-F- Test doesnt support acc data access split")

  // Read scratchpad
  class TensorMasterMock(tm: TensorMaster, scratchpad : Map[BigInt,Array[BigInt]]) {
    poke(tm.rd(0).data.valid, 0)
    var valid = peek(tm.rd(0).idx.valid)
    var idx : Int = 0
    def logical_step() : Unit = {
      if (valid == 1) {
        poke(tm.rd(0).data.valid, 1)
        val cols = tm.rd(0).data.bits(0).size
        for {i <- 0 until tm.rd(0).data.bits.size
          j <- 0 until cols
        } {
          poke(tm.rd(0).data.bits(i)(j), scratchpad(idx)(i*cols + j))
        }
      } else {
        poke(tm.rd(0).data.valid, 0)
      }
      valid = peek(tm.rd(0).idx.valid)
      idx = peek(tm.rd(0).idx.bits).toInt
    }
  }

  // Write scratchpad
  class TensorMasterMockWr(tm: TensorMaster, scratchpad : Map[BigInt,Array[BigInt]]) {
    def logical_step() : Unit = {
      if (peek(tm.wr(0).valid) == 1) {
        val idx = peek(tm.wr(0).bits.idx).toInt
        val cols = tm.wr(0).bits.data(0).size
        for {
          i <- 0 until tm.wr(0).bits.data.size
          j <- 0 until cols
        } {
          scratchpad(idx)(i*cols + j) = peek(tm.wr(0).bits.data(i)(j))
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

        // Read the dst offset of the current UOP
        val dst_offset = scratchpad(idx)(0)
        poke(um.data.bits.u0, dst_offset)

        // Read the src offset of the current UOP
        val src_offset = scratchpad(idx)(1)
        poke(um.data.bits.u1, src_offset)

        // Non-used field
        poke(c.io.uop.data.bits.u2, 0) // if src_offset is big, some bits go here

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
    val acc_mock = new TensorMasterMock(c.io.acc, acc_scratchpad)
    val acc_mock_wr = new TensorMasterMockWr(c.io.acc, acc_scratchpad)

    val uop_indices = new scala.collection.mutable.Queue[BigInt]
    val acc_indices = new scala.collection.mutable.Queue[BigInt]
    val accout_indices = new scala.collection.mutable.Queue[BigInt]
    val out_indices = new scala.collection.mutable.Queue[BigInt]

    // Emulate the clock
    // Print the data in this function!
    def logical_step() : Unit = {
      // Increment the clock
      step(1)

      // Perform the defined operations for each memory
      uop_mock.logical_step()
      acc_mock.logical_step()
      acc_mock_wr.logical_step()

      // Print the valid flags
      /*println(s"UOP: ${peek(c.io.uop.idx.valid)} \t ACC_RD: ${peek(c.io.acc.rd(0).idx.valid)} " +
        s"\t ACC_WR: ${peek(c.io.acc.wr(0).valid)} \t OUT: ${peek(c.io.out.wr(0).valid)}")*/

      // Check that the queues have been correctly read
      // Read UOP
      if (peek(c.io.uop.idx.valid) == 1) {
        expect(c.io.uop.idx.bits, uop_indices.dequeue())
      }
      // Read ACC
      if (peek(c.io.acc.rd(0).idx.valid) == 1) {
        val expected_acc_rd_idx = acc_indices.dequeue()
        expect(c.io.acc.rd(0).idx.bits, expected_acc_rd_idx)

        if (debug) {
          // Print data (SRC and, DST or IMM)
          if (count_print_flag == 0) {
            println("INPUTS:")
            print(s"Source scratchpad: (offset = ${expected_acc_rd_idx})")
            print_scratchpad(acc_scratchpad, index = expected_acc_rd_idx)
          }
          else if (count_print_flag == 1) {
            if (use_imm == 0) {
              print(s"Destination scratchpad: (offset = ${expected_acc_rd_idx})")
              print_scratchpad(acc_scratchpad, index = expected_acc_rd_idx)
            }
            else {
              print(s"Immediate value = ${imm} \n\n")
            }
          }
          count_print_flag = count_print_flag + 1
        }
      }
      // Write ACC
      if (peek(c.io.acc.wr(0).valid) == 1) {
        val expected_acc_wr_idx = accout_indices.dequeue()
        expect(c.io.acc.wr(0).bits.idx, expected_acc_wr_idx)
      }
      // Write OUT
      if (peek(c.io.out.wr(0).valid) == 1) {
        val expected_out_wr_idx = out_indices.dequeue()
        expect(c.io.out.wr(0).bits.idx, expected_out_wr_idx)

        if (debug) {
          // Print output
          println("OUTPUT:")
          print(s"Update DST scratchpad: (offset = ${expected_out_wr_idx})")
          print_scratchpad(acc_scratchpad, index = expected_out_wr_idx)
          count_print_flag = 0
          print("\n")
        }
      }
    }

    // Specification (enqueue the expected indices)
    def enqueue_indices() : Unit = {
      for {
        cnt_o <- BigInt(0) until lp_0
        cnt_i <- BigInt(0) until lp_1
        uop_idx <- uop_begin until uop_end

        // Definition of the offset
        dst_offset = uop_scratchpad(uop_idx)(0)
        src_offset = uop_scratchpad(uop_idx)(1)
      } {
        // SRC read at indices:
        mocks.uop_indices.enqueue(uop_idx)
        mocks.acc_indices.enqueue(src_offset + src_0 * cnt_o + src_1 * cnt_i)
        //FIXME: be sure the specification is correct when use_imm = 0 (added assumption)
        // DST read at indices:
        if (use_imm == 0) {
          mocks.uop_indices.enqueue(uop_idx)
          mocks.acc_indices.enqueue(dst_offset + dst_0 * cnt_o + dst_1 * cnt_i)
        }
        // DST write at indices:
        mocks.accout_indices.enqueue(dst_offset + dst_0 * cnt_o + dst_1 * cnt_i)
        mocks.out_indices.enqueue(dst_offset + dst_0 * cnt_o + dst_1 * cnt_i)
      }
    }

    // The queue should be empty
    def test_if_done() : Unit = {
      println(s"uop_indices should be empty ${uop_indices.size}")
      println(s"acc_indices should be empty ${acc_indices.size}")
      println(s"accout_indices should be empty ${accout_indices.size}")
      println(s"out_indices should be empty ${out_indices.size}")
    }

    // Check the final result
    def check() = {
      val dst_offset = uop_scratchpad(uop_scratchpad.size - 1)(0)
      for {i <- acc_scratchpad(dst_offset + lp_0 * dst_0 + lp_1 * dst_1).indices} {
        require(acc_scratchpad(dst_offset + lp_0*dst_0 + lp_1*dst_1)(i) == acc_expect_scratchpad(0)(i),
          s"Result mismatches at index ${i}")
      }
    }
  }

  // Create the mocks
  val mocks = new Mocks

  // Read the indices
  mocks.enqueue_indices()

  // Start the operation
  poke(c.io.start, 0)
  step(1)
  poke(c.io.start, 1)

  // Count the number of cycles and set a limit to avoid infinite loop
  var count = 0
  val end = (uop_end-uop_begin)*lp_0*lp_1

  // PRINT DATA WITHIN LOGICAL STEP
  if (debug) {
    print_scratchpad(acc_scratchpad, 256)
  }

  // Logical step for operation
  while (peek(c.io.done) == 0 && count < 10*end + 100) {
    mocks.logical_step()
    poke(c.io.start, 0)
    count += 1
  }
  expect(c.io.done, 1) // Operation is done

  if (debug) {
    // Check if the queues are empty
    mocks.test_if_done()
    // Check if everything is okay
    print("\n\t MATCH EXPECTATON! \n\n")
  }
}

/**
 * Execute the tests
 */
class TensorAluJsonTester_add extends GenericTest("TensorAluJsonTest_ADD", (p:Parameters) =>
  new TensorAlu()(p),
  (c:TensorAlu) => new TensorAluJsonTest(c, "/examples_alu/add.json"))

class TensorAluJsonTester_add_imm extends GenericTest("TensorAluJsonTest_ADD_IMM", (p:Parameters) =>
  new TensorAlu()(p),
  (c:TensorAlu) => new TensorAluJsonTest(c, "/examples_alu/add_imm.json"))

class TensorAluJsonTester_max extends GenericTest("TensorAluJsonTest_MAX", (p: Parameters) =>
  new TensorAlu()(p),
  (c: TensorAlu) => new TensorAluJsonTest(c, "/examples_alu/max.json"))

class TensorAluJsonTester_max_imm extends GenericTest("TensorAluJsonTest_MAX_IMM", (p: Parameters) =>
  new TensorAlu()(p),
  (c: TensorAlu) => new TensorAluJsonTest(c, "/examples_alu/max_imm.json"))

class TensorAluJsonTester_min extends GenericTest("TensorAluJsonTest_MIN", (p: Parameters) =>
  new TensorAlu()(p),
  (c: TensorAlu) => new TensorAluJsonTest(c, "/examples_alu/min.json"))

class TensorAluJsonTester_min_imm extends GenericTest("TensorAluJsonTest_MIN_IMM", (p: Parameters) =>
  new TensorAlu()(p),
  (c: TensorAlu) => new TensorAluJsonTest(c, "/examples_alu/min_imm.json"))

class TensorAluJsonTester_naive_maxpool extends GenericTest("TensorAluJsonTest_NAIVE_MAXPOOL", (p: Parameters) =>
  new TensorAlu()(p),
  (c: TensorAlu) => new TensorAluJsonTest(c, "/examples_alu/naive_maxpool.json"))

class TensorAluJsonTester_relu_activation extends GenericTest("TensorAluJsonTest_RELU_ACTIVATION", (p: Parameters) =>
  new TensorAlu()(p),
  (c: TensorAlu) => new TensorAluJsonTest(c, "/examples_alu/relu_activation.json"))

class TensorAluJsonTester_shift_left extends GenericTest("TensorAluJsonTest_SHIFT_LEFT", (p: Parameters) =>
  new TensorAlu()(p),
  (c: TensorAlu) => new TensorAluJsonTest(c, "/examples_alu/shift_left.json"))

class TensorAluJsonTester_shift_left_imm extends GenericTest("TensorAluJsonTest_SHIFT_LEFT_IMM", (p: Parameters) =>
  new TensorAlu()(p),
  (c: TensorAlu) => new TensorAluJsonTest(c, "/examples_alu/shift_left_imm.json"))

class TensorAluJsonTester_shift_right extends GenericTest("TensorAluJsonTest_SHIFT_RIGHT", (p: Parameters) =>
  new TensorAlu()(p),
  (c: TensorAlu) => new TensorAluJsonTest(c, "/examples_alu/shift_right.json"))

class TensorAluJsonTester_shift_right_imm extends GenericTest("TensorAluJsonTest_SHIFT_RIGHT_IMM", (p: Parameters) =>
  new TensorAlu()(p),
  (c: TensorAlu) => new TensorAluJsonTest(c, "/examples_alu/shift_right_imm.json"))
