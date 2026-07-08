package vta.test

import chisel3._
import chisel3.util._
import vta.interface.axi.AXILiteMaster
import vta.interface.axi.AxiLike._
import vta.shell.{ShellKey, VCRParams}
import vta.util.config.Parameters

import TestBenchLayout.LaunchParams

/** Synthesizable hardware per-layer VTA driver. Walks a baked-in layer ROM: for each layer it
  * programs the VCR pointer/value registers, writes ctrl=1 to launch, polls
  * ctrl bit1 (finish) over AXI-Lite, then advances. Raises `done` after the
  * last layer; raises `error` (latching `layerIdx`) if a layer never finishes
  * within `perLayerTimeout` cycles.
  */
class VtaHostDriver(layers: Seq[LaunchParams], perLayerTimeout: Int = 2000000)(
    implicit p: Parameters
) extends Module {
  require(layers.nonEmpty, "VtaHostDriver needs at least one layer")
  val hp = p(ShellKey).hostParams
  val nLayers = layers.size
  val idxW = log2Ceil(nLayers.max(2))

  val io = IO(new Bundle {
    val host = new AXILiteMaster(hp)
    val done = Output(Bool())
    val error = Output(Bool())
    val busy = Output(Bool())
    val layerIdx = Output(UInt(idxW.W))
    // Direct (clean) finish signal for post-synth funcsim: the AXI-Lite ctrl read-back is X
    // there because the read address is don't-care while the design just runs (the priority
    // read-mux selector goes X -> rdata X). The bored VCR ctrl[1] probe is clean, so the TB
    // feeds it here to advance layers. Defaults to false so real-HW behaviour (AXI poll) is
    // unchanged when left unconnected/tied low.
    val finishHint = Input(Bool())
  })

  // VCR byte offsets (mirror VcrTestUtils / VCR register order).
  val vcr = VCRParams()
  val ctrlOff = 0
  val valsOff = (vcr.nCtrl + vcr.nECnt) * 4
  val ptrsOff = (vcr.nCtrl + vcr.nECnt + vcr.nVals) * 4
  def ptrOff(i: Int) = ptrsOff + 4 * i

  // Layer ROM. All values written as data words on the host bus.
  val dW = hp.dataBits
  val romInsnBaddr = VecInit(layers.map(l => l.insnBaddr.U(dW.W)))
  val romInsnCount = VecInit(layers.map(l => l.insnCount.U(dW.W)))
  val romRelo = VecInit(layers.map(l => l.relo.U(dW.W)))

  // Per-layer programming micro-sequence: 8 register writes, launch last.
  val NPROG = 8
  val progAddr = VecInit(
    Seq(
      ptrOff(1),
      ptrOff(2),
      ptrOff(3),
      ptrOff(4),
      ptrOff(5), // uop,inp,wgt,acc,out
      ptrOff(0), // insn base
      valsOff, // insn count
      ctrlOff // launch (=1)
    ).map(_.U(hp.addrBits.W))
  )

  val layerReg = RegInit(0.U(idxW.W))
  val progIdx = RegInit(0.U(log2Ceil(NPROG).W))

  def progData(idx: UInt): UInt = {
    val relo = romRelo(layerReg)
    MuxLookup(idx, 0.U)(
      Seq(
        0.U -> relo,
        1.U -> relo,
        2.U -> relo,
        3.U -> relo,
        4.U -> relo,
        5.U -> romInsnBaddr(layerReg),
        6.U -> romInsnCount(layerReg),
        7.U -> 1.U // launch bit
      )
    )
  }

  val sProgram :: sPoll :: sNext :: sDone :: sError :: Nil = Enum(5)
  val state = RegInit(sProgram)

  // AXI-Lite master transaction wires (single-outstanding).
  val wrStart = WireDefault(false.B)
  val rdStart = WireDefault(false.B)
  val wrAddr = WireDefault(0.U(hp.addrBits.W))
  val wrData = WireDefault(0.U(hp.dataBits.W))
  val rdAddr = WireDefault(0.U(hp.addrBits.W))

  val wrDone = io.host.writeHandler(wrStart, wrAddr, wrData)
  val (rdData, rdDone) = io.host.readHandler(rdStart, rdAddr)

  // Busy regs ensure each start is a single pulse and we never overlap txns.
  val wrBusy = RegInit(false.B)
  when(wrStart) { wrBusy := true.B }.elsewhen(wrDone) { wrBusy := false.B }
  val rdBusy = RegInit(false.B)
  when(rdStart) { rdBusy := true.B }.elsewhen(rdDone) { rdBusy := false.B }

  val watchdog = RegInit(0.U(32.W))

  io.done := state === sDone
  io.error := state === sError
  io.busy := (state =/= sDone) && (state =/= sError)
  io.layerIdx := layerReg

  switch(state) {
    is(sProgram) {
      wrAddr := progAddr(progIdx)
      wrData := progData(progIdx)
      when(!wrBusy) { wrStart := true.B }
      when(wrDone) {
        when(progIdx === (NPROG - 1).U) {
          progIdx := 0.U
          watchdog := 0.U
          state := sPoll
        }.otherwise {
          progIdx := progIdx + 1.U
        }
      }
    }
    is(sPoll) {
      rdAddr := ctrlOff.U
      when(!rdBusy) { rdStart := true.B }
      watchdog := watchdog + 1.U
      when(
        (rdDone && rdData(1)) || io.finishHint
      ) { // ctrl bit1 = finish flag (AXI poll or clean probe)
        state := sNext
      }
      when(watchdog >= perLayerTimeout.U) {
        state := sError
      }
    }
    is(sNext) {
      when(layerReg === (nLayers - 1).U) {
        state := sDone
      }.otherwise {
        layerReg := layerReg + 1.U
        progIdx := 0.U
        state := sProgram
      }
    }
    is(sDone) {}
    is(sError) {}
  }
}
