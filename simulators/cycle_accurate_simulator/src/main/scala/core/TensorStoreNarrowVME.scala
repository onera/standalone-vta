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
import vta.shell._

/** TensorStore.
 *
 * Store 1D and 2D tensors from out-scratchpad (SRAM) to main memory (DRAM).
 */
class TensorStoreNarrowVME(tensorType: String = "none", debug: Boolean = false)(
    implicit p: Parameters)
    extends Module {
  val tp = new TensorParams(tensorType)
  val mp = p(ShellKey).memParams
  val io = IO(new Bundle {
    val start = Input(Bool())
    val done = Output(Bool())
    val inst = Input(UInt(INST_BITS.W))
    val baddr = Input(UInt(mp.addrBits.W))
    val vme_wr = new VMEWriteMaster
    val tensor = new TensorClient(tensorType)
  })
  val tensorLength = tp.tensorLength
  val tensorWidth = tp.tensorWidth
  val tensorElemBits = tp.tensorElemBits
  val memBlockBits = tp.memBlockBits
  val memDepth = tp.memDepth
  val numMemBlock = tp.numMemBlock
  require(numMemBlock > 0, s"-F- TensorStore doesnt support pulse width" +
    s"wider than tensor width. Needed for stride support tensorWidth=${tensorWidth}")
  require(tp.splitWidth == 1 && tp.splitLength == 1, s"-F- ${tensorType} Cannot do split direct access")

  val writePipeLatency = tp.writePipeLatency
  // Store write is delayed by writePipeLatency
  // postpone start by the same number of cycles
  // expects instr and baddr are valid from start till done
  val localStart = ShiftRegister(io.start, writePipeLatency, false.B, true.B)

  val dec = io.inst.asTypeOf(new MemDecode)
  val waddr_cur = Reg(chiselTypeOf(io.vme_wr.cmd.bits.addr))
  val waddr_nxt = Reg(chiselTypeOf(io.vme_wr.cmd.bits.addr))
  val xcnt = Reg(chiselTypeOf(io.vme_wr.cmd.bits.len))
  val xlen = Reg(chiselTypeOf(io.vme_wr.cmd.bits.len))
  val xrem = Reg(chiselTypeOf(dec.xsize))
  val xsize = (dec.xsize << log2Ceil(tensorLength * numMemBlock))
  val xmax = (1 << mp.lenBits).U
  val xmax_bytes = ((1 << mp.lenBits) * mp.dataBits / 8).U
  val ycnt = Reg(chiselTypeOf(dec.ysize))
  val ysize = dec.ysize
  val tag = Reg(UInt(8.W))
  val set = Reg(UInt(8.W))

  val xfer_bytes = Reg(chiselTypeOf(io.vme_wr.cmd.bits.addr))
  val xstride_bytes = dec.xstride << log2Ceil(tensorLength * tensorWidth)
  val maskOffset = VecInit(Seq.fill(M_DRAM_OFFSET_BITS)(true.B)).asUInt
  val elemBytes = (p(CoreKey).batch * p(CoreKey).blockOut * p(CoreKey).outBits) / 8
  val pulse_bytes_bits = log2Ceil(mp.dataBits >> 3)

  val xfer_init_addr = io.baddr | (maskOffset & (dec.dram_offset << log2Ceil(elemBytes)))
  val xfer_split_addr = waddr_cur + xfer_bytes
  val xfer_stride_addr = waddr_nxt + xstride_bytes

  val xfer_init_bytes   = xmax_bytes - xfer_init_addr % xmax_bytes
  val xfer_init_pulses  = xfer_init_bytes >> pulse_bytes_bits
  val xfer_split_bytes  = xmax_bytes - xfer_split_addr % xmax_bytes
  val xfer_split_pulses = xfer_split_bytes >> pulse_bytes_bits
  val xfer_stride_bytes = xmax_bytes - xfer_stride_addr % xmax_bytes
  val xfer_stride_pulses= xfer_stride_bytes >> pulse_bytes_bits

  val sIdle :: sWriteCmd :: sWriteData :: sReadMem :: sWriteAck :: Nil = Enum(5)
  val state = RegInit(sIdle)

  // control
  switch(state) {
    is(sIdle) {
      xfer_bytes := xfer_init_bytes
      when (localStart) {
        state := sWriteCmd
        when (xsize < xfer_init_pulses) {
          assert(xsize > 0.U)
          xlen := xsize - 1.U
          xrem := 0.U
        }.otherwise {
          xlen := xfer_init_pulses - 1.U
          assert(xsize >= xfer_init_pulses)
          xrem := xsize - xfer_init_pulses
        }
      }
    }
    is(sWriteCmd) {
      when(io.vme_wr.cmd.ready) {
        state := sWriteData
      }
    }
    is(sWriteData) {
      when(io.vme_wr.data.ready) {
        when(xcnt === xlen) {
          state := sWriteAck
        }.elsewhen(tag === (numMemBlock - 1).U) {
          state := sReadMem
        }
      }
    }
    is(sReadMem) {
      state := sWriteData
    }
    is(sWriteAck) {
      when(io.vme_wr.ack) {
        when(xrem === 0.U) {
          when(ycnt === ysize - 1.U) {
            state := sIdle
          }.otherwise { // stride
            state := sWriteCmd
            xfer_bytes := xfer_stride_bytes
            when(xsize < xfer_stride_pulses) {
              assert(xsize > 0.U)
              xlen := xsize - 1.U
              xrem := 0.U
            }.otherwise {
              xlen := xfer_stride_pulses - 1.U
              assert(xsize >= xfer_stride_pulses)
              xrem := xsize - xfer_stride_pulses
            }
          }
        } // split
        .elsewhen(xrem < xfer_split_pulses) {
          state := sWriteCmd
          xfer_bytes := xfer_split_bytes
          assert(xrem > 0.U)
          xlen := xrem - 1.U
          xrem := 0.U
        }
        .otherwise {
          state := sWriteCmd
          xfer_bytes := xfer_split_bytes
          xlen := xfer_split_pulses - 1.U
          assert(xrem >= xfer_split_pulses)
          xrem := xrem - xfer_split_pulses
        }
      }
    }
  }

  // write-to-sram
  val tensorFile = Seq.fill(tensorLength) {
    SyncReadMem(memDepth, Vec(numMemBlock, UInt(memBlockBits.W)))
  }
  val wdata_t = Wire(Vec(numMemBlock, UInt(memBlockBits.W)))
  val no_mask = Wire(Vec(numMemBlock, Bool()))

  wdata_t := DontCare
  no_mask.foreach { m =>
    m := true.B
  }

  for (i <- 0 until tensorLength) {
    val inWrData = io.tensor.wr(0).bits.data(i).asUInt.asTypeOf(wdata_t)
    when(ShiftRegister(io.tensor.wr(0).valid, writePipeLatency, false.B, true.B)) {
      tensorFile(i).write(ShiftRegister(io.tensor.wr(0).bits.idx, writePipeLatency),
      ShiftRegister(inWrData, writePipeLatency), no_mask)
    }
  }

  // read-from-sram
  val stride = state === sWriteAck &
    io.vme_wr.ack &
    xcnt === xlen + 1.U &
    xrem === 0.U &
    ycnt =/= ysize - 1.U

  when(state === sIdle) {
    ycnt := 0.U
  }.elsewhen(stride) {
    ycnt := ycnt + 1.U
  }

  when(state === sWriteCmd || tag === (numMemBlock - 1).U) {
    tag := 0.U
  }.elsewhen(io.vme_wr.data.fire) {
    tag := tag + 1.U
  }

  when(
    state === sWriteCmd || (state =/= sReadMem && set === (tensorLength - 1).U && tag === (numMemBlock - 1).U)) {
    set := 0.U
  }.elsewhen(io.vme_wr.data.fire && tag === (numMemBlock - 1).U) {
    set := set + 1.U
  }

  val raddr_cur = Reg(UInt(tp.memAddrBits.W))
  val raddr_nxt = Reg(UInt(tp.memAddrBits.W))
  when(state === sIdle) {
    raddr_cur := dec.sram_offset
    raddr_nxt := dec.sram_offset
  }.elsewhen(io.vme_wr.data.fire && set === (tensorLength - 1).U && tag === (numMemBlock - 1).U) {
    raddr_cur := raddr_cur + 1.U
  }.elsewhen(stride) {
    raddr_cur := raddr_nxt + dec.xsize
    raddr_nxt := raddr_nxt + dec.xsize
  }

  val tread = Seq.tabulate(tensorLength) { i =>
    i.U ->
      tensorFile(i).read(raddr_cur, state === sWriteCmd | state === sReadMem)
  }
  val mdata = MuxLookup(set, 0.U.asTypeOf(chiselTypeOf(wdata_t)))(tread)

  // write-to-dram
  when(state === sIdle) {
    waddr_cur := xfer_init_addr
    waddr_nxt := xfer_init_addr
  }.elsewhen(state === sWriteAck && io.vme_wr.ack && xrem =/= 0.U) {
    waddr_cur := xfer_split_addr
  }.elsewhen(stride) {
    waddr_cur := xfer_stride_addr
    waddr_nxt := xfer_stride_addr
  }

  io.vme_wr.cmd.valid := state === sWriteCmd
  io.vme_wr.cmd.bits.addr := waddr_cur
  io.vme_wr.cmd.bits.len := xlen
  io.vme_wr.cmd.bits.tag := dec.sram_offset

  io.vme_wr.data.valid := state === sWriteData
  io.vme_wr.data.bits.data := mdata(tag)
  io.vme_wr.data.bits.strb := Fill(io.vme_wr.data.bits.strb.getWidth, true.B)

  when(state === sWriteCmd) {
    xcnt := 0.U
  }.elsewhen(io.vme_wr.data.fire) {
    xcnt := xcnt + 1.U
  }

  // disable external read-from-sram requests
  io.tensor.tieoffRead()

  // done
  io.done := state === sWriteAck & io.vme_wr.ack & xrem === 0.U & ycnt === ysize - 1.U

  // debug
  if (debug) {
    when(io.vme_wr.cmd.fire) {
      printf("[TensorStore] ysize:%x ycnt:%x raddr:%x waddr:%x len:%x rem:%x\n",
        ysize, ycnt, raddr_cur, waddr_cur, xlen, xrem)
    }
    when(io.vme_wr.data.fire) {
      printf("[TensorStore] data:%x\n", io.vme_wr.data.bits.data)
      printf("[TensorStore] strb:%x\n", io.vme_wr.data.bits.strb)
    }
    when(io.vme_wr.ack) {
      printf("[TensorStore] ack\n")
    }
  }
}
