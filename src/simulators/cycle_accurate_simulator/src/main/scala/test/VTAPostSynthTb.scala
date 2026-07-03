package vta.test

import chisel3._
import chisel3.experimental.dataview.DataViewable
import vta.shell.{ShellKey, XilinxDebugShell}
import vta.interface.axi._
import TestBenchLayout.LaunchParams
import vta.models.MemoryConfig
import vta.util.config.Parameters

/** Self-driving multi-layer testbench for post-synthesis simulation of the
  * BOARD's actual top module: VTAXilinxShell (instantiated via XilinxDebugShell
  * so the board probe set is available as ports). This matches the FPGA IP flow
  * (DefaultXilinxConfig / build_fpga.tcl): active-low ap_rst_n + Xilinx AXI
  * interface shims, rather than the bare sim VTAShell. Vivado substitutes the
  * post-synthesis netlist of VTAXilinxShell by module name.
  *
  * The generic TB AXI (VtaHostDriver host master, MultiMemAxiClient DRAM slave)
  * is adapted to the Xilinx bundles with the AXI DataView (.viewAs), exactly as
  * XilinxShell does internally.
  */
class VTAPostSynthTb(
    memoryConfigs: Seq[MemoryConfig],
    layers: Seq[LaunchParams],
    perLayerTimeout: Int = 2000000
)(implicit p: Parameters)
    extends Module {
  val io = IO(new Bundle {
    val done = Output(Bool())
    val error = Output(Bool())
    val busy = Output(Bool())
    val layerIdx = Output(UInt(chisel3.util.log2Ceil(layers.size.max(2)).W))
    // AXI write-channel snoop (OUT capture), surfaced for sim_top's writes.log.
    val dbgW = new Bundle {
      val valid = Output(Bool())
      val addr = Output(UInt(32.W))
      val data = Output(UInt(64.W))
      val strb = Output(UInt(8.W))
      val last = Output(Bool())
    }
  })

  val vta = Module(new XilinxDebugShell)
  val dram = Module(
    new MultiMemAxiClient(memoryConfigs, enforceOutBounds = false)(
      p(ShellKey).memParams
    )
  )
  val driver = Module(new VtaHostDriver(layers, perLayerTimeout))

  // Board-faithful clock/reset: ap_clk = TB clock, ap_rst_n active-low.
  vta.ap_clk := clock
  vta.ap_rst_n := !reset.asBool

  // Adapt the Xilinx AXI ports to the generic bundles the TB drives.
  val mem = vta.m_axi_gmem.viewAs[AXIMaster]
  mem <> dram.io
  driver.io.host <> vta.s_axi_control.viewAs[AXILiteClient]

  // Advance layers from the bored VCR ctrl[1] (finish) 
  driver.io.finishHint := vta.debug.vcrCtrl(1)

  io.done := driver.io.done
  io.error := driver.io.error
  io.busy := driver.io.busy
  io.layerIdx := driver.io.layerIdx

  // Surface the shell's observation probes (vcrCtrl / computeState / computeDone)
  // so sim_top can print them for liveness triage on a watchdog timeout.
  val dbg = IO(Output(chiselTypeOf(vta.debug)))
  dbg := vta.debug

  // Per-burst byte-address tracking for the AXI write channel (single-beat burst
  // can present AW + first W in the same cycle for sparse stores).
  val awAddrReg = RegInit(0.U(32.W))
  val beatCnt = RegInit(0.U(9.W))
  val awFire = mem.aw.valid && mem.aw.ready
  val wFire = mem.w.valid && mem.w.ready
  val base = Mux(awFire, mem.aw.bits.addr, awAddrReg)
  val cnt = Mux(awFire, 0.U, beatCnt)
  when(awFire) { awAddrReg := mem.aw.bits.addr; beatCnt := 0.U }
  when(wFire && !awFire) { beatCnt := beatCnt + 1.U }
  when(wFire && awFire) { beatCnt := 1.U }
  io.dbgW.valid := wFire
  io.dbgW.addr := base + (cnt << 3)
  io.dbgW.data := mem.w.bits.data
  io.dbgW.strb := mem.w.bits.strb
  io.dbgW.last := mem.w.bits.last

  // End the simulation when all layers finish (RunUntilFinished / $finish).
  when(driver.io.done) { stop() }
}
