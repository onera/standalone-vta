package unittest.decode

import chiseltest.iotesters.PeekPokeTester
import unittest.GenericTest
import vta.core._
import vta.util.config.Parameters

import scala.language.postfixOps

class ComputeDecodeTest(c: ComputeDecode, debug:Boolean = false)
  extends PeekPokeTester(c) {
  if (debug) {
    // Print the test name
    println("TEST NAME: \n\t ComputeDecodeTester")
  }

  // Instructions

  /*
   * INSTRUCTION 0: LOAD UOP
      dep - pop prev: 0, pop next: 0, push prev: 0, push next: 0
      DRAM: 0x00001000, SRAM:0x0000
      y: size=1, pad=[0, 0]
      x: size=1, stride=1, pad=[0, 0]
      l2g_queue = 0, g2l_queue = 0
      s2g_queue = 0, g2s_queue = 0
   */
  val I0 = BigInt("00000000400000000100010001000000", 16)
  val R0 = BigInt("00000001000100010000004000000000", 16) // reversed instruction field

  /*
   * INSTRUCTION 1: GEMM
      dep - pop prev: 0, pop next: 0, push prev: 1, push next: 0
      reset_out: 1
      range (0, 1)
      outer loop - iter: 1, wgt: 0, inp: 0, acc: 0
      inner loop - iter: 1, wgt: 0, inp: 0, acc: 0
      l2g_queue = 0, g2l_queue = 1
      s2g_queue = 0, g2s_queue = 0
   */
  val I1 = BigInt("a2002000080002000000000000000000", 16)
  val R1 = BigInt("000000000000000000020008002000a2", 16) // reversed instruction field

  /*
   * INSTRUCTION 2: LOAD INP
      dep - pop prev: 0, pop next: 1, push prev: 0, push next: 0
      DRAM: 0x00000100, SRAM:0x0000
      y: size=1, pad=[0, 0]
      x: size=1, stride=1, pad=[0, 0]
      l2g_queue = 0, g2l_queue = 0
      s2g_queue = 0, g2s_queue = 0
   */
  val I2 = BigInt("10010000040000000100010001000000", 16)
  val R2 = BigInt("00000001000100010000000400000110", 16) // reversed instruction field

  /*
   * INSTRUCTION 3: LOAD WGT
      dep - pop prev: 0, pop next: 0, push prev: 0, push next: 1
      DRAM: 0x00000020, SRAM:0x0000
      y: size=1, pad=[0, 0]
      x: size=1, stride=1, pad=[0, 0]
      l2g_queue = 1, g2l_queue = 0
      s2g_queue = 0, g2s_queue = 0
   */
  val I3 = BigInt("c0000080000000000100010001000000", 16)
  val R3 = BigInt("000000010001000100000000800000c0", 16) // reversed instruction field

  /*
   * INSTRUCTION 4: LOAD UOP
      dep - pop prev: 1, pop next: 0, push prev: 0, push next: 0
      DRAM: 0x00001001, SRAM:0x0001
      y: size=1, pad=[0, 0]
      x: size=1, stride=1, pad=[0, 0]
      l2g_queue = 0, g2l_queue = 0
      s2g_queue = 0, g2s_queue = 0
   */
  val I4 = BigInt("08040004400000000100010001000000", 16)
  val R4 = BigInt("00000001000100010000004004000408", 16) // reversed instruction field

  /*
   * INSTRUCTION 5: GEMM
      dep - pop prev: 0, pop next: 0, push prev: 0, push next: 1
      reset_out: 0
      range (1, 2)
      outer loop - iter: 1, wgt: 0, inp: 0, acc: 0
      inner loop - iter: 1, wgt: 0, inp: 0, acc: 0
      l2g_queue = 0, g2l_queue = 0
      s2g_queue = 0, g2s_queue = 1
   */
  val I5 = BigInt("42014000080002000000000000000000", 16)
  val R5 = BigInt("00000000000000000002000400400142", 16) // reversed instruction field

  /*
   * INSTRUCTION 6: STORE:
      dep - pop prev: 1, pop next: 0, push prev: 1, push next: 0
      DRAM: 0x00000300, SRAM:0x0000
      y: size=1, pad=[0, 0]
      x: size=1, stride=1, pad=[0, 0]
      l2g_queue = 0, g2l_queue = 0
      s2g_queue = 1, g2s_queue = 0
   */
  val I6 = BigInt("290200000c0000000100010001000000", 16)
  val R6 = BigInt("00000001000100010000000c00000229", 16) // reversed instruction field

  /*
   * INSTRUCTION 7: NOP-MEMORY-STAGE
      dep - pop prev: 0, pop next: 0, push prev: 0, push next: 1
      l2g_queue = 1, g2l_queue = 0
      s2g_queue = 1, g2s_queue = 0
   */
  val I7 = BigInt("40010000000000000000000000000000", 16)
  val R7 = BigInt("00000000000000000000000000000140", 16) // reversed instruction field

  /*
   * INSTRUCTION 8: NOP-COMPUTE-STAGE
      dep - pop prev: 1, pop next: 1, push prev: 0, push next: 0
      l2g_queue = 0, g2l_queue = 0
      s2g_queue = 0, g2s_queue = 0
   */
  val I8 = BigInt("18000000000000000000000000000000", 16)
  val R8 = BigInt("00000000000000000000000000000018", 16) // reversed instruction field

  /*
   * INSTRUCTION 9: FINISH
      l2g_queue = 0, g2l_queue = 0
      s2g_queue = 0, g2s_queue = 0
   */
  val I9 = BigInt("03000000000000000000000000000000", 16)
  val R9 = BigInt("00000000000000000000000000000003", 16) // reversed instruction field


  // INTERACT WITH THE MODULE
  // ------------------------
  // Decode I0 = LOAD UOP
  if (debug) {
    print("\n\n Decode I0 (load UOP):\n")
  }
  poke(c.io.inst, R0)
  // Expected output:
  expect(c.io.pop_prev, 0)
  expect(c.io.pop_next, 0)
  expect(c.io.push_prev, 0)
  expect(c.io.push_next, 0)
  expect(c.io.isLoadAcc, 0)
  expect(c.io.isLoadUop, 1)
  expect(c.io.isSync, 0)
  expect(c.io.isAlu, 0)
  expect(c.io.isGemm, 0)
  expect(c.io.isFinish, 0)


  // Decode I1 = GEMM RESET
  if (debug) {
    print("\n\n Decode I1 (gemm reset):\n")
  }
  poke(c.io.inst, R1)
  // Expected output:
  expect(c.io.pop_prev, 0)
  expect(c.io.pop_next, 0)
  expect(c.io.push_prev, 1)
  expect(c.io.push_next, 0)
  expect(c.io.isLoadAcc, 0)
  expect(c.io.isLoadUop, 0)
  expect(c.io.isSync, 0)
  expect(c.io.isAlu, 0)
  expect(c.io.isGemm, 1)
  expect(c.io.isFinish, 0)

  // Decode I4 = LOAD UOP
  if (debug) {
    print("\n\n Decode I4 (load UOP):\n")
  }
  poke(c.io.inst, R4)
  // Expected output:
  expect(c.io.pop_prev, 1)
  expect(c.io.pop_next, 0)
  expect(c.io.push_prev, 0)
  expect(c.io.push_next, 0)
  expect(c.io.isLoadAcc, 0)
  expect(c.io.isLoadUop, 1)
  expect(c.io.isSync, 0)
  expect(c.io.isAlu, 0)
  expect(c.io.isGemm, 0)
  expect(c.io.isFinish, 0)


  // Decode I5 = GEMM
  if(debug) {
    print("\n\n Decode I5 (gemm):\n")
  }
  poke(c.io.inst, R5)
  // Expected output:
  expect(c.io.pop_prev, 0)
  expect(c.io.pop_next, 0)
  expect(c.io.push_prev, 0)
  expect(c.io.push_next, 1)
  expect(c.io.isLoadAcc, 0)
  expect(c.io.isLoadUop, 0)
  expect(c.io.isSync, 0)
  expect(c.io.isAlu, 0)
  expect(c.io.isGemm, 1)
  expect(c.io.isFinish, 0)

  // Decode I7 = NOP-MEMORY-STAGE
  if (debug) {
    print("\n\n Decode I7 (nop-memory-stage):\n")
  }
  poke(c.io.inst, R7) // LOAD DECODE ...
  // Expected output:
  expect(c.io.pop_prev, 0)
  expect(c.io.pop_next, 0)
  expect(c.io.push_prev, 0)
  expect(c.io.push_next, 1)
  expect(c.io.isLoadAcc, 0)
  expect(c.io.isLoadUop, 0)
  expect(c.io.isSync, 0)
  expect(c.io.isAlu, 0)
  expect(c.io.isGemm, 0)
  expect(c.io.isFinish, 0)


  // Decode I8 = NOP-COMPUTE-STAGE
  if (debug) {
    print("\n\n Decode I8 (nop-compute-stage):\n")
  }
  poke(c.io.inst, R8)
  // Expected output:
  expect(c.io.pop_prev, 1)
  expect(c.io.pop_next, 1)
  expect(c.io.push_prev, 0)
  expect(c.io.push_next, 0)
  expect(c.io.isLoadAcc, 0)
  expect(c.io.isLoadUop, 0)
  expect(c.io.isSync, 1) // ??? (NOP-COMPUTE-STAGE)
  expect(c.io.isAlu, 0)
  expect(c.io.isGemm, 0)
  expect(c.io.isFinish, 0)


  // Decode I9 = FINISH
  if (debug) {
    print("\n\n Decode I9 (finish):\n")
  }
  poke(c.io.inst, R9)
  // Expected output:
  expect(c.io.pop_prev, 0)
  expect(c.io.pop_next, 0)
  expect(c.io.push_prev, 0)
  expect(c.io.push_next, 0)
  expect(c.io.isLoadAcc, 0)
  expect(c.io.isLoadUop, 0)
  expect(c.io.isSync, 0)
  expect(c.io.isAlu, 0)
  expect(c.io.isGemm, 0)
  expect(c.io.isFinish, 1)


  // OTHERS INSTRUCTIONS (alternative)
  if (debug) {
    // Alternative INSN test
    //val Itest = BigInt("00000100010001000000040000000000", 16) // test
    print("\n\n Decode Itest:\n")
    poke(c.io.inst, I0)
    // Read:
    println(s"POP_PREV = ${peek(c.io.pop_prev)}")
    println(s"POP_NEXT = ${peek(c.io.pop_next)}")
    println(s"PUSH_PREV = ${peek(c.io.push_prev)}")
    println(s"PUSH_NEXT = ${peek(c.io.push_next)}")
    println(s"isLoadAcc = ${peek(c.io.isLoadAcc)}")
    println(s"isLoadUop = ${peek(c.io.isLoadUop)}")
    println(s"isSync = ${peek(c.io.isSync)}")
    println(s"isAlu = ${peek(c.io.isAlu)}")
    println(s"isGemm = ${peek(c.io.isGemm)}")
    println(s"isFinish = ${peek(c.io.isFinish)}")
    print("\n")

    // END OF THE TESTS
    print("\n\t END COMPUTE DECODE! \n\n")
  }
}

