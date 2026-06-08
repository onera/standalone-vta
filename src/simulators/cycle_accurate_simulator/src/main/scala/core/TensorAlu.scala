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
import vta.util.UserDefined.DebugLayer
import chisel3.layer.block

/** ALU datapath */
class Alu(implicit p: Parameters) extends Module {
  val aluBits = p(CoreKey).accBits
  val io = IO(new Bundle {
    val opcode = Input(UInt(C_ALU_OP_BITS.W))
    val a = Input(SInt(aluBits.W))
    val b = Input(SInt(aluBits.W))
    val y = Output(SInt(aluBits.W))
  })

  // FIXME: the following three will change once we support properly SHR and SHL
  val ub = io.b.asUInt
  val width = log2Ceil(aluBits)
  val m = ~ub(width - 1, 0) + 1.U

  val n = ub(width - 1, 0)
  // opcode - min:0, max:1, add:2, shr:3, shl:4
  val fop = Seq(
    Mux(io.a < io.b, io.a, io.b),
    Mux(io.a < io.b, io.b, io.a),
    io.a + io.b,
    io.a >> n,
    io.a << m
  )

  val opmux = Seq.tabulate(ALU_OP_NUM)(i => ALU_OP(i) -> fop(i))
  io.y := MuxLookup(io.opcode, io.a)(opmux)
}

/** Pipelined ALU */
class AluReg(implicit p: Parameters) extends Module {
  val io = IO(new Bundle {
    val opcode = Input(UInt(C_ALU_OP_BITS.W))
    val a = Flipped(ValidIO(UInt(p(CoreKey).accBits.W)))
    val b = Flipped(ValidIO(UInt(p(CoreKey).accBits.W)))
    val y = ValidIO(UInt(p(CoreKey).accBits.W))
  })
  val alu = Module(new Alu)
  val rA = RegEnable(io.a.bits, io.a.valid)
  val rB = RegEnable(io.b.bits, io.b.valid)
  val valid = RegNext(io.b.valid, init = false.B)

  alu.io.opcode := io.opcode

  // register input
  alu.io.a := rA.asSInt
  alu.io.b := rB.asSInt

  // output
  io.y.valid := valid
  io.y.bits := alu.io.y.asUInt
}

/** Vector of pipeline ALUs */
class AluVector(implicit p: Parameters) extends Module {
  val io = IO(new Bundle {
    val opcode = Input(UInt(C_ALU_OP_BITS.W))
    val acc_a = new TensorMasterData(tensorType = "acc")
    val acc_b = new TensorMasterData(tensorType = "acc")
    val acc_y = new TensorClientData(tensorType = "acc")
    val out = new TensorClientData(tensorType = "out")
  })
  val blockOut = p(CoreKey).blockOut
  val f = Seq.fill(blockOut)(Module(new AluReg))
  val valid = Wire(Vec(blockOut, Bool()))
  for (i <- 0 until blockOut) {
    f(i).io.opcode := io.opcode
    f(i).io.a.valid := io.acc_a.data.valid
    f(i).io.a.bits := io.acc_a.data.bits(0)(i)
    f(i).io.b.valid := io.acc_b.data.valid
    f(i).io.b.bits := io.acc_b.data.bits(0)(i)
    valid(i) := f(i).io.y.valid
    io.acc_y.data.bits(0)(i) := f(i).io.y.bits
    io.out.data.bits(0)(i) := f(i).io.y.bits
  }
  io.acc_y.data.valid := valid.asUInt.andR
  io.out.data.valid := valid.asUInt.andR
}

