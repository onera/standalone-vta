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
import org.scalatest.matchers.should.Matchers
import vta.tags.UnitTests
import vta.util.AnyFlatSpecSim

import scala.collection.mutable.ArrayBuffer

/** VMESplitSpec - the multi-AXI-master VME.
  *
  * `VMESplit` presents the same `VMEClient` interface as `VME`, but fans the
  * read/write clients out over `nMasters` independent AXI master ports so that
  * clients on different ports contend for nothing. What these tests check is
  * exactly the property a single-port `VME` cannot have: two clients assigned
  * to different ports make progress at the same time.
  *
  * The mapping under test splits the five read clients 3/2 and puts the single
  * write client on port 1, so every test can tell the ports apart:
  *
  * {{{
  *   port 0 <- rd(0) rd(1) rd(2)
  *   port 1 <- rd(3) rd(4) wr(0)
  * }}}
  *
  * As in [[VMESpec]] the testbench plays both roles: the core-side client
  * (drives `cmd`, controls `data.ready`) and the DDR-side AXI slave (drives
  * `ar.ready` and the `r` beats, echoing the id the VME allocated).
  */
@UnitTests
class VMESplitSpec extends AnyFlatSpecSim with Matchers {
  behavior of "VMESplit"

  private val nMasters = 2
  private val readClientMap = Seq(0, 0, 0, 1, 1)
  private val writeClientMaster = 1
  private val nReadClients = p(ShellKey).vmeParams.nReadClients

  private def dut() = new VMESplit(nMasters, readClientMap, writeClientMaster)