class AlternativeComputeMemDecodeTest(c: AlternativeComputeMemDecode, debug: Boolean = false)
  extends PeekPokeTester(c) {
  if (debug) {
    // Print the test name
    println("TEST NAME: \n\t AlternativeComputeMemDecodeTester")
  }

  // Instructions

  // INSTRUCTION 0: LOAD UOP
  val I0 = BigInt("00000000400000000100010001000000", 16)
  val R0 = BigInt("00000001000100010000004000000000", 16) // reversed instruction field

  // INSTRUCTION 2: LOAD INP
  val I2 = BigInt("10010000040000000100010001000000", 16)
  val R2 = BigInt("00000001000100010000000400000110", 16) // reversed instruction field

  // INSTRUCTION 3: LOAD WGT
  val I3 = BigInt("c0000080000000000100010001000000", 16)
  val R3 = BigInt("000000010001000100000000800000c0", 16) // reversed instruction field

  // INSTRUCTION 4: LOAD UOP
  val I4 = BigInt("08040004400000000100010001000000", 16)
  val R4 = BigInt("00000001000100010000004004000408", 16) // reversed instruction field

  // INSTRUCTION 7: NOP-MEMORY-STAGE
  val I7 = BigInt("40010000000000000000000000000000", 16)
  val R7 = BigInt("00000000000000000000000000000140", 16) // reversed instruction field

  // INSTRUCTION 8: NOP-COMPUTE-STAGE
  val I8 = BigInt("18000000000000000000000000000000", 16)
  val R8 = BigInt("00000000000000000000000000000018", 16) // reversed instruction field


  // INTERACT WITH THE MODULE
  // ------------------------
  // Decode I0 = LOAD UOP
  if (debug) {
    print("\n\n Decode I0 (load UOP):\n")
  }
  poke(c.io.inst, R0)
  // Expected output:
  expect(c.io.op, 0)
  expect(c.io.pop_prev, 0)
  expect(c.io.pop_next, 0)
  expect(c.io.push_prev, 0)
  expect(c.io.push_next, 0)
  expect(c.io.id, 0)
  expect(c.io.sram_offset, 0)
  expect(c.io.dram_offset, 4096)
  expect(c.io.ysize, 1)
  expect(c.io.xsize, 1)
  expect(c.io.xstride, 1)
  expect(c.io.ypad_0, 0)
  expect(c.io.ypad_1, 0)
  expect(c.io.xpad_0, 0)
  expect(c.io.xpad_1, 0)


  // Decode I2 = LOAD INP
  if (debug) {
    print("\n\n Decode I2 (load INP):\n")
  }
  poke(c.io.inst, R2)
  // Expected output:
  expect(c.io.op, 0)
  expect(c.io.pop_prev, 0)
  expect(c.io.pop_next, 1)
  expect(c.io.push_prev, 0)
  expect(c.io.push_next, 0)
  expect(c.io.id, 2)
  expect(c.io.sram_offset, 0)
  expect(c.io.dram_offset, 256)
  expect(c.io.ysize, 1)
  expect(c.io.xsize, 1)
  expect(c.io.xstride, 1)
  expect(c.io.ypad_0, 0)
  expect(c.io.ypad_1, 0)
  expect(c.io.xpad_0, 0)
  expect(c.io.xpad_1, 0)

  // END OF THE TESTS
  if (debug) {
    print("\n\t END ALTERNATIVE COMPUTE MEM DECODE! \n\n")
  }
}