class TensorAluIndexGenerator(debug: Boolean = false)(implicit p: Parameters)
    extends Module {
  val cnt_o_width = (new AluDecode).lp_0.getWidth
  val cnt_i_width = (new AluDecode).lp_1.getWidth

  val io = IO(new Bundle {
    val start = Input(Bool())
    val flush = Input(Bool())
    val last = Output(Bool())
    val dec = Input(new AluDecode)
    val valid = Output(Bool())
    val src_valid = Output(Bool())
    val dst_idx =
      Output(UInt(new TensorParams(tensorType = "acc").memAddrBits.W))
    val src_idx =
      Output(UInt(new TensorParams(tensorType = "acc").memAddrBits.W))
    val uop_idx = Output(UInt(log2Ceil(p(CoreKey).uopMemDepth).W))
    val cnt_o = Output(UInt(cnt_o_width.W))
    val cnt_i = Output(UInt(cnt_i_width.W))
  })

  val accW = new TensorParams(tensorType = "acc").memAddrBits

  // ALU-specific pacing: advance only on the compute cycle. The stutter reg
  // alternates source-read / compute when not using an immediate. The triple
  // nested loop itself lives in the shared NestedLoopCounter.
  val stutter = RegInit(false.B)
  val advance = io.dec.alu_use_imm || stutter

  val counter = Module(
    new NestedLoopCounter(
      idxWidths = Seq(accW, accW),
      strideWidths = Seq(io.dec.dst_0.getWidth, io.dec.src_0.getWidth),
      loopBits0 = io.dec.lp_0.getWidth,
      loopBits1 = io.dec.lp_1.getWidth,
      uopBits = io.dec.uop_end.getWidth
    )
  )
  counter.io.start := io.start
  counter.io.flush := io.flush
  counter.io.advance := advance
  counter.io.lp_0 := io.dec.lp_0
  counter.io.lp_1 := io.dec.lp_1
  counter.io.uop_begin := io.dec.uop_begin
  counter.io.uop_end := io.dec.uop_end
  counter.io.stride_0(0) := io.dec.dst_0
  counter.io.stride_0(1) := io.dec.src_0
  counter.io.stride_1(0) := io.dec.dst_1
  counter.io.stride_1(1) := io.dec.src_1

  val running = counter.io.running
  when(io.flush) {
    stutter := false.B
  }.elsewhen(running && !advance) {
    stutter := true.B
  }.elsewhen(running && advance) {
    stutter := false.B
  }

  io.valid := running && advance
  io.src_valid := running && !advance
  io.dst_idx := counter.io.idx(0)
  io.src_idx := counter.io.idx(1)
  io.uop_idx := counter.io.uop_idx
  io.cnt_o := counter.io.cnt_o
  io.cnt_i := counter.io.cnt_i
  io.last := counter.io.last
}

class TensorAluIfc(implicit p: Parameters) extends Module {
  val aluBits = p(CoreKey).accBits
  val io = IO(new Bundle {
    val start = Input(Bool())
    // flush: Compute asserts this whenever the ALU must not be running (i.e.
    // any cycle that is not "Compute in sExe executing an ALU instruction").
    // It force-resets the FSM / index generator / inflight to clean idle so a
    // stale decode or residual count cannot survive into the next layer and
    // live-lock the index generator. See Compute.scala.
    val flush = Input(Bool())
    val done = Output(Bool())
    val dec = Input(new AluDecode)
    val uop = new UopMaster
    val acc = new TensorMaster(tensorType = "acc")
    val out = new TensorMaster(tensorType = "out")
  })
}

class TensorAluPipelined(implicit p: Parameters) extends TensorAluIfc {
  val inflightBits = 4
  val dataSplitFactor = p(CoreKey).blockOutFactor

  val sIdle :: sRun :: sWait :: Nil = Enum(3)
  val state = RegInit(init = sIdle)
  val inflight = RegInit(0.U(inflightBits.W))

  val indexGenerator = Module(new TensorAluIndexGenerator)
  val aluDataReadPipeDelay = 0 // available for pipelining

  // Latch the decode at start and drive the run from it (mirrors
  // TensorGemmPipelinedSplit.capture_dec). decStable == io.dec during a
  // well-formed run, so values/timing are unchanged; it only diverges if the
  // queue head changes mid-run, in which case the latched decode keeps the
  // index generator iterating toward a reachable terminal instead of garbage.
  val capture_dec = Reg(chiselTypeOf(io.dec))
  when(state === sIdle && io.start) {
    capture_dec := io.dec
  }
  val decStable = Mux(io.start, io.dec, capture_dec)

  assert(
    !io.start || io.dec.empty_0 === 0.U,
    "[TensorAlu] reserved field nonzero - malformed instruction"
  )

