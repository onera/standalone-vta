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
import vta.util._
import chisel3.simulator
import org.scalatest.flatspec.AnyFlatSpec
import chisel3.simulator.scalatest.ChiselSim
import vta.util.SimulationUtils.verilatorWithWaveDump
import unittest.UnitTests

class Checker2P(c: SyncQueue2PTestWrapper[UInt]) extends simulator.ChiselSim {
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
    if (vv != false.B) {
      val bv = c.io.rq.deq.bits.peek()
      c.io.tq.deq.bits.expect(bv)
    }
    c.io.rq.count.peek()
    c.io.tq.count.peek()
  }
}
class TestSyncQueue2PLongRead(c: SyncQueue2PTestWrapper[UInt])
    extends simulator.ChiselSim {

  val chr = new Checker2P(c)

  def testFillRW(depth: Int) = {
    val qsize = c.io.tq.count.peek()
    require(qsize.litValue == 0, s"-F- An empty queue is expected ${qsize}")

    c.io.tq.deq.ready.poke(false.B)
    c.io.tq.enq.valid.poke(false.B)
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
    for (_ <- 0 until depth + 1) {
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
class TestSyncQueue2PWaveRead(c: SyncQueue2PTestWrapper[UInt])
    extends simulator.ChiselSim {

  val chr = new Checker2P(c)

  def testFillRW(depth: Int) = {
    val qsize = c.io.tq.count.peek()
    require(qsize.litValue == 0, s"-F- An empty queue is expected ${qsize}")

    c.io.tq.deq.ready.poke(false.B)
    c.io.tq.enq.valid.poke(false.B)
    chr.ready(1)
    c.clock.step()

    // fill up to depth
    for (i <- 10 until 10 + depth) {
      c.io.tq.enq.bits.poke(i)
      c.io.tq.enq.valid.poke(true)
      chr.status()
      c.clock.step()

    }
    // read out, no write
    c.io.tq.enq.valid.poke(false.B)
    c.io.tq.deq.ready.poke(1)
    for (i <- 0 until 7) {
      chr.status()
      c.clock.step()
    }
    // fill more
    c.io.tq.deq.ready.poke(false.B)
    c.io.tq.enq.valid.poke(1)
    for (i <- 0 until 13) {
      c.io.tq.enq.bits.poke(99 + i)
      chr.status()
      c.clock.step()
    }
    // read out, no write
    c.io.tq.enq.valid.poke(false.B)
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
class SyncQueue2PTestWrapper[T <: Data](gen: T, val entries: Int)
    extends Module {

  val genType = gen

  val io = IO(new Bundle {
    val tq = new QueueIO(genType, entries)
    val rq = new QueueIO(genType, entries)

  })

  val tq = Module(new SyncQueue2PortMem(genType, entries))
  val rq = Module(new Queue(genType, entries))
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

class SyncQueue2PortMemTest extends AnyFlatSpec with ChiselSim {
  behavior of "SyncQueue2PortMem"

  implicit val verilatorFst: simulator.HasSimulator = verilatorWithWaveDump

  "queue 24" should "run for depth 24" taggedAs (UnitTests) in {
    simulate(new SyncQueue2PTestWrapper(UInt(24.W), 24)) {
      enableWaves()
      new TestSyncQueue2PLongRead(_)
    }
  }

  "long read test" should "run for depth 13" taggedAs (UnitTests) in {
    simulate(new SyncQueue2PTestWrapper(UInt(13.W), 13)) {
      new TestSyncQueue2PLongRead(_)
    }
  }

  "wave read test" should "run for depth 1" taggedAs (UnitTests) in {

    simulate(new SyncQueue2PTestWrapper(UInt(16.W), 1))(
      new TestSyncQueue2PWaveRead(_)
    )
  }

  "wave read test" should "run for depth 2" taggedAs (UnitTests) in {

    simulate(new SyncQueue2PTestWrapper(UInt(16.W), 2))(
      new TestSyncQueue2PWaveRead(_)
    )
  }
  "wave read test" should "run for depth 3" taggedAs (UnitTests) in {

    simulate(new SyncQueue2PTestWrapper(UInt(16.W), 3))(
      new TestSyncQueue2PWaveRead(_)
    )
  }
  "wave read test" should "run for depth 4" taggedAs (UnitTests) in {

    simulate(new SyncQueue2PTestWrapper(UInt(16.W), 4))(
      new TestSyncQueue2PWaveRead(_)
    )
  }

  "wave read test" should "run for depth 24" taggedAs (UnitTests) in {

    simulate(new SyncQueue2PTestWrapper(UInt(16.W), 24))(
      new TestSyncQueue2PWaveRead(_)
    )
  }

  "wave read test" should "run for depth 13" taggedAs (UnitTests) in {

    simulate(new SyncQueue2PTestWrapper(UInt(16.W), 13))(
      new TestSyncQueue2PWaveRead(_)
    )
  }

}
