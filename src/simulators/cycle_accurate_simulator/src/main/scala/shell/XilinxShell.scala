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
import vta.interface.axi._
import vta.util.config._
import chisel3.experimental.dataview.DataViewable
import chisel3.util.experimental.BoringUtils
import chisel3.util.{log2Ceil, Cat}
import vta.core.CoreKey

/** XilinxShell.
  *
  * This is a wrapper shell mostly used to match Xilinx convention naming,
  * therefore we can pack VTA as an IP for IPI based flows.
  */
class XilinxShell(implicit p: Parameters) extends RawModule {

  override def desiredName: String = "VTAXilinxShell"
  val hp = p(ShellKey).hostParams
  val mp = p(ShellKey).memParams

  val ap_clk = IO(Input(Clock()))
  val ap_rst_n = IO(Input(Bool()))
  val m_axi_gmem = IO(new XilinxAXIMaster(mp))
  val s_axi_control = IO(new XilinxAXILiteClient(hp))

  val shell = withClockAndReset(clock = ap_clk, reset = ~ap_rst_n) {
    Module(new VTAShell)
  }

  shell.io.mem <> m_axi_gmem.viewAs[AXIMaster]
  shell.io.host <> s_axi_control.viewAs[AXILiteClient]
}

class XilinxDebugShell(implicit p: Parameters) extends RawModule {

  override def desiredName: String = "VTAXilinxShell"
  val hp = p(ShellKey).hostParams
  val mp = p(ShellKey).memParams

  val ap_clk = IO(Input(Clock()))
  val ap_rst_n = IO(Input(Bool()))
  val m_axi_gmem = IO(new XilinxAXIMaster(mp))
  val s_axi_control = IO(new XilinxAXILiteClient(hp))