  /** Issue a read command from a client and wait until the VME accepts it. */
  private def issueClientCmd(
    dut: VMESplit,
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
      s"VMESplit never accepted the read command from client $client"
    )
    dut.clock.step() // command is enqueued on this edge
    dut.io.vme.rd(client).cmd.valid.poke(false.B)
  }

  /** Act as the AXI slave on `port`: accept the next AR, return its id. */
  private def acceptAR(dut: VMESplit, port: Int, maxWait: Int = 50): BigInt = {
    dut.io.mem(port).ar.ready.poke(true.B)
    var n = 0
    while (!dut.io.mem(port).ar.valid.peekBoolean() && n < maxWait) {
      dut.clock.step(); n += 1
    }
    assert(
      dut.io.mem(port).ar.valid.peekBoolean(),
      s"VMESplit never issued an AR command on port $port"
    )
    val id = dut.io.mem(port).ar.bits.id.peek().litValue
    dut.clock.step() // AR fires here (ar.valid & ar.ready)
    dut.io.mem(port).ar.ready.poke(false.B)
    id
  }

  /** Respond on `port` with `data`, with the target client always ready.
    * Returns the (data, tag, last) actually delivered to that client.
    */
  private def respondBurst(
    dut: VMESplit,
    port: Int,
    id: BigInt,
    data: Seq[BigInt],
    client: Int,
    maxWait: Int = 100
  ): Seq[(BigInt, BigInt, Boolean)] = {
    val out = ArrayBuffer[(BigInt, BigInt, Boolean)]()
    dut.io.vme.rd(client).data.ready.poke(true.B)
    for ((d, k) <- data.zipWithIndex) {
      val last = k == data.size - 1
      dut.io.mem(port).r.valid.poke(true.B)
      dut.io.mem(port).r.bits.id.poke(id.U)
      dut.io.mem(port).r.bits.data.poke(d.U)
      dut.io.mem(port).r.bits.last.poke(last.B)
      var n = 0
      while (!dut.io.mem(port).r.ready.peekBoolean() && n < maxWait) {
        dut.clock.step(); n += 1
      }
      assert(
        dut.io.mem(port).r.ready.peekBoolean(),
        s"VMESplit never accepted read beat $k for id $id on port $port"
      )
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
    dut.io.mem(port).r.valid.poke(false.B)
    dut.io.mem(port).r.bits.last.poke(false.B)
    dut.io.vme.rd(client).data.ready.poke(false.B)
    out.toSeq
  }

  it should "issue AR on both masters in the same cycle for clients on different ports" in {
    simulate(dut(), additionalResetCycles = 2) { d =>
      // rd(0) -> port 0, rd(3) -> port 1. Enqueue both before accepting either
      // AR, so a single shared AXI port would have to serialize them.
      issueClientCmd(d, client = 0, addr = 0x100, len = 0, tag = 11)
      issueClientCmd(d, client = 3, addr = 0x200, len = 0, tag = 33)

      // VME asserts ar.valid only while ar.ready is high, so open both first.
      d.io.mem(0).ar.ready.poke(true.B)
      d.io.mem(1).ar.ready.poke(true.B)

      var n = 0
      while (
        !(d.io.mem(0).ar.valid.peekBoolean() && d.io
          .mem(1)
          .ar
          .valid
          .peekBoolean()) && n < 50
      ) {
        d.clock.step(); n += 1
      }
      d.io.mem(0).ar.valid.peekBoolean() shouldBe true
      d.io.mem(1).ar.valid.peekBoolean() shouldBe true
      d.io.mem(0).ar.bits.addr.peek().litValue shouldBe BigInt(0x100)
      d.io.mem(1).ar.bits.addr.peek().litValue shouldBe BigInt(0x200)
    }
  }

  it should "route a returned beat to the client owning the port it arrived on" in {
    simulate(dut(), additionalResetCycles = 2) { d =>
      issueClientCmd(d, client = 2, addr = 0x300, len = 0, tag = 22)
      val id2 = acceptAR(d, port = 0)
      val g2 = respondBurst(d, port = 0, id2, Seq(BigInt(0x222)), client = 2)
      g2.head._1 shouldBe BigInt(0x222)
      g2.head._2 shouldBe BigInt(22)
      g2.head._3 shouldBe true

      issueClientCmd(d, client = 4, addr = 0x400, len = 0, tag = 44)
      val id4 = acceptAR(d, port = 1)
      val g4 = respondBurst(d, port = 1, id4, Seq(BigInt(0x444)), client = 4)
      g4.head._1 shouldBe BigInt(0x444)
      g4.head._2 shouldBe BigInt(44)
      g4.head._3 shouldBe true
    }
  }

  it should "keep serving one port while a client on the other port stalls" in {
    simulate(dut(), additionalResetCycles = 2) { d =>
      issueClientCmd(d, client = 0, addr = 0x100, len = 0, tag = 11)
      val id0 = acceptAR(d, port = 0)
      issueClientCmd(d, client = 3, addr = 0x200, len = 0, tag = 33)
      val id3 = acceptAR(d, port = 1)

      // Both slaves present a beat; only client 3 is ready.
      d.io.mem(0).r.valid.poke(true.B)
      d.io.mem(0).r.bits.id.poke(id0.U)
      d.io.mem(0).r.bits.data.poke(0x111.U)
      d.io.mem(0).r.bits.last.poke(true.B)
      d.io.vme.rd(0).data.ready.poke(false.B)

      d.io.mem(1).r.valid.poke(true.B)
      d.io.mem(1).r.bits.id.poke(id3.U)
      d.io.mem(1).r.bits.data.poke(0x333.U)
      d.io.mem(1).r.bits.last.poke(true.B)
      d.io.vme.rd(3).data.ready.poke(true.B)

      // The stalled client holds its own port only.
      d.io.mem(0).r.ready.peekBoolean() shouldBe false
      d.io.mem(1).r.ready.peekBoolean() shouldBe true
      d.io.vme.rd(3).data.valid.peekBoolean() shouldBe true
      d.io.vme.rd(3).data.bits.data.peek().litValue shouldBe BigInt(0x333)
      d.io.vme.rd(3).data.bits.tag.peek().litValue shouldBe BigInt(33)
    }
  }

  it should "drive the write channel only on the assigned master" in {
    simulate(dut(), additionalResetCycles = 2) { d =>
      d.io.vme.wr(0).cmd.valid.poke(true.B)
      d.io.vme.wr(0).cmd.bits.addr.poke(0x800.U)
      d.io.vme.wr(0).cmd.bits.len.poke(0.U)
      d.io.vme.wr(0).cmd.bits.tag.poke(0.U)
      d.io.vme.wr(0).cmd.ready.peekBoolean() shouldBe true
      d.clock.step()
      d.io.vme.wr(0).cmd.valid.poke(false.B)

      var n = 0
      while (!d.io.mem(writeClientMaster).aw.valid.peekBoolean() && n < 50) {
        d.io
          .mem(1 - writeClientMaster)
          .aw
          .valid
          .peekBoolean() shouldBe false
        d.clock.step(); n += 1
      }
      d.io.mem(writeClientMaster).aw.valid.peekBoolean() shouldBe true
      d.io.mem(writeClientMaster).aw.bits.addr.peek().litValue shouldBe BigInt(
        0x800
      )
      d.io.mem(1 - writeClientMaster).aw.valid.peekBoolean() shouldBe false
    }
  }

  it should "give every read client its own port under perClient" in {
    simulate(VMESplit.perClient, additionalResetCycles = 2) { d =>
      // rd(i) must appear on port i, for every read client.
      for (i <- 0 until nReadClients) {
        issueClientCmd(d, client = i, addr = 0x100 * (i + 1), len = 0, tag = i)
        val id = acceptAR(d, port = i)
        val got =
          respondBurst(d, port = i, id, Seq(BigInt(0x1000 + i)), client = i)
        got.head._1 shouldBe BigInt(0x1000 + i)
        got.head._2 shouldBe BigInt(i)
      }
    }
  }

  it should "share the write port with the fetch client under perClient" in {
    simulate(VMESplit.perClient, additionalResetCycles = 2) { d =>
      d.io.mem.length shouldBe nReadClients

      d.io.vme.wr(0).cmd.valid.poke(true.B)
      d.io.vme.wr(0).cmd.bits.addr.poke(0x800.U)
      d.io.vme.wr(0).cmd.bits.len.poke(0.U)
      d.io.vme.wr(0).cmd.bits.tag.poke(0.U)
      d.clock.step()
      d.io.vme.wr(0).cmd.valid.poke(false.B)

      var n = 0
      while (!d.io.mem(0).aw.valid.peekBoolean() && n < 50) {
        d.clock.step(); n += 1
      }
      d.io.mem(0).aw.valid.peekBoolean() shouldBe true
      d.io.mem(0).aw.bits.addr.peek().litValue shouldBe BigInt(0x800)
      for (m <- 1 until nReadClients) {
        d.io.mem(m).aw.valid.peekBoolean() shouldBe false
      }
    }
  }

  it should "reject a readClientMap that does not cover every read client" in {
    val thrown = intercept[Throwable] {
      circt.stage.ChiselStage.emitCHIRRTL(new VMESplit(2, Seq(0, 1), 0))
    }
    messageChain(thrown) should include("readClientMap")
  }

  private def messageChain(t: Throwable): String = {
    var cur: Throwable = t
    val sb = new StringBuilder
    while (cur != null) {
      sb.append(String.valueOf(cur.getMessage)).append('\n')
      cur = cur.getCause
    }
    sb.toString
  }
}
