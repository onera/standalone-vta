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

package vta.shell

import chisel3._
import chisel3.util.log2Ceil
import org.scalatest.matchers.should.Matchers
import vta.tags.UnitTests
import vta.util.AnyFlatSpecSim

import scala.collection.mutable.ArrayBuffer

/** VMESpec - read-path corner cases for the VTA Memory Engine.
  *
  * The VME is the AXI *master* (`io.mem`) that multiplexes several read clients
  * (`io.vme.rd`) onto one AXI read channel. These tests exercise the cases that
  * only surface with realistic AXI timing (which the full-system sims never hit
  * because their memory model keeps every client permanently ready):
  *
  *   1. Read-data backpressure - when a client stalls (`data.ready` low), the
  *      VME must hold the AXI R channel (`io.mem.r.ready` low) and NOT drop the
  *      beat. The original VME hard-wired `io.mem.r.ready := true.B` and gated
  *      client `data.valid` with `data.ready`, so a stalled client silently
  *      lost the beat and its burst never completed -> FPGA deadlock.
  *   2. Tag free-list - slots must be freed on the actual beat transfer so more
  *      than `RequestQueueDepth` reads can complete back-to-back without
  *      stalling.
  *   3. Tag routing - interleaved / out-of-order responses must reach the
  *      client identified by the returned AXI id, with the correct client tag.
  *
  * The testbench plays both roles: the core-side read client (drives `cmd`,
  * controls `data.ready`) and the DDR-side AXI slave (drives `ar.ready` and the
  * `r` response beats, echoing the id the VME allocated).
  */
@UnitTests
class VMESpec extends AnyFlatSpecSim with Matchers {
  behavior of "VME read path"

  private val reqQueueDepth = p(ShellKey).vmeParams.RequestQueueDepth
  private val memDataBits = p(ShellKey).memParams.dataBits


  /** Issue a read command from a client and wait until the VME accepts it. */
  private def issueClientCmd(
      dut: VME,
      client: Int,
      addr: BigInt,
      len: Int,
      tag: Int,
      maxWait: Int = 50
  ): Unit = {
    dut.io.vme.rd(client).cmd.valid.poke(true.B)
    dut.io.vme.rd(client).cmd.bits.addr.poke(addr.U)
    dut.io.vme.rd(client).cmd.bits.len.poke(len.U)
    dut.io.vme.rd(client).cmd.bits.tag.poke(tag.U)
    var n = 0
    while (!dut.io.vme.rd(client).cmd.ready.peekBoolean() && n < maxWait) {
      dut.clock.step(); n += 1
    }
    assert(
      dut.io.vme.rd(client).cmd.ready.peekBoolean(),
      s"VME never accepted the read command from client $client"
    )
    dut.clock.step() // command is enqueued on this edge
    dut.io.vme.rd(client).cmd.valid.poke(false.B)
  }

  /** Act as the AXI slave: accept the next AR and return its (id, addr, len).
    */
  private def acceptAR(
      dut: VME,
      maxWait: Int = 50
  ): (BigInt, BigInt, BigInt) = {
    dut.io.mem.ar.ready.poke(true.B)
    var n = 0
    while (!dut.io.mem.ar.valid.peekBoolean() && n < maxWait) {
      dut.clock.step(); n += 1
    }
    assert(dut.io.mem.ar.valid.peekBoolean(), "VME never issued an AR command")
    val id = dut.io.mem.ar.bits.id.peek().litValue
    val addr = dut.io.mem.ar.bits.addr.peek().litValue
    val len = dut.io.mem.ar.bits.len.peek().litValue
    dut.clock.step() // AR fires here (ar.valid & ar.ready)
    dut.io.mem.ar.ready.poke(false.B)
    (id, addr, len)
  }