  // State Machine for compute io.done correctly.
  // flush takes priority: force clean idle without pulsing done.
  io.done := false.B
  when(io.flush) {
    state := sIdle
  }.elsewhen(state === sIdle && io.start) {
    state := sRun
  }.elsewhen(state === sRun && indexGenerator.io.last) {
    state := sWait
  }.elsewhen(state === sWait && inflight === 0.U) {
    state := sIdle
    io.done := true.B
  }

  indexGenerator.io.start := io.start
  indexGenerator.io.flush := io.flush
  indexGenerator.io.dec := decStable

  // second term works around funny clearing in uop register file flopped output
  io.uop.idx.valid := indexGenerator.io.valid || indexGenerator.io.src_valid
  io.uop.idx.bits := indexGenerator.io.uop_idx

  val valid_r1 = ShiftRegister(
    indexGenerator.io.valid,
    aluDataReadPipeDelay + 1,
    false.B,
    true.B
  )
  val validR2 = RegNext(valid_r1, init = false.B)
  val validR3 = RegNext(validR2, init = false.B)
  val validR4 = RegNext(validR3, init = false.B)

  when(io.flush) {
    inflight := 0.U
  }.elsewhen(indexGenerator.io.valid && validR4) {}
    .elsewhen(indexGenerator.io.valid) {
      assert(
        inflight =/= ((1 << inflightBits) - 1).U,
        "[TensorAlu] index generator incorrect"
      )
      inflight := inflight + 1.U
    }
    .elsewhen(validR4) {
      assert(inflight =/= 0.U, "[TensorAlu] inflight is zero")
      inflight := inflight - 1.U
    }
  when(state === sIdle && !io.flush) {
    assert(inflight === 0.U, "[TensorAlu] is not zero")
    inflight := 0.U
  }

  val srcValidR1 = ShiftRegister(
    indexGenerator.io.src_valid,
    aluDataReadPipeDelay + 1,
    false.B,
    true.B
  )
  val srcValidR2 = RegNext(srcValidR1, init = false.B)
  val srcValidR3 = RegNext(srcValidR2, init = false.B)
  val srcValidR4 = RegNext(srcValidR3, init = false.B)

  val dst_idx_r1 =
    ShiftRegister(indexGenerator.io.dst_idx, aluDataReadPipeDelay + 1)
  val src_idx_r1 =
    ShiftRegister(indexGenerator.io.src_idx, aluDataReadPipeDelay + 1)

  val uop_data_r1 = ShiftRegister(io.uop.data, aluDataReadPipeDelay)

  val dst_offset = uop_data_r1.bits.u0

  val w = dst_offset.getWidth
  val u2 = uop_data_r1.bits.u2.asTypeOf(UInt(w.W))
  val s = log2Ceil(p(CoreKey).inpMemDepth)
  val u1 = uop_data_r1.bits.u1.asTypeOf(UInt(w.W))
  val src_offset = (u2 << s) | u1

  // split registers of stage 2 by data groups
  val accRdIdxValid = valid_r1 || srcValidR1
  for (idx <- 0 until dataSplitFactor) {
    // init = false.B: this register drives the output idx.valid that downstream
    // memory mocks sample, including before the first clock step. Without an
    // init a random reset value can assert idx.valid out of reset and trip the
    // read-index data-valid assertion below. The other valid pipeline regs
    // (validR2/3/4, srcValidR2/3/4) carry init = false.B for the same reason.
    io.acc.rd(idx).idx.valid := RegNext(accRdIdxValid, init = false.B)
  }

  val new_src_idx_r1 = src_idx_r1 + src_offset
  val src_idx_r2 = RegNext(new_src_idx_r1)
  val src_idx_r3 = RegNext(src_idx_r2)

  val new_dst_idx_r1 = dst_idx_r1 + dst_offset
  val dst_idx_r2 = RegNext(new_dst_idx_r1)
  val dst_idx_r3 = RegNext(dst_idx_r2)
  val dst_idx_r4 = RegNext(dst_idx_r3)

  // split registers of stage 2 by data groups
  val accRdIdxBits =
    Mux(srcValidR1 || decStable.alu_use_imm, new_src_idx_r1, new_dst_idx_r1)
  for (idx <- 0 until dataSplitFactor) {
    io.acc.rd(idx).idx.bits := RegNext(accRdIdxBits)
    assert(
      io.acc.rd(idx).data.valid === (validR3 || srcValidR3),
      "[TensorAlu] read index data valid incorrect"
    )
  }

