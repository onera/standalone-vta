package simulatorTest.gemm

import chisel3._
import chisel3.util._
import unittest.util._
import vta.core._
import vta.util.config._

import scala.io._
import com.fasterxml.jackson.databind.ObjectMapper
import com.fasterxml.jackson.module.scala.DefaultScalaModule

import unittest.{GenericTest}
import unittest.AnyFlatSpecSim
import chisel3.simulator.PeekPokeAPI
import vta.tags

/** Similar to unittest.TensorGemmJsonTest with adaptation
  */

class TensorGemmTest(
    c: TensorGemmPipelinedSplit,
    fn: String = "/x.json",
    debug: Boolean = false
) extends PeekPokeAPI {

  // Print the test name
  if (debug) {
    print("TEST NAME: \n\t TensorGemmTester (take a JSON in input)\n")
    print(s"\tJSON: ${fn} \n\n")
  }

  // Read the JSON file
  val bufferedSource = Source.fromURL(getClass.getResource(fn))
  val mapper = new ObjectMapper()
  mapper.registerModule(DefaultScalaModule)
  val archState =
    mapper.readValue(bufferedSource.reader(), classOf[Map[String, Object]])
  bufferedSource.close

  // Decode the instruction
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
            val value = BigInt(v, 16)
            // Sign conversion
            if (value > 127) { value - 256 }
            else { value }
          }
        ).toArray
      }
    ).toMap
  }

  // Print scratchpad
  def print_scratchpad(
      scratchpad: Map[BigInt, Array[BigInt]],
      index: BigInt,
      name: String = "?"
  ): Unit = {
    print(s"\n ${name} scratchpad (index: ${index}) = \n (")
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
  c.io.start.poke(0)

  // Instruction fields with base conversion (hexadecimal)
  val dec_reset = BigInt(inst("reset"), 16)
  val uopBegin = BigInt(inst("uop_begin"), 16)
  val uopEnd = BigInt(inst("uop_end"), 16)
  assert(uopBegin < uopEnd)
  val lp0 = BigInt(inst("lp_0"), 16)
  val lp1 = BigInt(inst("lp_1"), 16)
  val acc0 = BigInt(inst("acc_0"), 16)
  val inp0 = BigInt(inst("inp_0"), 16)
  val wgt0 = BigInt(inst("wgt_0"), 16)
  val acc1 = BigInt(inst("acc_1"), 16)
  val inp1 = BigInt(inst("inp_1"), 16)
  val wgt1 = BigInt(inst("wgt_1"), 16)

  // Read instructions
  // Reset signal
  c.io.dec.reset.poke(dec_reset)
  // UOP_BGN
  c.io.dec.uopBegin.poke(uopBegin)
  // uopEnd
  c.io.dec.uopEnd.poke(uopEnd)
  // LOOP_EXTENT0
  c.io.dec.lp0.poke(lp0)
  // LOOP_EXTENT1
  c.io.dec.lp1.poke(lp1)
  // ACC_IDX_FACTOR0 (X0)
  c.io.dec.acc0.poke(acc0)
  // ACC_IDX_FACTOR1 (X1)
  c.io.dec.acc1.poke(acc1)
  // INP_IDX_FACTOR0 (Y0)
  c.io.dec.inp0.poke(inp0)
  // INP_IDX_FACTOR1 (Y1)
  c.io.dec.inp1.poke(inp1)
  // WGT_IDX_FACTOR0 (Z0)
  c.io.dec.wgt0.poke(wgt0)
  // WGT_IDX_FACTOR1 (Z1)
  c.io.dec.wgt1.poke(wgt1)

  if (debug) {
    print("Read instructions: \n")
    print(s"\t RESET: ${c.io.dec.reset.peek()} \n")
    print(s"\t uopBegin: ${c.io.dec.uopBegin.peek()} \n")
    print(s"\t uopEnd: ${c.io.dec.uopEnd.peek()} \n")
    print(s"\t LP0: ${c.io.dec.lp0.peek()} \n")
    print(s"\t LP1: ${c.io.dec.lp1.peek()} \n")
    print(s"\t ACC0: ${c.io.dec.acc0.peek()} \n")
    print(s"\t ACC1: ${c.io.dec.acc1.peek()} \n")
    print(s"\t INP0: ${c.io.dec.inp0.peek()} \n")
    print(s"\t INP1: ${c.io.dec.inp1.peek()} \n")
    print(s"\t WGT0: ${c.io.dec.wgt0.peek()} \n")
    print(s"\t WGT1: ${c.io.dec.wgt1.peek()} \n\n")
  }

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
    var valid = um.idx.valid.peekBoolean()
    var idx: Int = 0
    def logical_step(): Unit = {
      if (valid) {
        um.data.valid.poke(1)
        um.data.bits.u0.poke(scratchpad(idx)(0))
        um.data.bits.u1.poke(scratchpad(idx)(1))
        um.data.bits.u2.poke(scratchpad(idx)(2))
      } else {
        um.data.valid.poke(0)
      }
      valid = um.idx.valid.peekBoolean()
      idx = um.idx.bits.peek().litValue.toInt
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
    def logical_step(): Unit = {
      // Perform the defined operations for each emulated memory
      uop_mock.logical_step()
      inp_mock.logical_step()
      wgt_mock.logical_step()
      acc_mock.logical_step()
      acc_mock_wr.logical_step()

      if (c.io.uop.idx.valid.peekBoolean()) {
        val index = uop_indices.dequeue()
        c.io.uop.idx.bits.expect(
          index,
          "inconsistent uop index"
        )
      }
      if (c.io.acc.rd(0).idx.valid.peekBoolean()) {
        c.io.acc
          .rd(0)
          .idx
          .bits
          .expect(acc_indices.dequeue(), "inconsistent acc index")
      }
      if (c.io.inp.rd(0).idx.valid.peekBoolean()) {
        // c.io.inp
        //   .rd(0)
        //   .idx
        //   .bits
        //   .expect(inp_indices.dequeue(), "inconsistent inp index")
        if (debug) {
          // Print INPUT vector
          print(
            s"\n\nThe input vector (offset: ${c.io.inp.rd(0).idx.bits.peek()}): \n"
          )
          print_scratchpad(
            inp_scratchpad,
            c.io.inp.rd(0).idx.bits.peek().litValue,
            "INP"
          )
        }
      }
      if (c.io.wgt.rd(0).idx.valid.peekBoolean()) {
        val index = wgt_indices.dequeue()
        c.io.wgt
          .rd(0)
          .idx
          .bits
          .expect(
            index,
            "inconsistent wgt index"
          )
        if (debug) {
          // Print WEIGHT tensor
          print(
            s"\n\nThe weight tensor (offset: ${c.io.wgt.rd(0).idx.bits.peek()}): \n"
          )
          print_scratchpad(
            wgt_scratchpad,
            c.io.wgt.rd(0).idx.bits.peek().litValue,
            "WGT"
          )
        }
      }
      if (c.io.acc.wr(0).valid.peekBoolean()) {
        val index = accout_indices.dequeue()
        c.io.acc
          .wr(0)
          .bits
          .idx
          .expect(
            index,
            "inconsistent acc index"
          )
      }
      if (c.io.out.wr(0).valid.peekBoolean()) {
        val index = out_indices.dequeue()
        c.io.out
          .wr(0)
          .bits
          .idx
          .expect(
            index,
            "inconsistent"
          )
        if (debug) {
          // Print the result
          print(
            s"\n\nThe output vector (offset: ${c.io.out.wr(0).bits.idx.peek()}): \n"
          ) // Call acc and not out (???)
          print_scratchpad(
            acc_scratchpad,
            c.io.out.wr(0).bits.idx.peek().litValue,
            "ACC"
          )
        }
      }
      c.clock.step(1)
    }

    // Check if all the UOP are used
    def test_if_done(): Unit = {
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
    cnt_o <- BigInt(0) until lp0
    cnt_i <- BigInt(0) until lp1
    uop_idx <- uopBegin until uopEnd
  } {
    val u0 = uop_scratchpad(uop_idx.toInt)(0)
    val u1 = uop_scratchpad(uop_idx.toInt)(1)
    val u2 = uop_scratchpad(uop_idx.toInt)(2)

    mocks.uop_indices.enqueue(uop_idx)
    mocks.acc_indices.enqueue(u0 + acc0 * cnt_o + acc1 * cnt_i)
    mocks.inp_indices.enqueue(u1 + inp0 * cnt_o + inp1 * cnt_i)
    mocks.wgt_indices.enqueue(u2 + wgt0 * cnt_o + wgt1 * cnt_i)
    mocks.accout_indices.enqueue(u0 + acc0 * cnt_o + acc1 * cnt_i)

    if (dec_reset == 0) {
      mocks.out_indices.enqueue(u0 + acc0 * cnt_o + acc1 * cnt_i)
    }
  }

  // Unset (again ?) start signal
  c.io.start.poke(0)
  mocks.logical_step()
  c.io.state.expect(c.sIdle)

  // Set start signal (execute!)
  c.io.start.poke(1)

  // Specification
  val total_steps = (uopEnd - uopBegin) * lp0 * lp1

  // Timeout
  val max_count = 100 + 4 * total_steps

  // Count time to complete execuion
  var count = 0
  while (!c.io.done.peekBoolean() && count < max_count) {
    if (debug) {
      print(s"[CYCLE $count] \n")
    }
    mocks.logical_step()
    if (count == 0) {
      c.io.start.poke(0)
    }
    count += 1
  }

  // Execution is done
  assert(
    c.io.done.peekBoolean(),
    s"Signal done never high even after $count steps."
  )
  if (debug) {
    print(s"DEBUG: Signal done high after $count steps. \n")
  }

  // Reset signals (?)
  mocks.logical_step()
  c.io.done.expect(0)

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

@tags.UnitTests
class TensorGemmJsonTestSuite extends AnyFlatSpecSim {
  behavior of "TensorGemmPipelinedSplit"

  val debug = false
  def runSim(file: String) = {
    simulate(new TensorGemmPipelinedSplit) { c =>
      if (debug) enableWaves()
      new TensorGemmTest(c, file, debug)
    }
  }
  it should "compute a simple matrix multiplication" in runSim(
    "/examples_gemm/b1_c1h1w16_c1h1w16_simple_matrix_multiply.json"
  )

  it should "output channel" in runSim(
    "/examples_gemm/b1_c1h1w16_c2h1w16_output_channel.json"
  )
  it should "input channel" in runSim(
    "/examples_gemm/b1_c2h1w16_c1h1w16_input_channel.json"
  )

  it should "compute a full operation" in
    runSim("/examples_gemm/b1_c16h1w16_c16h1w16_full.json")

  it should "compute several batches" in runSim(
    "/examples_gemm/b2_c1h1w16_c1h1w16_batches.json"
  )
}

/* We must modify the configuration for this test */
//class TensorGemmTester_rows extends GenericTest("Rows", (p: Parameters) =>
//  new TensorGemmPipelinedSplit()(p),
//  (c: TensorGemmPipelinedSplit) => new TensorGemmTest(c, "/examples_gemm/b1_c1h2w16_c1h2w16_rows.json"))

/* Test for investigation */
class TensorGemmTester_test extends AnyFlatSpecSim {
  "Test instructions" should "run without assertions" in
    simulate(new TensorGemmPipelinedSplit()(p))(
      new TensorGemmTest(_, "/examples_gemm/test_instructions.json")
    )

}
/* Tests of performance */
class TensorGemmPerformanceTests extends AnyFlatSpecSim {
  behavior of "TensorGemmPipelinedSplit"

  it should "do atomic test" in
    simulate(new TensorGemmPipelinedSplit())(
      new TensorGemmTest(
        _,
        "/examples_gemm/performance_tests/LoopOut1_LoopIn1_UOP1.json",
        true
      )
    )

  it should "test 2 uop (ordered)" in
    simulate(new TensorGemmPipelinedSplit())(
      new TensorGemmTest(
        _,
        "/examples_gemm/performance_tests/LoopOut1_LoopIn1_UOP2.json",
        true
      )
    )

  it should "test 2 uop (reversed)" in
    simulate(new TensorGemmPipelinedSplit())(
      new TensorGemmTest(
        _,
        "/examples_gemm/performance_tests/LoopOut1_LoopIn1_UOP2_bis.json",
        true
      )
    )

  it should "test 2 loop in" in
    simulate(new TensorGemmPipelinedSplit())(
      new TensorGemmTest(
        _,
        "/examples_gemm/performance_tests/LoopOut1_LoopIn2_UOP1.json",
        true
      )
    )

  it should "test 2 loop out" in
    simulate(new TensorGemmPipelinedSplit())(
      new TensorGemmTest(
        _,
        "/examples_gemm/performance_tests/LoopOut2_LoopIn1_UOP1.json",
        true
      )
    )

  it should "Test block pattern" in
    simulate(new TensorGemmPipelinedSplit())(
      new TensorGemmTest(
        _,
        "/examples_gemm/performance_tests/block_matrix_pattern.json",
        true
      )
    )

  it should "Test block matrix uop" in
    simulate(new TensorGemmPipelinedSplit())(
      new TensorGemmTest(
        _,
        "/examples_gemm/performance_tests/block_matrix_uop.json",
        true
      )
    )
}
