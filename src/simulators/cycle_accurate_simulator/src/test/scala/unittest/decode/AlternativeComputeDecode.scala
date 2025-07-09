package unittest.decode

import chisel3._
import vta.core._
import chisel3.util._


class AlternativeComputeMemDecode extends Module {
  val io = IO(new Bundle {
    val inst = Input(UInt(INST_BITS.W))
    val op = Output(UInt(OP_BITS.W))
    val pop_prev = Output(Bool())
    val pop_next = Output(Bool())
    val push_prev = Output(Bool())
    val push_next = Output(Bool())
    val id = Output(UInt(M_ID_BITS.W))
    val sram_offset = Output(UInt(M_SRAM_OFFSET_BITS.W))
    val dram_offset = Output(UInt(M_DRAM_OFFSET_BITS.W))
    val empty_0 = Output(UInt(6.W))
    val ysize = Output(UInt(M_SIZE_BITS.W))
    val xsize = Output(UInt(M_SIZE_BITS.W))
    val xstride = Output(UInt(M_STRIDE_BITS.W))
    val ypad_0 = Output(UInt(M_PAD_BITS.W))
    val ypad_1 = Output(UInt(M_PAD_BITS.W))
    val xpad_0 = Output(UInt(M_PAD_BITS.W))
    val xpad_1 = Output(UInt(M_PAD_BITS.W))
  })
  val dec = io.inst.asTypeOf(new MemDecode)
  io.op := dec.op
  io.pop_prev := dec.pop_prev
  io.pop_next := dec.pop_next
  io.push_prev := dec.push_prev
  io.push_next := dec.push_next
  io.id := dec.id
  io.sram_offset := dec.sram_offset
  io.dram_offset := dec.dram_offset
  io.empty_0 := dec.empty_0
  io.ysize := dec.ysize
  io.xsize := dec.xsize
  io.xstride := dec.xstride
  io.ypad_0 := dec.ypad_0
  io.ypad_1 := dec.ypad_1
  io.xpad_0 := dec.xpad_0
  io.xpad_1 := dec.xpad_1
}


class AlternativeComputeGemmDecode extends Module {
  val io = IO(new Bundle {
    val inst = Input(UInt(INST_BITS.W))
    val op = Output(UInt(OP_BITS.W))
    val pop_prev = Output(Bool())
    val pop_next = Output(Bool())
    val push_prev = Output(Bool())
    val push_next = Output(Bool())
    val reset = Output(Bool())
    val uop_begin = Output(UInt(C_UOP_BGN_BITS.W))
    val uop_end = Output(UInt(C_UOP_END_BITS.W))
    val lp_0 = Output(UInt(C_ITER_BITS.W))
    val lp_1 = Output(UInt(C_ITER_BITS.W))
    val empty_0 = Output(Bool())
    val acc_0 = Output(UInt(C_AIDX_BITS.W))
    val acc_1 = Output(UInt(C_AIDX_BITS.W))
    val inp_0 = Output(UInt(C_IIDX_BITS.W))
    val inp_1 = Output(UInt(C_IIDX_BITS.W))
    val wgt_0 = Output(UInt(C_WIDX_BITS.W))
    val wgt_1 = Output(UInt(C_WIDX_BITS.W))
  })
  val dec = io.inst.asTypeOf(new GemmDecode)
  io.op := dec.op
  io.pop_prev := dec.pop_prev
  io.pop_next := dec.pop_next
  io.push_prev := dec.push_prev
  io.push_next := dec.push_next
  io.reset := dec.reset
  io.uop_begin := dec.uop_begin
  io.uop_end := dec.uop_end
  io.lp_0 := dec.lp_0
  io.lp_1 := dec.lp_1
  io.empty_0 := dec.empty_0
  io.acc_0 := dec.acc_0
  io.acc_1 := dec.acc_1
  io.inp_0 := dec.inp_0
  io.inp_1 := dec.inp_1
  io.wgt_0 := dec.wgt_0
  io.wgt_1 := dec.wgt_1
}