/*
 * Licensed to the Apache Software Foundation (ASF) under one
 * or more contributor license agreements.  See the NOTICE file
 * distributed with this work for additional information
 * regarding copyright ownership.  The ASF licenses this file
 * to you under the Apache License, Version 2.0 (the
 * "License"); you may not use this file except in compliance
 * with the License.  You may obtain a copy of the License at
 *
 *   http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing,
 * software distributed under the License is distributed on an
 * "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY
 * KIND, either express or implied.  See the License for the
 * specific language governing permissions and limitations
 * under the License.
 */

package unittest

import unittest.util._
import vta.core._
import vta.tags
import vta.util.AnyFlatSpecSim

import scala.math.pow

@tags.UnitTests
class MatrixVectorMultiplicationTest extends AnyFlatSpecSim {

  behavior of "MatrixVectorMultiplication"

  /* mvm_ref
   *
   * This is a software function that computes dot product with a programmable shift
   * This is used as a reference for the hardware
   */
  def mvmRef(
      inp: Array[Int],
      wgt: Array[Array[Int]],
      shift: Int
  ): Array[Int] = {
    val size = inp.length
    val res = Array.fill(size) { 0 }
    for (i <- 0 until size) {
      var dot = 0
      for (j <- 0 until size) {
        dot += wgt(i)(j) * inp(j)
      }
      res(i) = dot * pow(2, shift).toInt
    }
    res
  }

  it should "compute on random data" in {
    simulate(new MatrixVectorMultiplication) { c =>
      val cycles = 5
      for (i <- 0 until cycles) {
        // generate data based on bits
        val inpGen = new RandomArray(c.size, c.inpBits)
        val wgtGen = new RandomArray(c.size, c.wgtBits)
        val in_a = inpGen.any
        val in_b = Array.fill(c.size) { wgtGen.any }
        val res = mvmRef(in_a, in_b, 0)
        val inpMask = Helper.getMask(c.inpBits)
        val wgtMask = Helper.getMask(c.wgtBits)
        val accMask = Helper.getMask(c.accBits)

        for (i <- 0 until c.size) {
          c.io.inp.data.bits(0)(i).poke(in_a(i) & inpMask)
          c.io.acc_i.data.bits(0)(i).poke(0)
          for (j <- 0 until c.size) {
            c.io.wgt.data.bits(i)(j).poke(in_b(i)(j) & wgtMask)
          }
        }

        c.io.reset.poke(0)

        c.io.inp.data.valid.poke(1)
        c.io.wgt.data.valid.poke(1)
        c.io.acc_i.data.valid.poke(1)

        c.clock.step()

        c.io.inp.data.valid.poke(0)
        c.io.wgt.data.valid.poke(0)
        c.io.acc_i.data.valid.poke(0)

        // wait for valid signal
        while (!c.io.acc_o.data.valid.peekBoolean()) {
          c.clock.step() // advance clock
        }
        if (c.io.acc_o.data.valid.peekBoolean()) {
          for (i <- 0 until c.size) {
            c.io.acc_o.data.bits(0)(i).expect(res(i) & accMask)
          }
        }
      }
    }
  }

  it should "run a simple matrix multiplication" in {

    val debug = false // FIXME make a cli option
    if (debug) {
      // Print the test name
      println(
        "TEST NAME: \n\t MVM_simple_matrix_multiply (b1_c1h1w16_c1h1w16)\n"
      )
    }

    // Generate data based on bits
    val in_a = Array(2, 2, 1, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0)
    val in_b = Array(
      Array(1, 1, -1, -1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0),
      Array(2, 2, -2, -2, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0),
      Array(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0),
      Array(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0),
      Array(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0),
      Array(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0),
      Array(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0),
      Array(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0),
      Array(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0),
      Array(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0),
      Array(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0),
      Array(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0),
      Array(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0),
      Array(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0),
      Array(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0),
      Array(0, 0, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0)
    )

    // Get the reference result
    val res = mvmRef(in_a, in_b, 0)

    simulate(new MatrixVectorMultiplication()) { c =>
      // Define the mask (conversion from signed to unsigned)
      val inpMask = Helper.getMask(c.inpBits)
      val wgtMask = Helper.getMask(c.wgtBits)
      val accMask = Helper.getMask(c.accBits)

      // Loading of the input, weight and accumulator data
      for (i <- 0 until c.size) {
        // for each value, the mask convert the Scala Int to a UInt with bitwidth of c.inpBits
        c.io.inp.data.bits(0)(i).poke(in_a(i) & inpMask)
        c.io.acc_i.data.bits(0)(i).poke(0)
        for (j <- 0 until c.size) {
          c.io.wgt.data.bits(i)(j).poke(in_b(i)(j) & wgtMask)
        }
      }

      // Unset the reset signal
      c.io.reset.poke(0)

      // Set validity signal
      c.io.inp.data.valid.poke(1)
      c.io.wgt.data.valid.poke(1)
      c.io.acc_i.data.valid.poke(1)

      // Clock step
      c.clock.step()

      // HW READ DATA!

      // Unset validity signal (data have been consumed)
      c.io.inp.data.valid.poke(0)
      c.io.wgt.data.valid.poke(0)
      c.io.acc_i.data.valid.poke(0)

      // Wait for valid signal from HW
      while (!c.io.acc_o.data.valid.peekBoolean()) {
        c.clock.step() // advance clock
      }

      if (debug) {
        // Print INPUT vector
        println("The input vector (INP with mask):")
        print(s"${c.io.inp.data.bits(0).peek()} \n\n")
        // Print WEIGHT tensor
        println("The weight tensor (WGT with mask):")
        for (i <- 0 until c.size) {
          print(s"${c.io.wgt.data.bits(i).peek()} \n")
        }
        print("\n")
        // Print the result from MatrixVectorMultiplication
        println("The output vector (OUT with mask):")
        print(s"${c.io.acc_o.data.bits(0).peek()} \n\n")
      }

      // Assertion
      if (c.io.acc_o.data.valid.peekBoolean()) {
        for (i <- 0 until c.size) {
          c.io.acc_o.data.bits(0)(i).expect(res(i) & accMask)
        }
      }
      if (debug) {
        // Everything is okay
        print("\t MATCH EXPECTATION! \n\n")
      }
    }
  }
}
