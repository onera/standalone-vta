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
import vta.interface.axi.AXIMaster
import vta.util.config._

/** Multi-master VTA Memory Engine (VME).
  *
  * Same `VMEClient` interface as [[VME]], but the single AXI master port is
  * replaced by `nMasters` independent ones. Each read client is statically
  * assigned to one port and the write client to another (possibly the same), so
  * clients on different ports never arbitrate against each other and the
  * aggregate DRAM bandwidth scales with the number of ports the interconnect
  * gives VTA.
  *
  * This raises the *aggregate* bandwidth of concurrently active clients (e.g.
  * an input load and a weight load in flight together). It does not speed up a
  * single client's burst, which still runs on one port at one beat per cycle.
  *
  * Each port is driven by a full [[VME]] instance restricted to the clients
  * assigned to it: the tag-array allocation and the AXI R-channel backpressure
  * logic are subtle (see the VMESpec header for the deadlock they once caused),
  * so they are reused rather than reimplemented. A lane's unassigned client
  * ports are tied off. The cost is one unused tag array and a few unused
  * command queues per lane.
  *
  * Because the lanes drive separate AXI ports they have separate id spaces, so
  * each lane allocating `ar.bits.id` from its own tag array stays correct.
  *
  * @param nMasters
  *   number of AXI master ports to expose.
  * @param readClientMap
  *   port index for each read client, one entry per `nReadClients`. Empty means
  *   round-robin (`client % nMasters`).
  * @param writeClientMaster
  *   port index carrying the write client.
  */
class VMESplit(
  nMasters: Int = 2,
  readClientMap: Seq[Int] = Seq.empty,
  writeClientMaster: Int = 0
)(implicit p: Parameters)
    extends Module {
  val io = IO(new Bundle {
    val mem = Vec(nMasters, new AXIMaster(p(ShellKey).memParams))
    val vme = new VMEClient
  })

  val nReadClients = p(ShellKey).vmeParams.nReadClients

  require(
    nMasters > 0,
    s"\n\n[VTA] [VMESplit] nMasters must be larger than 0\n\n"
  )

  val clientMap: Seq[Int] =
    if (readClientMap.isEmpty) Seq.tabulate(nReadClients)(_ % nMasters)
    else readClientMap

  require(
    clientMap.length == nReadClients,
    s"\n\n[VTA] [VMESplit] readClientMap must have one entry per read client " +
      s"(got ${clientMap.length}, expected $nReadClients)\n\n"
  )
  require(
    clientMap.forall(m => m >= 0 && m < nMasters),
    s"\n\n[VTA] [VMESplit] readClientMap entries must be in [0, $nMasters)," +
      s" got ${clientMap.mkString(",")}\n\n"
  )
  require(
    writeClientMaster >= 0 && writeClientMaster < nMasters,
    s"\n\n[VTA] [VMESplit] writeClientMaster must be in [0, $nMasters)," +
      s" got $writeClientMaster\n\n"
  )
  // A port with no client would be a dead AXI interface that the interconnect
  // still has to carry, which is always a mapping mistake.
  require(
    (0 until nMasters).forall(m =>
      clientMap.contains(m) || m == writeClientMaster
    ),
    s"\n\n[VTA] [VMESplit] every master must serve at least one client," +
      s" got readClientMap ${clientMap.mkString(",")} and" +
      s" writeClientMaster $writeClientMaster for $nMasters masters\n\n"
  )

  val lanes =
    Seq.tabulate(nMasters)(m => Module(new VME).suggestName(s"vme_$m"))

  for (m <- 0 until nMasters) {
    io.mem(m) <> lanes(m).io.mem
  }

  for (i <- 0 until nReadClients) {
    val owner = clientMap(i)
    io.vme.rd(i) <> lanes(owner).io.vme.rd(i)
    for (m <- 0 until nMasters if m != owner) {
      lanes(m).io.vme.rd(i).cmd.valid := false.B
      lanes(m).io.vme.rd(i).cmd.bits := DontCare
      lanes(m).io.vme.rd(i).data.ready := false.B
    }
  }

  io.vme.wr(0) <> lanes(writeClientMaster).io.vme.wr(0)
  for (m <- 0 until nMasters if m != writeClientMaster) {
    lanes(m).io.vme.wr(0).cmd.valid := false.B
    lanes(m).io.vme.wr(0).cmd.bits := DontCare
    lanes(m).io.vme.wr(0).data.valid := false.B
    lanes(m).io.vme.wr(0).data.bits := DontCare
  }
}

/** Named [[VMESplit]] port mappings. Use as `Module(VMESplit.perClient)`,
  * matching the `Module(Fetch())` convention in `Core`.
  */
object VMESplit {

  /** One AXI port per read client, the write client sharing port 0.
    *
    * With the default five read clients (see `Core`) this is:
    * {{{
    *   port 0 <- rd(0) fetch  + wr(0) out
    *   port 1 <- rd(1) uop
    *   port 2 <- rd(2) inp
    *   port 3 <- rd(3) wgt
    *   port 4 <- rd(4) acc
    * }}}
    * The write client shares with fetch because fetch is the lightest reader:
    * it pulls one instruction stream, while inp/wgt/acc stream tensor data.
    */
  def perClient(implicit p: Parameters): VMESplit = {
    val n = p(ShellKey).vmeParams.nReadClients
    new VMESplit(n, 0 until n, 0)
  }

  /** Round-robin: read client `i` goes to port `i % nMasters`, write to 0. */
  def roundRobin(nMasters: Int)(implicit p: Parameters): VMESplit =
    new VMESplit(nMasters)
}
