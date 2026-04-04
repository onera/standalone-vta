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

/** TensorStore.
  *
  * Store 1D and 2D tensors from out-scratchpad (SRAM) to main memory (DRAM).
  */
case class TensorStoreNarrowVME(
    tensorType: String = "none",
    debug: Boolean = false
)(implicit
    val
    parameters: Parameters
) extends Module
    with TensorStore {
  val io: TensorStoreIf = IO(new TensorStoreIf())
  val tensorLength = tp.tensorLength
  val tensorWidth = tp.tensorWidth
  val tensorElemBits = tp.tensorElemBits
  val memBlockBits = tp.memBlockBits
  val memDepth = tp.memDepth
  val numMemBlock = tp.numMemBlock
  require(
    numMemBlock > 0,
    s"-F- TensorStore doesnt support pulse width" +
      s"wider than tensor width. Needed for stride support tensorWidth=${tensorWidth}"
  )
  require(
    tp.splitWidth == 1 && tp.splitLength == 1,
    s"-F- ${tensorType} Cannot do split direct access"
  )

  val writePipeLatency = tp.writePipeLatency
  // Store write is delayed by writePipeLatency
  // postpone start by the same number of cycles
  // expects instr and baddr are valid from start till done
  val localStart = ShiftRegister(io.start, writePipeLatency, false.B, true.B)

  val dec = io.inst.asTypeOf(new MemDecode)
  val waddrCur = Reg(chiselTypeOf(io.vmeWr.cmd.bits.addr))
  val waddrNxt = Reg(chiselTypeOf(io.vmeWr.cmd.bits.addr))
  val xcnt = Reg(chiselTypeOf(io.vmeWr.cmd.bits.len))
  val xlen = Reg(chiselTypeOf(io.vmeWr.cmd.bits.len))
  val xrem = Reg(chiselTypeOf(dec.xsize))
  val xsize = (dec.xsize << log2Ceil(tensorLength * numMemBlock))
  val xmax = (1 << mp.lenBits).U
  val xmaxBytes = ((1 << mp.lenBits) * mp.dataBits / 8).U
  val ycnt = Reg(chiselTypeOf(dec.ysize))
  val ysize = dec.ysize
  val tag = Reg(UInt(log2Ceil(numMemBlock).W))
  val set = Reg(UInt(8.W))

  val xferBytes = Reg(chiselTypeOf(io.vmeWr.cmd.bits.addr))
  val xstride_bytes = dec.xstride << log2Ceil(tensorLength * tensorWidth)
  val maskOffset = VecInit(Seq.fill(M_DRAM_OFFSET_BITS)(true.B)).asUInt
  val elemBytes =
    (parameters(CoreKey).batch * parameters(CoreKey).blockOut * parameters(
      CoreKey
    ).outBits) / 8
  val pulse_bytes_bits = log2Ceil(mp.dataBits >> 3)

  val xferInitAddr =
    io.baddr | (maskOffset & (dec.dram_offset << log2Ceil(elemBytes)))
  val xferSplitAddr = waddrCur + xferBytes
  val xferStrideAddr = waddrNxt + xstride_bytes

  val xferInitBytes = xmaxBytes - xferInitAddr % xmaxBytes
  val xferInitPulses = xferInitBytes >> pulse_bytes_bits
  val xferSplitBytes = xmaxBytes - xferSplitAddr % xmaxBytes
  val xferSplitPulses = xferSplitBytes >> pulse_bytes_bits
  val xferStrideBytes = xmaxBytes - xferStrideAddr % xmaxBytes
  val xferStridePulses = xferStrideBytes >> pulse_bytes_bits

  val sIdle :: sWriteCmd :: sWriteData :: sReadMem :: sWriteAck :: Nil = Enum(5)
  val state = RegInit(sIdle)

  // control
  switch(state) {
    is(sIdle) {
      xferBytes := xferInitBytes
      when(localStart) {
        state := sWriteCmd
        when(xsize < xferInitPulses) {
          assert(xsize > 0.U)
          xlen := xsize - 1.U
          xrem := 0.U
        }.otherwise {
          xlen := xferInitPulses - 1.U
          assert(xsize >= xferInitPulses)
          xrem := xsize - xferInitPulses
        }
      }
    }
    is(sWriteCmd) {
      when(io.vmeWr.cmd.ready) {
        state := sWriteData
      }
    }
    is(sWriteData) {
      when(io.vmeWr.data.ready) {
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
      when(io.vmeWr.ack) {
        when(xrem === 0.U) {
          when(ycnt === ysize - 1.U) {
            state := sIdle
          }.otherwise { // stride
            state := sWriteCmd
            xferBytes := xferStrideBytes
            when(xsize < xferStridePulses) {
              assert(xsize > 0.U)
              xlen := xsize - 1.U
              xrem := 0.U
            }.otherwise {
              xlen := xferStridePulses - 1.U
              assert(xsize >= xferStridePulses)
              xrem := xsize - xferStridePulses
            }
          }
        } // split
          .elsewhen(xrem < xferSplitPulses) {
            state := sWriteCmd
            xferBytes := xferSplitBytes
            assert(xrem > 0.U)
            xlen := xrem - 1.U
            xrem := 0.U
          }
          .otherwise {
            state := sWriteCmd
            xferBytes := xferSplitBytes
            xlen := xferSplitPulses - 1.U
            assert(xrem >= xferSplitPulses)
            xrem := xrem - xferSplitPulses
          }
      }
    }
  }

  // write-to-sram
  val tensorFile = Seq.fill(tensorLength) {
    Mem(memDepth, Vec(numMemBlock, UInt(memBlockBits.W)))
  }
  val wdata_t = Wire(Vec(numMemBlock, UInt(memBlockBits.W)))
  val no_mask = Wire(Vec(numMemBlock, Bool()))

  wdata_t := DontCare
  no_mask.foreach { m =>
    m := true.B
  }

  val writeDelayedEnable =
    ShiftRegister(io.tensor.wr(0).valid, writePipeLatency, false.B, true.B)
  for (i <- 0 until tensorLength) {
    val inWrData = io.tensor.wr(0).bits.data(i).asUInt.asTypeOf(wdata_t)
    when(writeDelayedEnable) {
      tensorFile(i).write(
        ShiftRegister(io.tensor.wr(0).bits.idx, writePipeLatency),
        ShiftRegister(inWrData, writePipeLatency),
        no_mask
      )
    }
  }

  // read-from-sram
  val stride = state === sWriteAck &
    io.vmeWr.ack &
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
  }.elsewhen(io.vmeWr.data.fire) {
    tag := tag + 1.U
  }

  when(
    state === sWriteCmd || (state =/= sReadMem && set === (tensorLength - 1).U && tag === (numMemBlock - 1).U)
  ) {
    set := 0.U
  }.elsewhen(io.vmeWr.data.fire && tag === (numMemBlock - 1).U) {
    set := set + 1.U
  }

  val raddrCur = Reg(UInt(tp.memAddrBits.W))
  val raddrNxt = Reg(UInt(tp.memAddrBits.W))
  when(state === sIdle) {
    raddrCur := dec.sramOffset
    raddrNxt := dec.sramOffset
  }.elsewhen(
    io.vmeWr.data.fire && set === (tensorLength - 1).U && tag === (numMemBlock - 1).U
  ) {
    raddrCur := raddrCur + 1.U
  }.elsewhen(stride) {
    raddrCur := raddrNxt + dec.xsize
    raddrNxt := raddrNxt + dec.xsize
  }

  val rread = Reg(Vec(tensorLength, Vec(numMemBlock, UInt(memBlockBits.W))))
  when(state === sWriteCmd | state === sReadMem) {
    rread := VecInit(
      tensorFile.map(
        _.read(
          raddrCur
        )
      )
    )
  }
  val tread = Seq.tabulate(tensorLength) { i =>
    i.U ->
      // tensorFile(i).read(raddrCur, state === sWriteCmd | state === sReadMem)
      rread(i)
  }
  val mdata = MuxLookup(set, 0.U.asTypeOf(chiselTypeOf(wdata_t)))(tread)

  // write-to-dram
  when(state === sIdle) {
    waddrCur := xferInitAddr
    waddrNxt := xferInitAddr
  }.elsewhen(state === sWriteAck && io.vmeWr.ack && xrem =/= 0.U) {
    waddrCur := xferSplitAddr
  }.elsewhen(stride) {
    waddrCur := xferStrideAddr
    waddrNxt := xferStrideAddr
  }

  io.vmeWr.cmd.valid := state === sWriteCmd
  io.vmeWr.cmd.bits.addr := waddrCur
  io.vmeWr.cmd.bits.len := xlen
  io.vmeWr.cmd.bits.tag := dec.sramOffset

  io.vmeWr.data.valid := state === sWriteData
  io.vmeWr.data.bits.data := mdata(tag)
  io.vmeWr.data.bits.strb := Fill(io.vmeWr.data.bits.strb.getWidth, true.B)

  when(state === sWriteCmd) {
    xcnt := 0.U
  }.elsewhen(io.vmeWr.data.fire) {
    xcnt := xcnt + 1.U
  }

  // disable external read-from-sram requests
  io.tensor.tieoffRead()

  // done
  io.done := state === sWriteAck & io.vmeWr.ack & xrem === 0.U & ycnt === ysize - 1.U

  // debug
  if (debug) {
    when(io.vmeWr.cmd.fire) {
      printf(
        "[TensorStore] ysize:%x ycnt:%x raddr:%x waddr:%x len:%x rem:%x\n",
        ysize,
        ycnt,
        raddrCur,
        waddrCur,
        xlen,
        xrem
      )
    }
    when(io.vmeWr.data.fire) {
      printf("[TensorStore] data:%x\n", io.vmeWr.data.bits.data)
      printf("[TensorStore] strb:%x\n", io.vmeWr.data.bits.strb)
    }
    when(io.vmeWr.ack) {
      printf("[TensorStore] ack\n")
    }
  }
}