  /** Respond to a read with `data`, with the target client always ready.
    * Returns the (data, tag, last) actually delivered to that client.
    */
  private def respondBurst(
      dut: VME,
      id: BigInt,
      data: Seq[BigInt],
      client: Int,
      maxWait: Int = 100
  ): Seq[(BigInt, BigInt, Boolean)] = {
    val out = ArrayBuffer[(BigInt, BigInt, Boolean)]()
    dut.io.vme.rd(client).data.ready.poke(true.B)
    for ((d, k) <- data.zipWithIndex) {
      val last = k == data.size - 1
      dut.io.mem.r.valid.poke(true.B)
      dut.io.mem.r.bits.id.poke(id.U)
      dut.io.mem.r.bits.data.poke(d.U)
      dut.io.mem.r.bits.last.poke(last.B)
      var n = 0
      while (!dut.io.mem.r.ready.peekBoolean() && n < maxWait) {
        dut.clock.step(); n += 1
      }
      assert(
        dut.io.mem.r.ready.peekBoolean(),
        s"VME never accepted read beat $k for id $id"
      )
      // The beat is being accepted this cycle; the client must see it now.
      val cd = dut.io.vme.rd(client).data
      assert(
        cd.valid.peekBoolean(),
        s"client $client data not valid while its beat is accepted"
      )
      out += ((
        cd.bits.data.peek().litValue,
        cd.bits.tag.peek().litValue,
        cd.bits.last.peekBoolean()
      ))
      dut.clock.step() // beat fires
    }
    dut.io.mem.r.valid.poke(false.B)
    dut.io.mem.r.bits.last.poke(false.B)
    dut.io.vme.rd(client).data.ready.poke(false.B)
    out.toSeq
  }

  it should "backpressure the AXI read channel and drop no beats when a client stalls" in {
    simulate(new VME,additionalResetCycles=2) { dut =>
      val client = 0
      val tag = 7
      val beats = Seq[BigInt](0xaa, 0xbb, 0xcc, 0xdd) // len = 3 (4 beats)

      issueClientCmd(dut, client, addr = 0x100, len = beats.size - 1, tag = tag)
      val (id, _, len) = acceptAR(dut)
      len shouldBe BigInt(beats.size - 1)

      val delivered = ArrayBuffer[BigInt]()
      for ((d, k) <- beats.zipWithIndex) {
        val last = k == beats.size - 1
        dut.io.mem.r.valid.poke(true.B)
        dut.io.mem.r.bits.id.poke(id.U)
        dut.io.mem.r.bits.data.poke(d.U)
        dut.io.mem.r.bits.last.poke(last.B)

        // Client stalls: the VME must NOT consume the beat (r.ready low).
        dut.io.vme.rd(client).data.ready.poke(false.B)
        for (_ <- 0 until 3) {
          dut.io.mem.r.ready.peekBoolean() shouldBe false
          dut.clock.step()
        }

        // Client releases: same cycle the beat must be accepted and correct.
        dut.io.vme.rd(client).data.ready.poke(true.B)
        dut.io.mem.r.ready.peekBoolean() shouldBe true
        dut.io.vme.rd(client).data.valid.peekBoolean() shouldBe true
        dut.io.vme.rd(client).data.bits.data.peek().litValue shouldBe d
        dut.io.vme.rd(client).data.bits.tag.peek().litValue shouldBe BigInt(tag)
        dut.io.vme.rd(client).data.bits.last.peekBoolean() shouldBe last
        delivered += dut.io.vme.rd(client).data.bits.data.peek().litValue
        dut.clock.step() // fire
        dut.io.vme.rd(client).data.ready.poke(false.B)
      }
      dut.io.mem.r.valid.poke(false.B)

      delivered.toSeq shouldBe beats
    }
  }

  it should "free tag slots so more than RequestQueueDepth reads complete" in {
    simulate(new VME,additionalResetCycles=2) { dut =>
      val client = 0
      val nReads = reqQueueDepth + 8 // exceed the 16-entry free-list
      for (r <- 0 until nReads) {
        val tag = r & 0xffff
        issueClientCmd(dut, client, addr = 0x100 * (r + 1), len = 0, tag = tag)
        val (id, _, _) = acceptAR(dut) // would time-out here if slots leaked
        val got = respondBurst(dut, id, Seq(BigInt(0x1000 + r)), client)
        got.size shouldBe 1
        got.head._1 shouldBe BigInt(0x1000 + r)
        got.head._2 shouldBe BigInt(tag)
        got.head._3 shouldBe true
        dut.clock.step()
      }
    }
  }

