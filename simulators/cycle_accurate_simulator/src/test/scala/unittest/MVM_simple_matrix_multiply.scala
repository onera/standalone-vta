/*
 * Simple Matrix Multiply example (b1_c1h1w16_c1h1w16) executed on MatrixVectorMultiplication module (TensorGemm.scala)
 * -> Example based on unittest.MvmTest
 */

package unittest.gemm

import chiseltest.iotesters.PeekPokeTester
import unittest.GenericTest
import unittest.util._
import vta.core._
import vta.util.config.Parameters

import scala.math.pow

/**
 * Simple matrix multiply implemented in
 * ftdnn-fault-tolerance-dnn/code/B_VTA_TVM/TVM_investigation/instructions_investigation/examples_gemm/b1_c1h1w16_c1h1w16_simple_matrix_multiply/b1_c1h1w16_c1h1w16.py
 *
 * @param c The hardware description of the MVM
 */
class MVM_simple_matrix_multiply(c: MatrixVectorMultiplication, debug: Boolean = false) extends PeekPokeTester(c) {

  /* mvm_ref
   *
   * This is a software function that computes dot product with a programmable shift
   * This is used as a reference for the hardware
   */
  def mvmRef(inp: Array[Int], wgt: Array[Array[Int]], shift: Int): Array[Int] = {
    val size = inp.length
    val res = Array.fill(size) {
      0
    }
    for (i <- 0 until size) {
      var dot = 0
      for (j <- 0 until size) {
        dot += wgt(i)(j) * inp(j)
      }
      res(i) = dot * pow(2, shift).toInt
    }
    res
  }

  if (debug) {
    // Print the test name
    println("TEST NAME: \n\t MVM_simple_matrix_multiply (b1_c1h1w16_c1h1w16)\n")
  }

  // Generate data based on bits
  val in_a = Array(2, 2, 1, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0)
  val in_b = Array(
    Array(1, 1, -1, -1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0),
    Array(2, 2, -2, -2, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0),
    Array(0, 0,  0,  0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0),
    Array(0, 0,  0,  0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0),
    Array(0, 0,  0,  0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0),
    Array(0, 0,  0,  0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0),
    Array(0, 0,  0,  0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0),
    Array(0, 0,  0,  0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0),
    Array(0, 0,  0,  0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0),
    Array(0, 0,  0,  0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0),
    Array(0, 0,  0,  0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0),
    Array(0, 0,  0,  0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0),
    Array(0, 0,  0,  0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0),
    Array(0, 0,  0,  0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0),
    Array(0, 0,  0,  0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0),
    Array(0, 0,  1,  0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0)
  )

  // Get the reference result
  val res = mvmRef(in_a, in_b, 0)

  // Define the mask (conversion from signed to unsigned)
  val inpMask = Helper.getMask(c.inpBits)
  val wgtMask = Helper.getMask(c.wgtBits)
  val accMask = Helper.getMask(c.accBits)

  // Loading of the input, weight and accumulator data
  for (i <- 0 until c.size) {
    // for each value, the mask convert the Scala Int to a UInt with bitwidth of c.inpBits
    poke(c.io.inp.data.bits(0)(i), in_a(i) & inpMask)
    poke(c.io.acc_i.data.bits(0)(i), 0)
    for (j <- 0 until c.size) {
      poke(c.io.wgt.data.bits(i)(j), in_b(i)(j) & wgtMask)
    }
  }

  // Unset the reset signal
  poke(c.io.reset, 0)

  // Set validity signal
  poke(c.io.inp.data.valid, 1)
  poke(c.io.wgt.data.valid, 1)
  poke(c.io.acc_i.data.valid, 1)

  // Clock step
  step(1)

  // HW READ DATA!

  // Unset validity signal (data have been consumed)
  poke(c.io.inp.data.valid, 0)
  poke(c.io.wgt.data.valid, 0)
  poke(c.io.acc_i.data.valid, 0)

  // Wait for valid signal from HW
  while (peek(c.io.acc_o.data.valid) == BigInt(0)) {
    step(1) // advance clock
  }

  if (debug) {
    // Print INPUT vector
    println("The input vector (INP with mask):")
    print(s"${peek(c.io.inp.data.bits(0))} \n\n")
    // Print WEIGHT tensor
    println("The weight tensor (WGT with mask):")
    for (i <- 0 until c.size) {
      print(s"${peek(c.io.wgt.data.bits(i))} \n")
    }
    print("\n")
    // Print the result from MatrixVectorMultiplication
    println("The output vector (OUT with mask):")
    print(s"${peek(c.io.acc_o.data.bits(0))} \n\n")
  }

  // Assertion
  if (peek(c.io.acc_o.data.valid) == BigInt(1)) {
    for (i <- 0 until c.size) {
      expect(c.io.acc_o.data.bits(0)(i), res(i) & accMask)
    }
  }
  if (debug) {
    // Everything is okay
    print("\t MATCH EXPECTATION! \n\n")
  }
}



/**
 * Execute the tests
 */
class MVM_simple_matrix_multiply_Tester extends GenericTest("MVM_simple_matrix_multiply", (p:Parameters) =>
  new MatrixVectorMultiplication()(p),
  (c:MatrixVectorMultiplication) => new MVM_simple_matrix_multiply(c))