class AlternativeComputeGemmDecodeTest(c: AlternativeComputeGemmDecode, debug:Boolean = false)
  extends PeekPokeTester(c) {
  if (debug) {
    // Print the test name
    println("TEST NAME: \n\t AlternativeComputeGemmDecodeTester")
  }

  // Instructions
  // INSTRUCTION 0: LOAD UOP
  // I1: GEMM reset
  val I1 = BigInt("a2002000080002000000000000000000", 16)
  val R1 = BigInt("000000000000000000020008002000a2", 16) // reversed instruction field

  // I5: GEMM
  val I5 = BigInt("42014000080002000000000000000000", 16)
  val R5 = BigInt("00000000000000000002000800400142", 16) // reversed instruction field


  // INTERACT WITH THE MODULE
  // ------------------------
  // Decode I0 = LOAD UOP
  if (debug) {
    print("\n\n Decode I1 (GEMM reset):\n")
  }
  poke(c.io.inst, R1)
  // Expected output:
  expect(c.io.op, 2)
  expect(c.io.pop_prev, 0)
  expect(c.io.pop_next, 0)
  expect(c.io.push_prev, 1)
  expect(c.io.push_next, 0)
  expect(c.io.reset, 1)
  expect(c.io.uop_begin, 0)
  expect(c.io.uop_end, 1)
  expect(c.io.lp_0, 1)
  expect(c.io.lp_1, 1)
  expect(c.io.empty_0, 0) // NOT USED
  expect(c.io.acc_0, 0)
  expect(c.io.acc_1, 0)
  expect(c.io.inp_0, 0)
  expect(c.io.inp_1, 0)
  expect(c.io.wgt_0, 0)
  expect(c.io.wgt_1, 0)


  // Decode I2 = LOAD INP
  if (debug) {
    print("\n\n Decode I5 (GEMM):\n")
  }
  poke(c.io.inst, R5)
  // Expected output:
  expect(c.io.op, 2)
  expect(c.io.pop_prev, 0)
  expect(c.io.pop_next, 0)
  expect(c.io.push_prev, 0)
  expect(c.io.push_next, 1)
  expect(c.io.reset, 0)
  expect(c.io.uop_begin, 1)
  expect(c.io.uop_end, 2)
  expect(c.io.lp_0, 1)
  expect(c.io.lp_1, 1)
  expect(c.io.empty_0, 0) // NOT USED
  expect(c.io.acc_0, 0)
  expect(c.io.acc_1, 0)
  expect(c.io.inp_0, 0)
  expect(c.io.inp_1, 0)
  expect(c.io.wgt_0, 0)
  expect(c.io.wgt_1, 0)

  if (debug) {
    // END OF THE TESTS
    print("\n\t END ALTERNATIVE COMPUTE GEMM DECODE! \n\n")
  }
}


/**
 * Execute the tests
 */
class ComputeDecodeTester extends GenericTest("ComputeDecodeTest", (p:Parameters) =>
  new ComputeDecode(),
  (c:ComputeDecode) => new ComputeDecodeTest(c))

class AlternativeComputeMemDecodeTester extends GenericTest("AlternativeComputeMemDecodeTest", (p:Parameters) =>
  new AlternativeComputeMemDecode(),
  (c:AlternativeComputeMemDecode) => new AlternativeComputeMemDecodeTest(c))

class AlternativeComputeGemmDecodeTester extends GenericTest("AlternativeComputeGemmDecodeTest", (p: Parameters) =>
  new AlternativeComputeGemmDecode(),
  (c: AlternativeComputeGemmDecode) => new AlternativeComputeGemmDecodeTest(c))

