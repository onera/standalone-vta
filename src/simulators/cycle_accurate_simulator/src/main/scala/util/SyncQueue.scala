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

package vta.util

import chisel3._
import chisel3.util._

/** Synchronous queue.
  *
  * Functionally a drop-in for `chisel3.util.Queue` (no flush / pipe / flow):
  * for `entries < 4` (or `forceSimpleQueue`) it uses a combinational `Mem`,
  * otherwise a `SyncReadMem` (BRAM-inferrable) with a one-cycle read.
  *
  * Why this is hand-rolled instead of `new Queue(useSyncReadMem = true)`: the
  * stock implementation requests `SyncReadMem(..., SyncReadMem.WriteFirst)` but
  * reads `deq_ptr` and writes `enq_ptr` on SEPARATE ports. On the
  * empty->nonempty refill `enq_ptr == deq_ptr`, so the read-during-write is a
  * CROSS-PORT collision. `WriteFirst` is only honorable for a same-port RDW; a
  * synthesized simple-dual-port BRAM cannot do cross-port WriteFirst, so Vivado
  * synthesizes the real BRAM behavior (the read returns STALE data for one
  * cycle) even though behavioral simulation models WriteFirst and returns the
  * new data. The result is `deq.bits` (=> the instruction decode) lagging
  * `deq.valid` (=> the `start` term) by one cycle on the first dequeue of a
  * refilled layer, which makes Compute's combinational `start & isLoadUop`
  * loadUop launch miss its single-cycle window and wedge (the FPGA-only
  * "MaxPool hang"). This module replicates WriteFirst with an EXPLICIT,
  * port-independent write-bypass register (a plain mux + reg that synthesis
  * honors), so `deq.bits` is the freshly-written head on a collision in both
  * simulation and silicon.
  */
class SyncQueueModule[T <: Data](
    gen: T,
    val entries: Int,
    useSyncReadMem: Boolean
) extends Module {
  require(entries > 0, "SyncQueueModule requires entries > 0")

  val io = IO(new QueueIO(gen, entries))

  val ram =
    if (useSyncReadMem) SyncReadMem(entries, gen, SyncReadMem.WriteFirst)
    else Mem(entries, gen)
  val enq_ptr = Counter(entries)
  val deq_ptr = Counter(entries)
  val maybe_full = RegInit(false.B)
  val ptr_match = enq_ptr.value === deq_ptr.value
  val empty = ptr_match && !maybe_full
  val full = ptr_match && maybe_full
  val do_enq = io.enq.fire
  val do_deq = io.deq.fire

  when(do_enq) {
    ram(enq_ptr.value) := io.enq.bits
    enq_ptr.inc()
  }
  when(do_deq) {
    deq_ptr.inc()
  }
  when(do_enq =/= do_deq) {
    maybe_full := do_enq
  }

  io.deq.valid := !empty
  io.enq.ready := !full

  if (useSyncReadMem) {
    val deq_ptr_next =
      Mux(deq_ptr.value === (entries.U - 1.U), 0.U, deq_ptr.value + 1.U)
    val r_addr = Mux(do_deq, deq_ptr_next, deq_ptr.value)
    val ramOut = ram.read(r_addr)
    // Explicit cross-port WriteFirst bypass (see class scaladoc): when the address
    // being read this cycle is also the address being written this cycle, the value
    // that appears at the read port next cycle must be the just-written data, not the
    // (stale) BRAM output. Replicate that in logic synthesis can honor.
    val rdwCollision = do_enq && (enq_ptr.value === r_addr)
    val bypassValid = RegNext(rdwCollision, init = false.B)
    val bypassData = RegNext(io.enq.bits)
    io.deq.bits := Mux(bypassValid, bypassData, ramOut)
  } else {
    io.deq.bits := ram(deq_ptr.value)
  }

  val ptr_diff = enq_ptr.value - deq_ptr.value
  if (isPow2(entries)) {
    io.count := Mux(maybe_full && ptr_match, entries.U, 0.U) | ptr_diff
  } else {
    io.count := Mux(
      ptr_match,
      Mux(maybe_full, entries.asUInt, 0.U),
      Mux(deq_ptr.value > enq_ptr.value, entries.asUInt + ptr_diff, ptr_diff)
    )
  }
}

/** Synchronous queue factory object */
object SyncQueue {

  /** SyncQueue implementation: if `entries < 4` or `forceSimpleQueue`, use a
    * simple combinational-read queue, else a `SyncReadMem`-backed queue with an
    * explicit read-during-write bypass (see [[SyncQueueModule]]).
    *
    * `pipe` / `flow` are accepted for source compatibility but are not
    * supported (no caller uses them); they must be false.
    *
    * @param gen
    *   chisel type of data loaded in the queue
    * @param entries
    *   depth of the queue
    * @param forceSimpleQueue
    * @param pipe
    * @param flow
    * @return
    */
  def apply[U <: Data](
      gen: U,
      entries: Int,
      forceSimpleQueue: Boolean = false,
      pipe: Boolean = false,
      flow: Boolean = false
  ): SyncQueueModule[U] = {
    require(
      !pipe && !flow,
      "-F- SyncQueue does not support pipe/flow"
    )
    new SyncQueueModule(
      gen,
      entries,
      useSyncReadMem = !(forceSimpleQueue || entries < 4)
    )
  }
}