  val (shell, debug) = withClockAndReset(clock = ap_clk, reset = ~ap_rst_n) {
    val s = Module(new VTAShell)
    val semaphore0 = RegNext(BoringUtils.bore(s.core.compute.s(0).cnt))
    val semaphore1 = RegNext(BoringUtils.bore(s.core.compute.s(1).cnt))
    val tensorAluSt =
      RegNext(BoringUtils.bore(s.core.compute.tensorAlu.state))
    val tensorAluInf =
      RegNext(BoringUtils.bore(s.core.compute.tensorAlu.inflight))
    val vmeAvailEntries =
      RegNext(BoringUtils.bore(s.vme.availableEntries))
    val computeSt = RegNext(BoringUtils.bore(s.core.compute.state))
    val instQDeqV =
      RegNext(BoringUtils.bore(s.core.compute.inst_q.io.deq.valid))
    val computeIsGemmW =
      RegNext(BoringUtils.bore(s.core.compute.dec.io.isGemm))
    val computeIsAluW =
      RegNext(BoringUtils.bore(s.core.compute.dec.io.isAlu))

    val computeIsLoadUopW =
      RegNext(BoringUtils.bore(s.core.compute.dec.io.isLoadUop))
    val computeIsLoadAccW =
      RegNext(BoringUtils.bore(s.core.compute.dec.io.isLoadAcc))
    val computeIsSyncW =
      RegNext(BoringUtils.bore(s.core.compute.dec.io.isSync))
    val computeIsFinishW =
      RegNext(BoringUtils.bore(s.core.compute.dec.io.isFinish))
    val headBits = BoringUtils.bore(s.core.compute.inst_q.io.deq.bits)
    val headByteW = RegNext(headBits(7, 0))
    val loadUopDoneW = RegNext(BoringUtils.bore(s.core.compute.loadUop.io.done))
    val tensorAccDoneW =
      RegNext(BoringUtils.bore(s.core.compute.tensorAcc.io.done))
    val computeDoneW = RegNext(BoringUtils.bore(s.core.compute.done))
    val instQDeqReadyW =
      RegNext(BoringUtils.bore(s.core.compute.inst_q.io.deq.ready))
    // uop-load wedge probes (P1 vs P2 disambiguation): ysize the loader decodes
    // for the frozen head, plus the loader's commandsDone / clInFlight.
    //   ysize==0                        -> P1 instruction corruption
    //   ysize>0 & commandsDone & clInFlight>0 -> P2 lost VME beat
    val luopYsizeW = RegNext(BoringUtils.bore(s.core.compute.memDec.ysize))
    val luopCommandsDoneW =
      RegNext(
        BoringUtils.bore(s.core.compute.loadUop.loadUopWide.get.commandsDone)
      )
    val luopClInFlightW =
      RegNext(
        BoringUtils.bore(s.core.compute.loadUop.loadUopWide.get.clInFlight)
      )
    val vmeRdCmdValW = RegNext(
      Cat(
        BoringUtils.bore(s.core.compute.io.vme_rd(1).cmd.valid),
        BoringUtils.bore(s.core.compute.io.vme_rd(0).cmd.valid)
      )
    )
    // VCR finish path (post-synth X investigation): the finish signal into the VCR
    // (Core's RegNext(compute.io.finish)) and the ctrl register it corrupts via
    // when(io.vcr.finish){ctrl:=2}. If vcrFinish reads X, ctrl/rdata go X -> host poll wedges.
    val vcrFinishW = RegNext(BoringUtils.bore(s.vcr.io.vcr.finish))
    val vcrCtrlW = RegNext(BoringUtils.bore(s.vcr.regs.ctrl))
    // Read-path X hunt: raddr (read addr into MuxLookup), the read output itself, and an
    // event-counter reg + its valid (ecnt corruption via when(io.vcr.ecnt(i).valid){...}).
    val vcrRaddrW = RegNext(BoringUtils.bore(s.vcr.raddr))
    val vcrRdataW = RegNext(BoringUtils.bore(s.vcr.io.host.r.bits.data))
    val vcrEcnt0W = RegNext(BoringUtils.bore(s.vcr.regs.ecnt(0)))
    val vcrEcnt0ValW = RegNext(BoringUtils.bore(s.vcr.io.vcr.ecnt(0).valid))
    // loadUop loader Capture-4: did `start` reach the loader (sticky luStartSeen) and is the
    // loader in sBusy (luState)? luStartSeen=0 => start never reached it (FF divergence on the
    // launch net); luStartSeen=1 & luState=sIdle => seen but fell back (localDone/reset glitch).
    val luStartBore = BoringUtils.bore(s.core.compute.loadUop.io.start)
    val luDoneBore = BoringUtils.bore(s.core.compute.loadUop.io.done)
    val luStartSeen = RegInit(false.B)
    when(luStartBore) { luStartSeen := true.B }.elsewhen(luDoneBore) {
      luStartSeen := false.B
    }
    val luStateW =
      RegNext(BoringUtils.bore(s.core.compute.loadUop.loadUopWide.get.state))

    val debug = IO(new Bundle {
      val vcrFinish = Output(Bool())
      val vcrCtrl = Output(UInt(32.W))
      val vcrRaddr = Output(UInt(16.W))
      val vcrRdata = Output(UInt(32.W))
      val vcrEcnt0 = Output(UInt(32.W))
      val vcrEcnt0Val = Output(Bool())
      val luStartSeen = Output(Bool())
      val luState = Output(UInt(1.W))
      val sem0 = Output(UInt((log2Ceil(p(CoreKey).instQueueEntries) + 1).W))
      val sem1 = Output(UInt((log2Ceil(p(CoreKey).instQueueEntries) + 1).W))
      val tensorAluState = Output(UInt(2.W))
      val tensorAluInf = Output(UInt(4.W))
      val vmeAvailEntries = Output(UInt(16.W))
      val computeState = Output(UInt(2.W))
      val instQDeqValid = Output(Bool())
      val computeIsGemm = Output(Bool())
      val computeIsAlu = Output(Bool())
      val computeIsLoadUop = Output(Bool())
      val computeIsLoadAcc = Output(Bool())
      val computeIsSync = Output(Bool())
      val computeIsFinish = Output(Bool())
      val headByte = Output(UInt(8.W))
      val loadUopDone = Output(Bool())
      val tensorAccDone = Output(Bool())
      val computeDone = Output(Bool())
      val instQDeqReady = Output(Bool())
      val luopYsize = Output(UInt(16.W)) // M_SIZE_BITS
      val luopCommandsDone = Output(Bool())
      val luopClInFlight =
        Output(UInt(16.W)) // >= clCntIdxWdth for any uop depth
      val vmeRdCmdValid = Output(UInt(2.W))
    })
    debug.sem0 := semaphore0
    debug.sem1 := semaphore1
    debug.tensorAluInf := tensorAluInf
    debug.tensorAluState := tensorAluSt
    debug.vmeAvailEntries := vmeAvailEntries
    debug.computeState := computeSt
    debug.instQDeqValid := instQDeqV
    debug.computeIsGemm := computeIsGemmW
    debug.computeIsAlu := computeIsAluW
    debug.computeIsLoadUop := computeIsLoadUopW
    debug.computeIsLoadAcc := computeIsLoadAccW
    debug.computeIsSync := computeIsSyncW
    debug.computeIsFinish := computeIsFinishW
    debug.headByte := headByteW
    debug.loadUopDone := loadUopDoneW
    debug.tensorAccDone := tensorAccDoneW
    debug.computeDone := computeDoneW
    debug.instQDeqReady := instQDeqReadyW
    debug.luopYsize := luopYsizeW
    debug.luopCommandsDone := luopCommandsDoneW
    debug.luopClInFlight := luopClInFlightW
    debug.vmeRdCmdValid := vmeRdCmdValW
    debug.vcrFinish := vcrFinishW
    debug.vcrCtrl := vcrCtrlW
    debug.vcrRaddr := vcrRaddrW
    debug.vcrRdata := vcrRdataW
    debug.vcrEcnt0 := vcrEcnt0W
    debug.vcrEcnt0Val := vcrEcnt0ValW
    debug.luStartSeen := luStartSeen
    debug.luState := luStateW
    (s, debug)
  }

  shell.io.mem <> m_axi_gmem.viewAs[AXIMaster]
  shell.io.host <> s_axi_control.viewAs[AXILiteClient]
}
