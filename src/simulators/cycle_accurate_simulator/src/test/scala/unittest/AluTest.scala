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

import chisel3.util._
import scala.util.Random
import unittest.util._
import vta.core._
import vta.util.config._
import chisel3.simulator.ChiselSim
import vta.tags.UnitTests

object Alu_ref {
  /* alu_ref
   *
   * This is a software function used as a reference for the hardware
   */
  def alu(opcode: Int, a: Array[Int], b: Array[Int], width: Int): Array[Int] = {
    val size = a.length
    val mask = Helper.getMask(log2Ceil(width))
    val res = Array.fill(size) { 0 }

    if (opcode == 0) {
      for (i <- 0 until size) { // min
        res(i) = if (a(i) < b(i)) a(i) else b(i)
      }
    } else if (opcode == 1) { // max
      for (i <- 0 until size) {
        res(i) = if (a(i) < b(i)) b(i) else a(i)
      }
    } else if (opcode == 2) { // add
      for (i <- 0 until size) {
        res(i) = a(i) + b(i)
      }
    } else if (opcode == 3) { // right shift
      for (i <- 0 until size) {
        res(i) = a(i) >> (b(i) & mask).toInt
      }
    } else if (opcode == 4) { // left shift
      // HLS shift left by >> negative number
      // b always < 0 when opcode == 4
      for (i <- 0 until size) {
        res(i) = a(i) << ((-1 * b(i)) & mask).toInt
      }
    } else { // default
      for (i <- 0 until size) {
        res(i) = 0
      }
    }
    res
  }
}

@UnitTests
class AluTest extends AnyFlatSpecSim {
  behavior of "AluVector"

  it should "be consistent with AluRef for all opcodes on random data" in {
    val seed = 48
    simulate(new AluVector()) { c =>
      val r = new Random(seed)

      val num_ops = ALU_OP_NUM
      for (op <- 0 until num_ops) {
        // generate data based on bits
        val bits = c.io.acc_a.tensorElemBits
        val dataGen = new RandomArray(c.blockOut, bits, r)
        val in_a = dataGen.any
        val in_b = if (op != 4) dataGen.any else dataGen.negative
        val mask = Helper.getMask(bits)
        val res = Alu_ref.alu(op, in_a, in_b, bits)

        for (i <- 0 until c.blockOut) {
          c.io.acc_a.data.bits(0)(i).poke(in_a(i) & mask)
          c.io.acc_b.data.bits(0)(i).poke(in_b(i) & mask)
        }
        c.io.opcode.poke(op)

        c.io.acc_a.data.valid.poke(true)
        c.io.acc_b.data.valid.poke(true)

        c.clock.step(1)

        c.io.acc_a.data.valid.poke(false)
        c.io.acc_b.data.valid.poke(false)

        // wait for valid signal
        while (!c.io.acc_y.data.valid.peekBoolean()) {
          c.clock.step(1) // advance clock
        }
        if (c.io.acc_y.data.valid.peekBoolean()) {
          for (i <- 0 until c.blockOut) {
            c.io.acc_y.data.bits(0)(i).expect(res(i) & mask)
          }
        }
      }
    }
  }
}
