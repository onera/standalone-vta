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

package vta.core

import chisel3._
import vta.tags.UnitTests
import vta.util.AnyFlatSpecSim

/** TensorLoadPadSpec - the zero-padding path of TensorLoad.
  *
  * Drives strided 2D INP loads with a zero border and checks that the border
  * slots read back zero and the interior slots hold the loaded data at the
  * expected padded offsets.
  *
  * DRAM model (baddr 0): tensor t's element e == t*16 + e, tensors laid out
  * contiguously; xstride selects which DRAM tensors a scratchpad row pulls.
  */
@UnitTests
class TensorLoadPadSpec extends AnyFlatSpecSim {
  behavior of "TensorLoad zero padding"

  // MemDecode field widths, LSB-first (reverse of the Bundle declaration order
  // in core/Decode.scala, where the first field is the MSB).
  private def memInsn(
    op: Int,
    id: Int,
    ysize: Int,
    xsize: Int,
    xstride: Int,
    ypad0: Int,
    ypad1: Int,
    xpad0: Int,
    xpad1: Int,
    sramBase: Int,
    dramOffset: Int
  ): BigInt = {
    var v = BigInt(0)
    var sh = 0
    def push(value: Int, bits: Int): Unit = {
      v |= (BigInt(value) & ((BigInt(1) << bits) - 1)) << sh
      sh += bits
    }
    push(op, 3)
    push(0, 1) // pop_prev
    push(0, 1) // pop_next
    push(0, 1) // push_prev
    push(0, 1) // push_next
    push(id, 3)
    push(sramBase, 16) // sramOffset
    push(dramOffset, 32) // dram_offset
    push(0, 6) // empty_0
    push(ysize, 16)
    push(xsize, 16)
    push(xstride, 16)
    push(ypad0, 4)
    push(ypad1, 4)
    push(xpad0, 4)
    push(xpad1, 4)
    require(sh == 128, s"MemDecode packing is $sh bits, expected 128")
    v
  }