  require(
    io.out.splitWidth == 1 && io.out.splitLength == 1,
    "-F- Out split write is not supported"
  )
  val numVecUnits = dataSplitFactor
  val outData = Wire(chiselTypeOf(io.out.wr(0).bits.data))
  val dataRemapB = Wire(Vec(numVecUnits, chiselTypeOf(io.acc.rd(0).data.bits)))
  val dataRemapA = Wire(Vec(numVecUnits, chiselTypeOf(io.acc.rd(0).data.bits)))

  // RAW hazard detection: when the stage-3 read and the stage-4 write fire on
  // the same cycle, the SyncReadMem read returns memory contents from before
  // that cycle's write commits. If read and write target the same accumulator
  // index the read is stale; the up-to-date value is alu.io.acc_y.data.bits on
  // that cycle.
  //
  // bypass_src: the index generator's stutter/advance pattern makes srcValidR3
  // overlap with validR4 on the same cycle, so a same-cycle compare suffices.
  //
  // bypass_dst: for non-imm uops validR3 lands one cycle after validR4 (each
  // advance is preceded by a stutter), so two terms are needed. bypass_dst_now
  // catches the imm-mode same-cycle collision; bypass_dst_prev catches the
  // one-cycle-delayed stutter case. Without _prev, consecutive same-dst
  // (MaxPool-shaped) reductions drop the older uop's contribution.
  val validR4_d1 = RegNext(validR4, init = false.B)
  val dst_idx_r4_d1 = RegNext(dst_idx_r4)
  val bypass_dst_now = validR3 && validR4 && (dst_idx_r4 === dst_idx_r3)
  val bypass_dst_prev = validR3 && validR4_d1 && (dst_idx_r4_d1 === dst_idx_r3)
  val bypass_dst = bypass_dst_now || bypass_dst_prev
  val bypass_src = srcValidR3 && validR4 && (dst_idx_r4 === src_idx_r3)
  // numVecUnits is a pow of 2
  // split dec bits pipe further if there are many vecUnits
  val decSplitNb0 = if (numVecUnits < 8) 1 else 2
  val decSplit0 = Wire(Vec(decSplitNb0, chiselTypeOf(io.dec)))
  for (idx <- 0 until decSplitNb0) {
    decSplit0(idx) := ShiftRegister(
      decStable,
      if (aluDataReadPipeDelay < 2) 0 else 1
    )
  }

