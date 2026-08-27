package vta.test

import chisel3._
import chisel3.simulator.stimulus.RunUntilFinished
import chisel3.simulator.{
  ChiselOptionsModifications,
  ChiselSim,
  FirtoolOptionsModifications,
  HasSimulator
}
import chisel3.testing.HasTestingDirectory
import chisel3.util.experimental.BoringUtils
import vta.configs.DefaultPynqConfig
import vta.interface.axi.AXILiteClient
import vta.models.MemoryConfig
import vta.shell.{ShellKey, VTAShell}
import vta.util.config.Parameters

class VTAShellTestFull(
  content: Seq[MemoryConfig],
  enforceOutBounds: Boolean = true
)(implicit param: Parameters)
    extends Module {
  val io = IO(new Bundle {
    val host = new AXILiteClient(param(ShellKey).hostParams)
    val finish = Output(Bool())
    // Debug-probe bundle mirroring XilinxDebugShell, available to ScalaTest
    // peeks. Tests that don't care can ignore these IOs - they're only read,
    // never poked. See shell/XilinxShell.scala:53-92 for the synthesized
    // counterpart on the FPGA debug bitstream.
    val dbg = new Bundle {
      val sem0 = Output(UInt(16.W))
      val sem1 = Output(UInt(16.W))
      val tensorAluState = Output(UInt(2.W))
      val tensorAluInf = Output(UInt(4.W))
      val tensorGemmState = Output(UInt(4.W))
      val tensorGemmInf = Output(UInt(4.W))
      val computeState = Output(UInt(2.W))
      val vmeAvailEntries = Output(UInt(16.W))
      val instQDeqValid = Output(Bool())
      val computeIsGemm = Output(Bool())
      val computeIsAlu = Output(Bool())
      // Launch-path probes: ctrl(0) and the Fetch-side state. If `vcrLaunch`
      // is stuck high across layers, Fetch's rising-edge detector
      // (FetchWideVME.scala:60 `start = io.launch & ~s1_launch`) never fires.
      // If `fetchInstCoValid` stays 0 throughout the hang, Fetch is dispatching
      // nothing to Compute - the bug is upstream of Compute.
      val vcrLaunch = Output(Bool())
      val fetchInstCoValid = Output(Bool())
      val fetchInstCoReady = Output(Bool())
      val vcrInsCount = Output(UInt(16.W))
      // True for one cycle when Compute's FNSH instr fires (state === sExe &
      // done & isFinish). If this never pulses across the whole layer we know
      // FNSH was never processed.
      val computeFinish = Output(Bool())
      // Lowest 8 bits of inst_q.deq.bits - just the opcode+dep field, enough
      // to distinguish what instruction Compute is currently looking at.
      val computeInstHead = Output(UInt(8.W))
      val computeIsSync = Output(Bool())
      val computeIsFinish = Output(Bool())
      val computeStart = Output(Bool())
    }
  })
  val vta = Module(new VTAShell)

  val dramMock = Module(
    new MultiMemAxiClient(content, enforceOutBounds)(param(ShellKey).memParams)
  )
  io.finish := dontTouch(RegNext(BoringUtils.tapAndRead(vta.vcr.io.vcr.finish)))

  // Debug probes - same wiring as XilinxDebugShell. All tapped via BoringUtils
  // so they don't depend on adding IO to the VTA core itself.
  io.dbg.sem0 := RegNext(BoringUtils.tapAndRead(vta.core.compute.s(0).cnt))
  io.dbg.sem1 := RegNext(BoringUtils.tapAndRead(vta.core.compute.s(1).cnt))
  io.dbg.tensorAluState :=
    RegNext(BoringUtils.tapAndRead(vta.core.compute.tensorAlu.state))
  io.dbg.tensorAluInf :=
    RegNext(BoringUtils.tapAndRead(vta.core.compute.tensorAlu.inflight))
  io.dbg.tensorGemmState :=
    RegNext(BoringUtils.tapAndRead(vta.core.compute.tensorGemm.state))
  io.dbg.tensorGemmInf :=
    RegNext(BoringUtils.tapAndRead(vta.core.compute.tensorGemm.inflight))
  io.dbg.computeState :=
    RegNext(BoringUtils.tapAndRead(vta.core.compute.state))
  io.dbg.instQDeqValid :=
    RegNext(BoringUtils.tapAndRead(vta.core.compute.inst_q.io.deq.valid))
  io.dbg.computeIsGemm :=
    RegNext(BoringUtils.tapAndRead(vta.core.compute.dec.io.isGemm))
  io.dbg.computeIsAlu :=
    RegNext(BoringUtils.tapAndRead(vta.core.compute.dec.io.isAlu))
  // No RegNext on these so the snapshot reflects the same cycle the test peeks.
  io.dbg.vcrLaunch := BoringUtils.tapAndRead(vta.vcr.io.vcr.launch)
  io.dbg.fetchInstCoValid :=
    BoringUtils.tapAndRead(vta.core.fetch.io.inst.co.valid)
  io.dbg.fetchInstCoReady :=
    BoringUtils.tapAndRead(vta.core.fetch.io.inst.co.ready)
  io.dbg.vcrInsCount :=
    BoringUtils.tapAndRead(vta.vcr.io.vcr.vals(0))
  io.dbg.computeFinish :=
    BoringUtils.tapAndRead(vta.core.compute.io.finish)
  io.dbg.computeInstHead :=
    BoringUtils.tapAndRead(vta.core.compute.inst_q.io.deq.bits).apply(7, 0)
  io.dbg.computeIsSync :=
    BoringUtils.tapAndRead(vta.core.compute.dec.io.isSync)
  io.dbg.computeIsFinish :=
    BoringUtils.tapAndRead(vta.core.compute.dec.io.isFinish)
  // Recreate Compute's `start` externally: inst_q.deq.valid AND
  // (pop_prev ? s(0).sready : 1) AND (pop_next ? s(1).sready : 1)
  // This mirrors Compute.scala:97-99.
  io.dbg.computeStart := {
    val deqV = BoringUtils.tapAndRead(vta.core.compute.inst_q.io.deq.valid)
    val popp = BoringUtils.tapAndRead(vta.core.compute.dec.io.pop_prev)
    val popn = BoringUtils.tapAndRead(vta.core.compute.dec.io.pop_next)
    val s0rdy = BoringUtils.tapAndRead(vta.core.compute.s(0).io.sready)
    val s1rdy = BoringUtils.tapAndRead(vta.core.compute.s(1).io.sready)
    deqV & Mux(popp, s0rdy, true.B) & Mux(popn, s1rdy, true.B)
  }

  // when(finish) {
  //   stop()
  // }
  vta.io.host <> io.host
  vta.io.mem <> dramMock.io
}