  /** Run one padded strided INP load and assert the whole scratchpad matrix.
    *
    * DRAM row r starts at tensor `r * xstride`; the scratchpad matrix is
    * (ysize + ypad0 + ypad1) rows x (xsize + xpad0 + xpad1) cols, row-major
    * from slot `sramBase`. Interior cell (r, c) holds DRAM tensor
    * `r * xstride + c`; every border cell is zero.
    */
  private def runPadCase(
    ysize: Int,
    xsize: Int,
    xstride: Int,
    ypad0: Int,
    ypad1: Int,
    xpad0: Int,
    xpad1: Int,
    sramBase: Int = 0
  ): Unit = simulate(new TensorLoadNarrowVME("inp")) { c =>
    val tp = new TensorParams("inp")(c.parameters)
    val beatBits = c.parameters(vta.shell.ShellKey).memParams.dataBits
    val elemBits = tp.tensorElemBits
    val elemsPerBeat = beatBits / elemBits
    val blockIn = tp.tensorWidth
    val mask = (BigInt(1) << elemBits) - 1

    // byte address -> one VME beat of elemsPerBeat consecutive elements,
    // lowest-addressed in the low bits.
    def beatAt(byteAddr: BigInt): BigInt = {
      val b = byteAddr / (beatBits / 8)
      (0 until elemsPerBeat).foldLeft(BigInt(0)) { (acc, i) =>
        acc | (((b * elemsPerBeat + i) & mask) << (i * elemBits))
      }
    }

    c.io.baddr.poke(0.U)
    c.io.start.poke(false.B)
    c.io.vme_rd.cmd.ready.poke(false.B)
    c.io.vme_rd.data.valid.poke(false.B)
    c.io.tensor.rd(0).idx.valid.poke(false.B)
    c.clock.step(2)

    c.io.inst.poke(
      memInsn(0, 2, ysize, xsize, xstride, ypad0, ypad1, xpad0, xpad1,
        sramBase, 0).U
    )
    c.io.start.poke(true.B)
    c.clock.step()
    c.io.start.poke(false.B)

    // VME slave: accept every command, stream len+1 sequential beats.
    var pending: List[(BigInt, Int, BigInt)] = Nil
    var guard = 0
    var doneSeen = false
    while (!doneSeen && guard < 50000) {
      val cmdValid = c.io.vme_rd.cmd.valid.peekBoolean()
      c.io.vme_rd.cmd.ready.poke(cmdValid.B)
      val newCmd =
        if (cmdValid)
          Some(
            (
              c.io.vme_rd.cmd.bits.addr.peek().litValue,
              c.io.vme_rd.cmd.bits.len.peek().litValue.toInt + 1,
              c.io.vme_rd.cmd.bits.tag.peek().litValue
            )
          )
        else None

      pending.headOption match {
        case Some((addr, left, tag)) =>
          c.io.vme_rd.data.valid.poke(true.B)
          c.io.vme_rd.data.bits.data.poke(beatAt(addr).U)
          c.io.vme_rd.data.bits.tag.poke(tag.U)
          c.io.vme_rd.data.bits.last.poke((left == 1).B)
        case None => c.io.vme_rd.data.valid.poke(false.B)
      }
      val dataFire =
        pending.nonEmpty && c.io.vme_rd.data.ready.peekBoolean()
      if (c.io.done.peekBoolean()) doneSeen = true
      c.clock.step()
      if (dataFire) {
        val (addr, left, tag) = pending.head
        pending =
          if (left > 1) (addr + (beatBits / 8), left - 1, tag) :: pending.tail
          else pending.tail
      }
      newCmd.foreach(nc => pending = pending :+ nc)
      guard += 1
    }
    c.io.vme_rd.cmd.ready.poke(false.B)
    c.io.vme_rd.data.valid.poke(false.B)
    assert(doneSeen, s"TensorLoad never asserted done (guard=$guard)")
    c.clock.step(4)

    val rows = ysize + ypad0 + ypad1
    val cols = xsize + xpad0 + xpad1
    val slots = sramBase until (sramBase + rows * cols)

    // Read back the whole matrix: hold idx.valid, one address per cycle, value
    // for slot i is on the port the cycle after it is presented.
    c.io.tensor.rd(0).idx.valid.poke(true.B)
    c.io.tensor.rd(0).idx.bits.poke(slots.head.U)
    c.clock.step()
    val got = slots.zipWithIndex.map { case (slot, i) =>
      val nextIdx = if (i + 1 < slots.size) slots(i + 1) else slot
      c.io.tensor.rd(0).idx.bits.poke(nextIdx.U)
      val v = (0 until blockIn).map(e =>
        c.io.tensor.rd(0).data.bits(0)(e).peek().litValue
      )
      c.clock.step()
      slot -> v
    }.toMap
    c.io.tensor.rd(0).idx.valid.poke(false.B)

    for (r <- 0 until rows; col <- 0 until cols) {
      val slot = sramBase + r * cols + col
      val interior =
        r >= ypad0 && r < ypad0 + ysize && col >= xpad0 && col < xpad0 + xsize
      val want =
        if (interior) {
          val t = (r - ypad0) * xstride + (col - xpad0)
          (0 until blockIn).map(e => BigInt(t * 16 + e))
        } else Seq.fill(blockIn)(BigInt(0))
      assert(
        got(slot) == want,
        s"case y=$ysize x=$xsize str=$xstride pad(y $ypad0/$ypad1 x $xpad0/$xpad1)" +
          s" slot $slot (r=$r c=$col ${if (interior) "data" else "border"}): " +
          s"got ${got(slot).mkString(",")} want ${want.mkString(",")}"
      )
    }
  }

  it should "border-fill and interior-load a symmetric 1-tensor pad (contiguous stride)" in {
    runPadCase(ysize = 2, xsize = 2, xstride = 2,
      ypad0 = 1, ypad1 = 1, xpad0 = 1, xpad1 = 1)
  }

  it should "handle asymmetric x/y padding" in {
    runPadCase(ysize = 3, xsize = 2, xstride = 2,
      ypad0 = 2, ypad1 = 1, xpad0 = 1, xpad1 = 3)
  }

  it should "handle a non-contiguous row stride (im2row-shaped gather)" in {
    runPadCase(ysize = 3, xsize = 2, xstride = 5,
      ypad0 = 1, ypad1 = 1, xpad0 = 2, xpad1 = 1)
  }

  it should "load into a nonzero sram base" in {
    runPadCase(ysize = 2, xsize = 2, xstride = 2,
      ypad0 = 1, ypad1 = 1, xpad0 = 1, xpad1 = 1, sramBase = 64)
  }
}
