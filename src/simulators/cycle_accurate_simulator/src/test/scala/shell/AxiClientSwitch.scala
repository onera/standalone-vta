package vta.shell

import chisel3._
import vta.interface.axi.AXIClient
import vta.interface.axi.AxiClientWrapper
import vta.util.config.Parameters
import vta.interface.axi.AXIMaster
import chisel3.util.MuxCase
import org.scalatest.flatspec.AnyFlatSpec
import chisel3.simulator.ChiselSim
import circt.stage.ChiselStage
import vta.DefaultPynqConfig
import _root_.util.SimulationUtils
import chisel3.util.RegEnable

/** A very crude implementation of an AXI interconnect (combinational switch)
  * for simulation only
  *
  * @param baseAdresses
  *   the addresses of the clients, an axi master interface is created for each
  *   one
  * @param maxAdress
  *   the maximum addressable value
  * @param p
  *   VTA parameters
  */
class AxiClientSwitch(baseAdresses: Seq[BigInt], maxAdress: BigInt)(implicit
    p: Parameters
) extends Module
    with AxiClientWrapper {

  val io = IO(new Bundle {
    val axis = new AXIClient(p(ShellKey).memParams)
    val axim = Vec(baseAdresses.size, new AXIMaster(p(ShellKey).memParams))
  })

  require(maxAdress > baseAdresses.max)
  val addresses = baseAdresses :+ maxAdress
  def enCondition(addr: BigInt, laddr: BigInt, addressW: UInt) =
    addr.U <= addressW && addressW < (laddr).U

  val axisAwValid = Reg(Bool())
  val axisArValid = Reg(Bool())
  val axisArBits = RegEnable(io.axis.ar.bits, io.axis.ar.valid)
  val axisAwBits = RegEnable(io.axis.aw.bits, io.axis.aw.valid)
  val rSelectors =
    addresses.zipWithIndex
      .sortBy(_._1)
      .sliding(2)
      .map { case ((laddr, idl) :: (raddr, idr) :: Nil) =>
        idl -> enCondition(laddr, raddr, axisArBits.addr)
      }
      .toMap

  val wSelectors =
    addresses.zipWithIndex
      .sortBy(_._1)
      .sliding(2)
      .map { case ((laddr, idl) :: (raddr, idr) :: Nil) =>
        idl -> enCondition(laddr, raddr, axisAwBits.addr)
      }
      .toMap

  println(rSelectors, wSelectors)
  io.axis.r.bits := MuxCase(
    0.U.asTypeOf(chiselTypeOf(io.axis.r.bits)),
    rSelectors.map(e => e._2 -> io.axim(e._1).r.bits).toSeq
  )

  io.axis.r.valid := MuxCase(
    false.B,
    rSelectors.map(e => e._2 -> io.axim(e._1).r.valid).toSeq
  )

  val axisArReady = Reg(Bool())
  axisArReady := MuxCase(
    true.B,
    rSelectors.map(e => e._2 -> io.axim(e._1).ar.ready).toSeq
  )
  io.axis.ar.ready := axisArReady

  val axisAwReady = Reg(Bool())
  axisAwReady := MuxCase(
    true.B,
    rSelectors.map(e => e._2 -> io.axim(e._1).aw.ready).toSeq
  )
  io.axis.aw.ready := axisAwReady

  io.axis.w.ready := MuxCase(
    true.B,
    rSelectors.map(e => e._2 -> io.axim(e._1).w.ready).toSeq
  )

  io.axis.b.valid := MuxCase(
    false.B,
    rSelectors.map(e => e._2 -> io.axim(e._1).b.valid).toSeq
  )

  io.axis.b.bits := MuxCase(
    0.U.asTypeOf(chiselTypeOf(io.axis.b.bits)),
    rSelectors.map(e => e._2 -> io.axim(e._1).b.bits).toSeq
  )

  axisArValid := io.axis.ar.valid
  axisAwValid := io.axis.aw.valid
  // axisAwBits := io.axis.aw.bits
  // axisArBits := io.axis.ar.bits

  io.axim.zipWithIndex.foreach { case (axim, id) =>
    // connect every interfaces
    // axim.ar := io.axis.ar
    // axim.aw := io.axis.aw
    // axim.b := io.axis.b

    // override ready valid signals to match selected client
    axim.ar.valid := axisArValid && rSelectors(id)
    axim.r.ready := io.axis.r.ready && rSelectors(id)
    // io.axis.ar.ready := axim.ar.ready && rSelectors(id)
    // io.axis.r.valid := axim.r.valid && rSelectors(id)

    axim.aw.bits := axisAwBits
    axim.aw.bits.addr := Mux(
      wSelectors(id),
      axisAwBits.addr - baseAdresses(id).U,
      0.U
    )
    axim.ar.bits := axisArBits

    axim.ar.bits.addr := Mux(
      rSelectors(id),
      axisArBits.addr - baseAdresses(id).U,
      0.U
    )
    axim.w.bits := io.axis.w.bits

    axim.aw.valid := axisAwValid && wSelectors(id)
    axim.w.valid := io.axis.w.valid && wSelectors(id)
    axim.w.bits.last := io.axis.w.bits.last && wSelectors(id)
    // io.axis.aw.ready := axim.aw.ready && wSelectors(id)
    // io.axis.w.ready := axim.w.ready && wSelectors(id)

    // io.axis.b.valid := axim.b.valid && wSelectors(id)
    axim.b.ready := io.axis.b.ready && wSelectors(id)
  }

}

class AxiClientSwitchTestBench(implicit p: Parameters) extends Module {
  val io = IO(new AXIClient(p(ShellKey).memParams))

  val axiSwitch = Module(new AxiClientSwitch(Seq(0, 10), 20))
  val axiMem0 = Module(new SyncAxiDram("", 10, 32))
  val axiMem1 = Module(new SyncAxiDram("", 10, 32))
  axiSwitch.io.axim.head <> axiMem0.io.axis
  axiSwitch.io.axim.last <> axiMem1.io.axis
  io <> axiSwitch.io.axis
}

class AxiClientSwitchSpec
    extends AnyFlatSpec
    with ChiselSim
    with AxiFullSimUtils {
  behavior of "AxiClientSwitch"

  implicit val p: Parameters = new DefaultPynqConfig
  it should "be compiled" in {
    val sv = ChiselStage.emitSystemVerilog(new AxiClientSwitch(Seq(0, 10), 20))
    println(sv)
  }

  it should "run axi transactions on 1st client" in {
    implicit val verilatorWithWaveDump = SimulationUtils.verilatorWithWaveDump
    simulate(new AxiClientSwitchTestBench) { dut =>
      enableWaves()
      implicit val clock = dut.clock
      implicit val axi = dut.io
      writeAxiBurst(1, Seq(23, 34, 12))
      val res = readAxiBurst(1, 4)
      println(res)
    }
  }

  it should "run axi transactions on 2nd client" in {
    implicit val verilatorWithWaveDump = SimulationUtils.verilatorWithWaveDump
    simulate(new AxiClientSwitchTestBench) { dut =>
      enableWaves()
      implicit val clock = dut.clock
      implicit val axi = dut.io
      writeAxiBurst(11, Seq(23, 34, 12))
      val res = readAxiBurst(11, 4)
      println(res)
    }
  }
}