  for (idx <- 0 until numVecUnits) {
    val alu = Module(new AluVector)

    for (aluLenIdx <- 0 until alu.io.acc_b.lenSplit) {
      for (aluWdtIdx <- 0 until alu.io.acc_b.widthSplit) {
        val (accGrpIdx, accLenIdx, accWdtIdx) =
          alu.io.acc_b.reindexDataFromGroup(idx, aluLenIdx, aluWdtIdx)
        dataRemapB(idx)(aluLenIdx)(aluWdtIdx) :=
          io.acc.rd(accGrpIdx).data.bits(accLenIdx)(accWdtIdx)
      }
    }
    // src-read bypass: when bypass_src fires, latch the current ALU write
    // (alu.io.acc_y.data.bits) into save_src instead of the stale memory read.
    val srcBypassed = Mux(bypass_src, alu.io.acc_y.data.bits, dataRemapB(idx))
    val save_src = RegNext(srcBypassed)
    val tensorImm = Wire(new TensorClientData(tensorType = "acc"))
    tensorImm.data.valid := validR3
    val tensorImmBits_piped = ShiftRegister(
      decSplit0(idx / (numVecUnits / decSplitNb0)).alu_imm,
      if (aluDataReadPipeDelay < 2) aluDataReadPipeDelay
      else aluDataReadPipeDelay - 1
    )
    tensorImm.data.bits.foreach { b =>
      b.foreach { c =>
        c := Mux(
          tensorImmBits_piped(C_ALU_IMM_BITS - 1),
          Cat(-1.S((aluBits - C_ALU_IMM_BITS).W), tensorImmBits_piped),
          tensorImmBits_piped
        )
      }
    }

    // alu
    val tensorOpBits_piped = ShiftRegister(
      decSplit0(idx / (numVecUnits / decSplitNb0)).alu_op,
      if (aluDataReadPipeDelay < 2) aluDataReadPipeDelay
      else aluDataReadPipeDelay - 1
    )
    val isSHR = (tensorOpBits_piped === ALU_OP(3))
    val neg_shift = isSHR & tensorImmBits_piped(C_ALU_IMM_BITS - 1)
    val fixme_alu_op = Mux(
      neg_shift,
      ALU_OP(4), // use opcode = 4 for left shift
      tensorOpBits_piped
    )
    alu.io.opcode := fixme_alu_op

    assert(
      !validR3 || io.acc.rd(idx).data.valid,
      "[TensorAlu] condition de con"
    )

    // init = false.B mirrors validR2/3/4: without an init a random reset value
    // could assert this valid out of reset, latching a junk acc_a operand.
    alu.io.acc_a.data.valid := RegNext(validR2, init = false.B)

    for (aluLenIdx <- 0 until alu.io.acc_a.lenSplit) {
      for (aluWdtIdx <- 0 until alu.io.acc_a.widthSplit) {
        val (accGrpIdx, accLenIdx, accWdtIdx) =
          alu.io.acc_a.reindexDataFromGroup(idx, aluLenIdx, aluWdtIdx)
        dataRemapA(idx)(aluLenIdx)(aluWdtIdx) :=
          io.acc.rd(accGrpIdx).data.bits(accLenIdx)(accWdtIdx)
      }
    }
    // dst-read bypass mux:
    //   - bypass_dst_now  -> live alu.io.acc_y.data.bits (imm-mode same-cycle hazard)
    //   - bypass_dst_prev -> acc_y_d1, a one-cycle-delayed snapshot of the just-
    //                        written value (stutter-pattern non-imm hazard)
    //   - else            -> live dataRemapA(idx) (fresh memory read)
    val acc_y_d1 = RegNext(alu.io.acc_y.data.bits)
    alu.io.acc_a.data.bits := Mux(
      bypass_dst_now,
      alu.io.acc_y.data.bits,
      Mux(bypass_dst_prev, acc_y_d1, dataRemapA(idx))
    )
    val tensorUseImmBits_piped = ShiftRegister(
      decSplit0(idx / (numVecUnits / decSplitNb0)).alu_use_imm,
      if (aluDataReadPipeDelay < 2) aluDataReadPipeDelay
      else aluDataReadPipeDelay - 1
    )
    alu.io.acc_b.data.valid := Mux(
      tensorUseImmBits_piped,
      tensorImm.data.valid,
      validR3
    )
    alu.io.acc_b.data.bits := Mux(
      tensorUseImmBits_piped,
      tensorImm.data.bits,
      save_src
    )

    assert(
      alu.io.acc_y.data.valid === validR4,
      "[TensorAlu] acc_y valid not sync with validR4"
    )
    io.acc.wr(idx).valid := validR4
    io.acc.wr(idx).bits.idx := dst_idx_r4

    for (aluLenIdx <- 0 until alu.io.acc_y.lenSplit) {
      for (aluWdtIdx <- 0 until alu.io.acc_y.widthSplit) {
        val (accGrpIdx, accLenIdx, accWdtIdx) =
          alu.io.acc_y.reindexDataFromGroup(idx, aluLenIdx, aluWdtIdx)
        io.acc.wr(accGrpIdx).bits.data(accLenIdx)(accWdtIdx) :=
          alu.io.acc_y.data.bits(aluLenIdx)(aluWdtIdx)
      }
    }

    // assert(alu.io.out.data.valid === valid_r4)
    for (idx1 <- 0 until io.out.tensorLength) {
      for (idx2 <- 0 until io.out.tensorWidth / numVecUnits) {
        outData(idx1)(
          idx * io.out.tensorWidth / numVecUnits + idx2
        ) := alu.io.out.data.bits(idx1)(idx2)
      }
    }
  }

// comment for split write
  io.out.wr(0).valid := validR4
  io.out.wr(0).bits.idx := dst_idx_r4
  io.out.wr(0).bits.data := outData
  io.out.tieoffRead()

}