  it should "route interleaved responses to the correct client by id" in {
    simulate(new VME,additionalResetCycles=2) { dut =>
      dut.clock.step(2)

      // Two outstanding reads on different clients.
      issueClientCmd(dut, client = 0, addr = 0x100, len = 0, tag = 11)
      val (id0, _, _) = acceptAR(dut)
      issueClientCmd(dut, client = 2, addr = 0x200, len = 0, tag = 22)
      val (id2, _, _) = acceptAR(dut)
      id0 should not be id2

      // Respond out of program order: client 2 first, then client 0.
      val g2 = respondBurst(dut, id2, Seq(BigInt(0x222)), client = 2)
      g2.head._1 shouldBe BigInt(0x222)
      g2.head._2 shouldBe BigInt(22)

      val g0 = respondBurst(dut, id0, Seq(BigInt(0x111)), client = 0)
      g0.head._1 shouldBe BigInt(0x111)
      g0.head._2 shouldBe BigInt(11)
    }
  }

  // PENDING (#2): the tag free-list compares the FULL returned id against the
  // slot index (`i.U === io.mem.r.bits.id`, VME.scala), while routing only uses
  // the low log2(RequestQueueDepth) bits. So if the interconnect returns an id
  // with dirty upper bits, the beat is still routed correctly but its slot is
  // never freed; after `RequestQueueDepth` such reads the free-list drains and
  // the VME stops issuing AR -> `acceptAR` times out on read 17. The free-list
  // must key only on the bits the VME actually issued. Registered with `ignore`
  // until that fix lands; flip `ignore`->`it` afterwards.
  it should "free tag slots even when the slave returns dirty upper id bits (#2)" in {
    simulate(new VME,additionalResetCycles=2) { dut =>

      val client = 0
      // A bit set just above the RequestQueueAddrWidth slot-index field.
      val dirtyBit = BigInt(1) << log2Ceil(reqQueueDepth)
      val nReads = reqQueueDepth + 8 // exceed the free-list so a leak deadlocks
      for (r <- 0 until nReads) {
        val tag = r & 0xffff
        issueClientCmd(dut, client, addr = 0x100 * (r + 1), len = 0, tag = tag)
        val (id, _, _) =
          acceptAR(dut) // would time out on read 17 if slots leak
        val got =
          respondBurst(dut, id | dirtyBit, Seq(BigInt(0x1000 + r)), client)
        got.size shouldBe 1
        got.head._1 shouldBe BigInt(0x1000 + r)
        got.head._2 shouldBe BigInt(tag)
        dut.clock.step()
      }
    }
  }

  // PENDING (#4): the VME forwards a client's addr/len straight to io.mem.ar,
  // so a burst can straddle a 4 KB boundary, which AXI4 forbids for INCR bursts.
  // A compliant master must split such a request (the burst length is chosen in
  // the clients TensorLoad/Fetch/LoadUop). Registered with `ignore`; flip
  // `ignore`->`it` if/when the VME splits.
  ignore should "not issue AR bursts that cross a 4 KB boundary (#4)" in {
    simulate(new VME) { dut =>

      val bytesPerBeat = memDataBits / 8
      // 16 beats x 8 B = 128 B starting at 0xFC0 spans 0xFC0..0x1040 (crosses 0x1000).
      issueClientCmd(dut, client = 0, addr = 0xfc0, len = 15, tag = 0)
      val (_, addr, len) = acceptAR(dut)
      val burstEnd = (addr % 4096) + (len.toInt + 1) * bytesPerBeat
      burstEnd should be <= BigInt(4096)
    }
  }
}