trait VTAShellTest extends ChiselSim with AxiFullSimUtils with VcrTestUtils {

  def runVtaTestWithInitializedMem(
    content: Seq[MemoryConfig],
    timeout: Int = 10000,
    waves: Boolean = false
  )(implicit
    testingDirectory: HasTestingDirectory,
    simulator: HasSimulator,
    chiselOptsModifications: ChiselOptionsModifications,
    firtoolOptsModifications: FirtoolOptionsModifications,
    commonSettingsModifications: svsim.CommonSettingsModifications,
    backendSettingsModifications: svsim.BackendSettingsModifications,
    parameters: Parameters = new DefaultPynqConfig
  ) = {
    // Settings modifications (mem-init, FST tracing, ...) are forwarded from
    // the call site rather than fixed here, so each caller controls them.
    simulate(
      new VTAShellTestFull(content, false),
      firtoolOpts = Array("--disable-mem-randomization")
    ) { vta =>
      implicit val clock = vta.clock
      implicit val axiLiteClient = vta.io.host
      vta.io.host.b.ready.poke(true.B)

      if (waves) {
        enableWaves()
      }

      writeInstructionBaseAddress(
        content.find(_.name.startsWith("INSN")).get.baseAddress
      )
      writeUopBaseAddress(0)
      writeInputBaseAddress(0)
      writeWeightBaseAddress(0)
      writeAccBaseAddress(0)
      writeOutBaseAddress(0)
      // Configure instruction size

      writeInstructionCount(
        content.find(_.name.startsWith("INSN")).get.numberOfData
      )

      // launch the processing of VTA
      launchVTA()

      // step clock until the computation is over
      clock.step(timeout)
      RunUntilFinished(timeout)
    }
  }

}