/** TensorAluOrig. This unit instantiate the ALU vector unit (AluVector) and go
  * over the micro-ops (uops) which are used to read the source operands
  * (vectors) from the acc-scratchpad and then they are written back the same
  * acc-scratchpad.
  */
class TensorAluOrig(debug: Boolean = false)(implicit p: Parameters)
    extends TensorAluIfc {
  val sIdle :: sReadUop :: sComputeIdx :: sReadTensorA :: sReadTensorB :: sExe :: Nil =
    Enum(6)
  val state = RegInit(sIdle)
  val alu = Module(new AluVector)
  val dec = io.dec
  val uop_idx = Reg(chiselTypeOf(dec.uop_end))
  val uop_end = dec.uop_end
  val uop_dst = Reg(
    chiselTypeOf(io.uop.data.bits.u0)
  ) // width can address entire acc
  val uop_src = Reg(
    chiselTypeOf(io.uop.data.bits.u0)
  ) // width can address entire acc
  val cnt_o = Reg(chiselTypeOf(dec.lp_0))
  val dst_o = Reg(chiselTypeOf(io.uop.data.bits.u0))
  val src_o = Reg(chiselTypeOf(io.uop.data.bits.u0))
  val cnt_i = Reg(chiselTypeOf(dec.lp_1))
  val dst_i = Reg(chiselTypeOf(io.uop.data.bits.u0))
  val src_i = Reg(chiselTypeOf(io.uop.data.bits.u0))
  val done =
    state === sExe &
      alu.io.out.data.valid &
      (cnt_o === dec.lp_0 - 1.U) &
      (cnt_i === dec.lp_1 - 1.U) &
      (uop_idx === uop_end - 1.U)

  switch(state) {
    is(sIdle) {
      when(io.start) {
        state := sReadUop
      }
    }
    is(sReadUop) {
      state := sComputeIdx
    }
    is(sComputeIdx) {
      state := sReadTensorA
    }
    is(sReadTensorA) {
      state := sReadTensorB
    }
    is(sReadTensorB) {
      state := sExe
    }
    is(sExe) {
      when(alu.io.out.data.valid) {
        when(
          (cnt_o === dec.lp_0 - 1.U) &&
            (cnt_i === dec.lp_1 - 1.U) &&
            (uop_idx === uop_end - 1.U)
        ) {
          state := sIdle
        }.otherwise {
          state := sReadUop
        }
      }
    }
  }

  when(
    state === sIdle ||
      (state === sExe &&
        alu.io.out.data.valid &&
        uop_idx === uop_end - 1.U)
  ) {
    uop_idx := dec.uop_begin
  }.elsewhen(state === sExe && alu.io.out.data.valid) {
    uop_idx := uop_idx + 1.U
  }

  when(state === sIdle) {
    cnt_o := 0.U
    dst_o := 0.U
    src_o := 0.U
  }.elsewhen(
    state === sExe &&
      alu.io.out.data.valid &&
      uop_idx === uop_end - 1.U &&
      cnt_i === dec.lp_1 - 1.U
  ) {
    cnt_o := cnt_o + 1.U
    dst_o := dst_o + dec.dst_0
    src_o := src_o + dec.src_0
  }

  when(state === sIdle) {
    cnt_i := 0.U
    dst_i := 0.U
    src_i := 0.U
  }.elsewhen(state === sReadUop && cnt_i === dec.lp_1) {
    cnt_i := 0.U
    dst_i := dst_o
    src_i := src_o
  }.elsewhen(
    state === sExe && alu.io.out.data.valid && uop_idx === uop_end - 1.U
  ) {
    cnt_i := cnt_i + 1.U
    dst_i := dst_i + dec.dst_1
    src_i := src_i + dec.src_1
  }

  when(state === sComputeIdx && io.uop.data.valid) {
    uop_dst := io.uop.data.bits.u0 + dst_i
    uop_src := ((io.uop.data.bits.u2.asTypeOf(
      UInt(width = uop_dst.getWidth.W)
    ) << log2Ceil(p(CoreKey).inpMemDepth))
      | io.uop.data.bits.u1.asTypeOf(UInt(width = uop_dst.getWidth.W))) + src_i
  }

  // uop
  io.uop.idx.valid := state === sReadUop
  io.uop.idx.bits := uop_idx

  val dataSplitFactor = p(CoreKey).blockOutFactor

  val accRdValid =
    state === sReadTensorA | (state === sReadTensorB & ~dec.alu_use_imm)
  val accRdIdx = Mux(state === sReadTensorA, uop_dst, uop_src)
  for (idx <- 0 until dataSplitFactor) {
    // acc (input)
    io.acc.rd(idx).idx.valid := accRdValid
    io.acc.rd(idx).idx.bits := accRdIdx

    // imm
    val tensorImm = Wire(new TensorClientData(tensorType = "acc"))
    tensorImm.data.valid := state === sReadTensorB
    tensorImm.data.bits.foreach { b =>
      b.foreach { c =>
        c := Mux(
          dec.alu_imm(C_ALU_IMM_BITS - 1),
          Cat(-1.S((aluBits - C_ALU_IMM_BITS).W), dec.alu_imm),
          dec.alu_imm
        )
      }
    }

    // alu
    val isSHR = (dec.alu_op === ALU_OP(3))
    val isSHL = isSHR & dec.alu_imm(C_ALU_IMM_BITS - 1)
    // opcode - min:0, max:1, add:2, shr:3, shl:4
    val fixme_alu_op = Cat(isSHL, Mux(isSHL, 0.U, dec.alu_op(1, 0)))
    alu.io.opcode := fixme_alu_op
    alu.io.acc_a.data.valid := io.acc
      .rd(idx)
      .data
      .valid & state === sReadTensorB
    alu.io.acc_a.data.bits <> io.acc.rd(idx).data.bits
    alu.io.acc_b.data.valid := Mux(
      dec.alu_use_imm,
      tensorImm.data.valid,
      io.acc.rd(idx).data.valid & state === sExe
    )
    alu.io.acc_b.data.bits <> Mux(
      dec.alu_use_imm,
      tensorImm.data.bits,
      io.acc.rd(idx).data.bits
    )

    // acc (output)
    io.acc.wr(idx).valid := alu.io.acc_y.data.valid
    io.acc.wr(idx).bits.idx := uop_dst
    io.acc.wr(idx).bits.data <> alu.io.acc_y.data.bits

    // out
    io.out.wr(idx).valid := alu.io.out.data.valid
    io.out.wr(idx).bits.idx := uop_dst
    io.out.wr(idx).bits.data <> alu.io.out.data.bits
  }
  io.out.tieoffRead() // write-only
  io.done := done

  block(DebugLayer) {
    when(state === sReadUop) {
      printf("[TensorAlu] [uop] idx:%x\n", uop_idx)
    }

    when(state === sReadTensorA) {
      printf("[TensorAlu] [uop] dst:%x src:%x\n", uop_dst, uop_src)
    }

    when(state === sIdle && io.start) {
      printf(p"[TensorAlu] decode:$dec\n")
    }

    alu.io.acc_a.data.bits.foreach { tensor =>
      tensor.zipWithIndex.foreach { case (elem, i) =>
        when(alu.io.acc_a.data.valid) {
          printf("[TensorAlu] [a] i:%x val:%x\n", i.U, elem)
        }
      }
    }

    alu.io.acc_b.data.bits.foreach { tensor =>
      tensor.zipWithIndex.foreach { case (elem, i) =>
        when(alu.io.acc_b.data.valid) {
          printf("[TensorAlu] [b] i:%x val:%x\n", i.U, elem)
        }
      }
    }

    alu.io.acc_y.data.bits.foreach { tensor =>
      tensor.zipWithIndex.foreach { case (elem, i) =>
        when(alu.io.acc_y.data.valid) {
          printf("[TensorAlu] [y] i:%x val:%x\n", i.U, elem)
        }
      }
    }

    alu.io.out.data.bits.foreach { tensor =>
      tensor.zipWithIndex.foreach { case (elem, i) =>
        when(alu.io.out.data.valid) {
          printf("[TensorAlu] [out] i:%x val:%x\n", i.U, elem)
        }
      }
    }
  }
}

class TensorAlu(debug: Boolean = false)(implicit p: Parameters)
    extends TensorAluPipelined
