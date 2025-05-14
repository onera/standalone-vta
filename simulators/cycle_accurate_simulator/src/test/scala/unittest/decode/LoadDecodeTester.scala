package unittest.decode

import chiseltest.iotesters.PeekPokeTester
import unittest.GenericTest
import vta.core._
import vta.util.config.Parameters

import scala.language.postfixOps

class LoadDecodeTest(c: LoadDecode, debug: Boolean = false)
  extends PeekPokeTester(c) {
  if (debug) {
    // Print the test name
    println("TEST NAME: \n\t LoadDecodeTester")
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

  // Decode I2 = LOAD INP
  if (debug) {
    print("\n\n Decode I2 (load INP):\n")
  }
  poke(c.io.inst, R2)
  // Expected output:
  expect(c.io.pop_next, 1)
  expect(c.io.push_next, 0)
  expect(c.io.isInput, 1)
  expect(c.io.isWeight, 0)
  expect(c.io.isSync, 0)


  // Decode I3 = LOAD WGT => LoadDecode
  if (debug) {
    print("\n\n Decode I3 (load WGT):\n")
  }
  poke(c.io.inst, R3)
  // Expected output:
  expect(c.io.pop_next, 0)
  expect(c.io.push_next, 1)
  expect(c.io.isInput, 0)
  expect(c.io.isWeight, 1)
  expect(c.io.isSync, 0)

  // Decode I7 = NOP-MEMORY-STAGE
  if (debug) {
    print("\n\n Decode I7 (nop-memory-stage):\n")
  }
  poke(c.io.inst, R7)
  // Expected output:
  expect(c.io.pop_next, 0)
  expect(c.io.push_next, 1)
  expect(c.io.isInput, 0) // Inp but size = 0
  expect(c.io.isWeight, 0)
  expect(c.io.isSync, 1)
}



/**
 * Execute the tests
 */
class LoadDecodeTester extends GenericTest("LoadDecodeTest", (p:Parameters) =>
  new LoadDecode(),
  (c:LoadDecode) => new LoadDecodeTest(c))
