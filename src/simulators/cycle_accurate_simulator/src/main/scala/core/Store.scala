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
import chisel3.layer._
import chisel3.util._
import vta.shell._
import vta.util.UserDefined.DebugLayer
import vta.util.config._

/** Store.
  *
  * Store results back to memory (DRAM) from scratchpads (SRAMs). This module
  * instantiate the TensorStore unit which is in charge of storing 1D and 2D
  * tensors to main memory.
  */
class Store(debug: Boolean = false)(implicit p: Parameters) extends Module {
  val mp = p(ShellKey).memParams
  val io = IO(new Bundle {
    val i_post = Input(Bool())
    val o_post = Output(Bool())
    val inst = Flipped(Decoupled(UInt(INST_BITS.W)))
    val out_baddr = Input(UInt(mp.addrBits.W))
    val vme_wr = new VMEWriteMaster
    val out = new TensorClient(tensorType = "out")
  })
  val sIdle :: sSync :: sExe :: Nil = Enum(3)
  val state = RegInit(sIdle)

  // Counter sized for the worst-case outstanding posts (a producer can run up
  // to instQueueEntries ahead); a saturating counter would drop posts and stall.
  val sem = Module(
    new Semaphore(
      counterBits = log2Ceil(p(CoreKey).instQueueEntries) + 1,
      counterInitValue = 0
    )
  )
  val instructionQueue = Module(
    new Queue(UInt(INST_BITS.W), p(CoreKey).instQueueEntries)
  )

  val dec = Module(new StoreDecode)
  dec.io.inst := instructionQueue.io.deq.bits

  val tensorStore = Module(TensorStore(tensorType = "out", debug))

  val start =
    instructionQueue.io.deq.valid & Mux(
      dec.io.pop_prev,
      sem.io.sready,
      true.B
    )
  val done = tensorStore.io.done

  // control
  switch(state) {
    is(sIdle) {
      when(start) {
        when(dec.io.isSync) {
          state := sSync
        }.elsewhen(dec.io.isStore) {
          state := sExe
        }
      }
    }
    is(sSync) {
      state := sIdle
    }
    is(sExe) {
      when(done) {
        state := sIdle
      }
    }
  }

  // instructions
  instructionQueue.io.enq <> io.inst
  instructionQueue.io.deq.ready := (state === sExe & done) | (state === sSync)

  // store
  tensorStore.io.start := state === sIdle & start & dec.io.isStore
  tensorStore.io.inst := instructionQueue.io.deq.bits
  tensorStore.io.baddr := io.out_baddr
  io.vme_wr <> tensorStore.io.vmeWr
  tensorStore.io.tensor <> io.out

  // semaphore
  sem.io.spost := io.i_post
  sem.io.swait := dec.io.pop_prev & (state === sIdle & start)
  io.o_post := dec.io.push_prev & ((state === sExe & done) | (state === sSync))

  // debug
  block(DebugLayer) {
    // start
    when(state === sIdle && start) {
      when(dec.io.isSync) {
        printf("[Store] start sync\n")
      }.elsewhen(dec.io.isStore) {
        printf("[Store] start\n")
      }
    }
    // done
    when(state === sSync) {
      printf("[Store] done sync\n")
    }
    when(state === sExe) {
      when(done) {
        printf("[Store] done\n")
      }
    }
  }
}
