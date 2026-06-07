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
import chisel3.util._
import vta.util.config._

/** NestedLoopCounter.
  *
  * The common triple-nested loop shared by the GEMM and ALU index generators:
  * an innermost uop counter (uop_begin..uop_end-1), then an inner loop (cnt_i /
  * lp_1), then an outer loop (cnt_o / lp_0). Each "index stream" carries an
  * outer accumulator and an inner accumulator; the inner step adds stride_1,
  * the outer step adds stride_0 and carries the new outer value into the inner.
  *
  * Streams are heterogeneous in width (GEMM: acc/inp/wgt; ALU: dst/src), so the
  * index/stride ports are MixedVecs sized per stream. Mixed-width adds truncate
  * to the index width on assignment, matching the original
  * `idx := idx + stride`.
  *
  * `advance` gates stepping and the terminal: GEMM ties it true (advances every
  * running cycle); the ALU drives it from its stutter/use-imm pacing. `flush`
  * forces the counter back to clean idle (clears `running`).
  */
class NestedLoopCounter(
    idxWidths: Seq[Int],
    strideWidths: Seq[Int],
    loopBits0: Int,
    loopBits1: Int,
    uopBits: Int
) extends Module {
  require(
    idxWidths.length == strideWidths.length,
    "-F- NestedLoopCounter: idx/stride stream count mismatch"
  )
  val n = idxWidths.length

  val io = IO(new Bundle {
    val start = Input(Bool())
    val flush = Input(Bool())
    val advance = Input(Bool())
    val lp_0 = Input(UInt(loopBits0.W))
    val lp_1 = Input(UInt(loopBits1.W))
    val uop_begin = Input(UInt(uopBits.W))
    val uop_end = Input(UInt(uopBits.W))
    val stride_0 = Input(MixedVec(strideWidths.map(w => UInt(w.W))))
    val stride_1 = Input(MixedVec(strideWidths.map(w => UInt(w.W))))
    val idx = Output(MixedVec(idxWidths.map(w => UInt(w.W))))
    val uop_idx = Output(UInt(uopBits.W))
    val cnt_o = Output(UInt(loopBits0.W))
    val cnt_i = Output(UInt(loopBits1.W))
    val last = Output(Bool())
    val running = Output(Bool())
  })

  io.last := false.B

  val running = RegInit(false.B)
  when(io.flush) {
    running := false.B
  }.elsewhen(!running && io.start) {
    running := true.B
  }.elsewhen(running && io.advance && io.last) {
    running := false.B
  }
  io.running := running

  val cnt_i = Reg(UInt(loopBits1.W))
  val cnt_o = Reg(UInt(loopBits0.W))
  val uop_idx = Reg(UInt(uopBits.W))
  val idx_i = Seq.tabulate(n)(k => Reg(UInt(idxWidths(k).W)))
  val idx_o = Seq.tabulate(n)(k => Reg(UInt(idxWidths(k).W)))

  io.cnt_o := cnt_o
  io.cnt_i := cnt_i
  io.uop_idx := uop_idx
  for (k <- 0 until n) io.idx(k) := idx_i(k)

  when(!running) {
    cnt_i := 0.U; cnt_o := 0.U
    for (k <- 0 until n) { idx_i(k) := 0.U; idx_o(k) := 0.U }
    uop_idx := io.uop_begin
  }.elsewhen(io.advance) {
    when(uop_idx =/= io.uop_end - 1.U) {
      uop_idx := uop_idx + 1.U
    }.otherwise {
      uop_idx := io.uop_begin
      when(cnt_i =/= io.lp_1 - 1.U) {
        cnt_i := cnt_i + 1.U
        for (k <- 0 until n) idx_i(k) := idx_i(k) + io.stride_1(k)
      }.otherwise {
        when(cnt_o =/= io.lp_0 - 1.U) {
          cnt_o := cnt_o + 1.U
          cnt_i := 0.U
          for (k <- 0 until n) {
            val tmp = idx_o(k) + io.stride_0(k)
            idx_o(k) := tmp
            idx_i(k) := tmp
          }
        }.otherwise {
          io.last := true.B
        }
      }
    }
  }
}
