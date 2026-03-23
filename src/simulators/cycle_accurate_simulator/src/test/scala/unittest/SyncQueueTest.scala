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

import chisel3._
import chisel3.util._
import scala.util.Random
import unittest.AnyFlatSpecSim
import vta.util._
import vta.util.config._
import chisel3.simulator.ChiselSim
import chisel3.simulator.scalatest
import org.scalatest.flatspec.AnyFlatSpec
import vta.tags

class Checker(c: SyncQueueTestWrapper[UInt]) extends ChiselSim {

  def bits(bits: Int) = {
    c.io.tq.deq.bits.expect(bits)
    c.io.rq.deq.bits.expect(bits)

  }
  def ready(bits: Int) = {
    c.io.tq.enq.ready.expect(bits)
    c.io.rq.enq.ready.expect(bits)

  }
  def valid(bits: Int) = {
    c.io.tq.deq.valid.expect(bits)
    c.io.rq.deq.valid.expect(bits)

  }
  def status() = {
    val rv = c.io.rq.enq.ready.peek()
    c.io.tq.enq.ready.expect(rv)
    val rc = c.io.rq.count.peek()
    c.io.tq.count.expect(rc)
    val vv = c.io.rq.deq.valid.peek()
    c.io.tq.deq.valid.expect(vv)
    if (vv.litValue != 0) {
      val bv = c.io.rq.deq.bits.peek()
      c.io.tq.deq.bits.expect(bv)
    }
    c.io.rq.count.peek()
    c.io.tq.count.peek()
  }
}
class TestSyncQueueLongRead(c: SyncQueueTestWrapper[UInt]) extends ChiselSim {

  val chr = new Checker(c)

  def testFillRW(depth: Int) = {
    val qsize = c.io.tq.count.peek()
    require(qsize.litValue == 0, s"-F- An empty queue is expected ${qsize}")

    c.io.tq.deq.ready.poke(0)
    c.io.tq.enq.valid.poke(0)
    chr.ready(1)
    c.clock.step()

    // fill up to depth
    for (i <- 10 until 10 + depth) {
      c.io.tq.enq.bits.poke(i)
      c.io.tq.enq.valid.poke(1)
      chr.status()
      c.clock.step()

    }
    // read and write same cycle
    for (i <- 30 + depth until 30 + depth * 2) {
      c.io.tq.enq.valid.poke(1)
      c.io.tq.deq.ready.poke(1)
      c.io.tq.enq.bits.poke(i)
      chr.status()
      c.clock.step()
    }
    // read out
    for (i <- 0 until depth + 1) {
      c.io.tq.enq.valid.poke(0)
      c.io.tq.deq.ready.poke(1)
      c.io.tq.enq.bits.poke(99)
      chr.status()
      c.clock.step()
    }
  }
  for (i <- 1 until 28) {
    testFillRW(i)
  }
}
class TestSyncQueueWaveRead(c: SyncQueueTestWrapper[UInt]) extends ChiselSim {

  val chr = new Checker(c)

  def testFillRW(depth: Int) = {
    val qsize = c.io.tq.count.peek()
    require(qsize.litValue == 0, s"-F- An empty queue is expected ${qsize}")

    c.io.tq.deq.ready.poke(0)
    c.io.tq.enq.valid.poke(0)
    chr.ready(1)
    c.clock.step()

    // fill up to depth
    for (i <- 10 until 10 + depth) {
      c.io.tq.enq.bits.poke(i)
      c.io.tq.enq.valid.poke(1)
      chr.status()
      c.clock.step()

    }
    // read out, no write
    c.io.tq.enq.valid.poke(0)
    c.io.tq.deq.ready.poke(1)
    for (i <- 0 until 7) {
      chr.status()
      c.clock.step()
    }
    // fill more
    c.io.tq.deq.ready.poke(0)
    c.io.tq.enq.valid.poke(1)
    for (i <- 0 until 13) {
      c.io.tq.enq.bits.poke(99 + i)
      chr.status()
      c.clock.step()
    }
    // read out, no write
    c.io.tq.enq.valid.poke(0)
    c.io.tq.deq.ready.poke(1)
    for (i <- 1 until 14 + depth) {
      chr.status()
      c.clock.step()
    }
  }
  // read
  for (i <- 1 until 28) {
    testFillRW(i)
  }
}

class SyncQueueTestWrapper[T <: Data](gen: T, val entries: Int)
    extends Module() {

  val genType = gen

  val io = IO(new Bundle {
    val tq = new QueueIO(genType, entries)
    val rq = new QueueIO(genType, entries)

  })

  val tq = Module(SyncQueue(genType.asUInt, entries))
  val rq = Module(new Queue(genType.asUInt, entries))
  io.tq <> tq.io
  io.rq <> rq.io
  tq.io.enq.valid := RegNext(io.tq.enq.valid)
  tq.io.enq.bits := RegNext(io.tq.enq.bits)
  tq.io.deq.ready := RegNext(io.tq.deq.ready)
  // connect reference queue inport to test input
  rq.io.enq.valid := RegNext(io.tq.enq.valid)
  rq.io.enq.bits := RegNext(io.tq.enq.bits)
  rq.io.deq.ready := RegNext(io.tq.deq.ready)
}

@tags.UnitTests
class SyncQueueTest extends AnyFlatSpecSim {
  behavior of "SyncQueue"

  import chisel3.simulator.stimulus.ResetProcedure
  for (i <- Seq(1, 2, 3, 4, 13, 24)) {

    s"of depth ${i}" should "run correctly in long and wave read tests" in {
      simulate(new SyncQueueTestWrapper(UInt(16.W), i)) { c =>
        new TestSyncQueueLongRead(c)
        ResetProcedure.module()(c)
        new TestSyncQueueWaveRead(c)
      }
    }
  }

}
