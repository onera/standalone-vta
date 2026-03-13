package simulatorTest.alu

import chisel3._
import com.fasterxml.jackson.databind.ObjectMapper
import com.fasterxml.jackson.module.scala.DefaultScalaModule
import scala.io._
import scala.language.postfixOps
import vta.core._
import vta.util.config._
import unittest.GenericTest
import chisel3.simulator.ChiselSim
import chisel3.simulator.PeekPokeAPI
import unittest.AnyFlatSpecSim
import chisel3.simulator.stimulus.ResetProcedure
import chisel3.experimental.inlinetest.TestHarness
import chisel3.experimental.inlinetest.TestHarnessGenerator

class TensorAluJsonTest(
    c: TensorAlu,
    fn: String = "/x.json",
    debug: Boolean = false
) extends PeekPokeAPI {

  if (debug) {
    // Print the test name
    println("TEST NAME: \n\t TensorAluJsonTester (take a JSON in input)")
  }
  print(s"\tJSON: ${fn} \n\n")

  // READ the JSON file
  val bufferedSource = Source.fromURL(getClass.getResource(fn))
  val mapper = new ObjectMapper()
  mapper.registerModule(DefaultScalaModule)
  val archState =
    mapper.readValue(bufferedSource.reader(), classOf[Map[String, Object]])
  bufferedSource.close

  // Decode the instruction section
  val inst = archState("inst").asInstanceOf[Map[String, String]]

  // Scratchpad memory (emulate the buffers / registers)
  def build_scratchpad(tag: String): Map[BigInt, Array[BigInt]] = {
    val arr = archState(tag).asInstanceOf[Seq[Map[String, Object]]]
    (
      for { m <- arr } yield {
        val idx = BigInt(m("idx").asInstanceOf[String], 16)
        val vec = m("vec").asInstanceOf[Seq[String]]
        idx -> (
          for { v <- vec } yield {
            BigInt(v, 16)
          }
        ).toArray
      }
    ).toMap
  }

  // Print scratchpad
  def print_scratchpad(
      scratchpad: Map[BigInt, Array[BigInt]],
      index: BigInt
  ): Unit = {
    print("\n (")
    for { i <- scratchpad(index).indices } {
      print(s"${scratchpad(index)(i).toInt}")
      if (i != scratchpad(index).size - 1) {
        print(", ")
      }
    }
    print(") \n\n")
  }

  // Compare scratchpad
  def compare_scratchpad(
      reference: Map[BigInt, Array[BigInt]],
      scratchpadUnderTest: Map[BigInt, Array[BigInt]]
  ): Unit = {
    val availableIndexes = reference.keySet
    for (index <- availableIndexes) {
      for (i <- reference(index).indices) {
        if (reference(index)(i).toInt != scratchpadUnderTest(index)(i).toInt) {
          print(
            s"\n\nERROR: difference between result and expectation at index:${index} position:${i}\n"
          )
          print(
            s"\t Expected = ${reference(index)(i).toInt}, Obtained = ${scratchpadUnderTest(index)(i).toInt}"
          )
        }
        assert(
          reference(index)(i).toInt == scratchpadUnderTest(index)(i).toInt,
          "reference and scratchpad differ"
        )
      }
    }
  }

  // Print counter to avoid multiple printing of a same scratchpad
  var count_print_flag = 0

  // Build memory
  // TODO: Missing "src" that is in the same memory space as "acc"
  val uop_scratchpad = build_scratchpad("uop")
  val acc_scratchpad = build_scratchpad("acc")
  val acc_expect_scratchpad = build_scratchpad("acc_expect") // Expected

  // Unset start value (block computation -> sIdle)
  c.io.start.poke(0)

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
  c.io.dec.reset.poke(dec_reset)
  // UOP_BGN
  c.io.dec.uop_begin.poke(uop_begin)
  // UOP_END
  c.io.dec.uop_end.poke(uop_end)
  // LOOP_EXTENT_0
  c.io.dec.lp_0.poke(lp_0)
  // LOOP_EXTENT_1
  c.io.dec.lp_1.poke(lp_1)
  // DST_IDX_FACTOR_0 (Y0)
  c.io.dec.dst_0.poke(dst_0)
  // DST_IDX_FACTOR_1 (Y1)
  c.io.dec.dst_1.poke(dst_1)
  // SRC_IDX_FACTOR_0 (X0)
  c.io.dec.src_0.poke(src_0)
  // SRC_IDX_FACTOR_1 (X1)
  c.io.dec.src_1.poke(src_1)
  // ALU_OP (opcode: min:0, max:1, add:2, shr:3, shl:4)
  c.io.dec.alu_op.poke(alu_op)
  // USE_IMM
  c.io.dec.alu_use_imm.poke(use_imm)
  // IMM
  c.io.dec.alu_imm.poke(imm)

  if (debug) {
    println("Read instructions:")
    print(s"\t RESET: ${c.io.dec.reset.peek()} \n")
    print(s"\t UOP_BEGIN: ${c.io.dec.uop_begin.peek()} \n")
    print(s"\t UOP_END: ${c.io.dec.uop_end.peek()} \n")
    print(s"\t LP_0: ${c.io.dec.lp_0.peek()} \n")
    print(s"\t LP_1: ${c.io.dec.lp_1.peek()} \n")
    print(s"\t DST_0: ${c.io.dec.dst_0.peek()} \n")
    print(s"\t DST_1: ${c.io.dec.dst_1.peek()} \n")
    print(s"\t SRC_0: ${c.io.dec.src_0.peek()} \n")
    print(s"\t SRC_1: ${c.io.dec.src_1.peek()} \n")
    print(
      s"\t ALU_OP: ${c.io.dec.alu_op.peek()} \t (0 = MIN / 1 = MAX / 2 = ADD / 3 = SHR / 4 = SHL) \n"
    )
    print(s"\t USE_IMM: ${c.io.dec.alu_use_imm.peek()} \n")
    print(s"\t IMM: ${c.io.dec.alu_imm.peek()} \n\n")
  }

  // FIXME: comment - what is it???
  require(
    c.io.acc.splitWidth == 1,
    "-F- Test doesnt support acc data access split"
  )
  require(
    c.io.acc.splitLength == 1,
    "-F- Test doesnt support acc data access split"
  )

  // Read scratchpad
  class TensorMasterMock(
      tm: TensorMaster,
      scratchpad: Map[BigInt, Array[BigInt]]
  ) {
    tm.rd(0).data.valid.poke(0)
    var valid = tm.rd(0).idx.valid.peekBoolean()
    var idx: Int = 0
    def logical_step(): Unit = {
      if (valid) {
        tm.rd(0).data.valid.poke(1)
        val cols = tm.rd(0).data.bits(0).size
        for {
          i <- 0 until tm.rd(0).data.bits.size
          j <- 0 until cols
        } {
          tm.rd(0).data.bits(i)(j).poke(scratchpad(idx)(i * cols + j))
        }
      } else {
        tm.rd(0).data.valid.poke(0)
      }
      valid = tm.rd(0).idx.valid.peekBoolean()
      idx = tm.rd(0).idx.bits.peek().litValue.toInt
    }
  }

  // Write scratchpad
  class TensorMasterMockWr(
      tm: TensorMaster,
      scratchpad: Map[BigInt, Array[BigInt]]
  ) {
    def logical_step(): Unit = {
      if (tm.wr(0).valid.peekBoolean()) {
        val idx = tm.wr(0).bits.idx.peek().litValue.toInt
        val cols = tm.wr(0).bits.data(0).size
        for {
          i <- 0 until tm.wr(0).bits.data.size
          j <- 0 until cols
        } {
          scratchpad(idx)(i * cols + j) =
            tm.wr(0).bits.data(i)(j).peek().litValue
        }
      }
    }
  }

  // Write UOP buffer scratchpad
  class UopMasterMock(um: UopMaster, scratchpad: Map[BigInt, Array[BigInt]]) {
    um.data.valid.poke(0)
    var valid = um.idx.valid.peek()
    var idx: Int = 0
    def logical_step(): Unit = {
      if (valid == 1) {
        um.data.valid.poke(1)

        // Read the dst offset of the current UOP
        val dst_offset = scratchpad(idx)(0)
        um.data.bits.u0.poke(dst_offset)

        // Read the src offset of the current UOP
        val src_offset = scratchpad(idx)(1)
        um.data.bits.u1.poke(src_offset)

        // Non-used field
        c.io.uop.data.bits.u2.poke(0) // if src_offset is big, some bits go here

      } else {
        um.data.valid.poke(0)
      }
      valid = um.idx.valid.peek()
      idx = um.idx.bits.peek().litValue.toInt
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
    def logical_step(): Unit = {
      // Increment the clock
      c.clock.step(1)

      // Perform the defined operations for each memory
      uop_mock.logical_step()
      acc_mock.logical_step()
      acc_mock_wr.logical_step()

      // Print the valid flags
      /*println(s"UOP: ${c.io.uop.idx.valid.peek()} \t ACC_RD: ${c.io.acc.rd(0.peek().idx.valid)} " +
        s"\t ACC_WR: ${c.io.acc.wr(0.peek().valid)} \t OUT: ${c.io.out.wr(0.peek().valid)}")*/

      // Check that the queues have been correctly read
      // Read UOP
      if (c.io.uop.idx.valid.peekBoolean()) {
        c.io.uop.idx.bits.expect(
          uop_indices.dequeue(),
          "[read uop] uop index should be correct"
        )
      }
      // Read ACC
      if (c.io.acc.rd(0).idx.valid.peekBoolean()) {
        val expected_acc_rd_idx = acc_indices.dequeue()
        // c.io.acc
        //   .rd(0)
        //   .idx
        //   .bits
        //   .expect(
        //     expected_acc_rd_idx,
        //     "[read acc] accumulator read index is incorrect"
        //   )

        if (debug) {
          // Print data (SRC and, DST or IMM)
          if (count_print_flag == 0) {
            println("INPUTS:")
            print(s"Source scratchpad: (offset = ${expected_acc_rd_idx})")
            print_scratchpad(acc_scratchpad, index = expected_acc_rd_idx)
          } else if (count_print_flag == 1) {
            if (use_imm == 0) {
              print(
                s"Destination scratchpad: (offset = ${expected_acc_rd_idx})"
              )
              print_scratchpad(acc_scratchpad, index = expected_acc_rd_idx)
            } else {
              print(s"Immediate value = ${imm} \n\n")
            }
          }
          count_print_flag = count_print_flag + 1
        }
      }
      // Write ACC
      if (c.io.acc.wr(0).valid.peekBoolean()) {
        val expected_acc_wr_idx = accout_indices.dequeue()
        // c.io.acc
        //   .wr(0)
        //   .bits
        //   .idx
        //   .expect(expected_acc_wr_idx, "[write acc] acc index is incorrect")
      }
      // Write OUT
      if (c.io.out.wr(0).valid.peekBoolean()) {
        val expected_out_wr_idx = out_indices.dequeue()
        // c.io.out
        //   .wr(0)
        //   .bits
        //   .idx
        //   .expect(expected_out_wr_idx, "[write out] out index is incorrect")

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
    def enqueue_indices(): Unit = {
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
        // FIXME: be sure the specification is correct when use_imm = 0 (added assumption)
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
    def test_if_done(): Unit = {
      println(s"uop_indices should be empty ${uop_indices.size}")
      println(s"acc_indices should be empty ${acc_indices.size}")
      println(s"accout_indices should be empty ${accout_indices.size}")
      println(s"out_indices should be empty ${out_indices.size}")
    }

    // Check the final result
    def check() = {
      val dst_offset = uop_scratchpad(uop_scratchpad.size - 1)(0)
      for {
        i <- acc_scratchpad(dst_offset + lp_0 * dst_0 + lp_1 * dst_1).indices
      } {
        require(
          acc_scratchpad(dst_offset + lp_0 * dst_0 + lp_1 * dst_1)(
            i
          ) == acc_expect_scratchpad(0)(i),
          s"Result mismatches at index ${i}"
        )
      }
    }
  }

  // Create the mocks
  val mocks = new Mocks

  // Read the indices
  mocks.enqueue_indices()

  // Start the operation
  c.io.start.poke(0)
  c.clock.step(1)
  c.io.start.poke(1)

  // Count the number of cycles and set a limit to avoid infinite loop
  var count = 0
  val end = (uop_end - uop_begin) * lp_0 * lp_1

  // PRINT DATA WITHIN LOGICAL STEP
  if (debug) {
    print_scratchpad(acc_scratchpad, 256)
  }

  // Logical step for operation
  while (!c.io.done.peekBoolean() && count < 10 * end + 100) {
    mocks.logical_step()
    c.io.start.poke(0)
    count += 1
  }
  c.io.done.expect(1) // Operation is done

  if (debug) {
    // Check if the queues are empty
    mocks.test_if_done()
    // Check if everything is okay
    print("\n\t MATCH EXPECTATON! \n\n")
  }
}

/** Execute the tests
  */
class TensorAluJsonTester extends AnyFlatSpecSim {
  behavior of "TensorAlu"

  it should "run correctly instructions described in Json files" in {
    simulate(new TensorAlu) { c =>
      Seq(
        "/examples_alu/add.json",
        "/examples_alu/add_imm.json",
        "/examples_alu/max.json",
        "/examples_alu/max_imm.json",
        "/examples_alu/min.json",
        "/examples_alu/min_imm.json",
        "/examples_alu/naive_maxpool.json",
        "/examples_alu/relu_activation.json",
        "/examples_alu/shift_left.json",
        "/examples_alu/shift_left_imm.json",
        "/examples_alu/shift_right.json",
        "/examples_alu/shift_right_imm.json"
      ).foreach { file =>
        new TensorAluJsonTest(c, file)
        ResetProcedure.module()(c)
      }

    }
  }
}
