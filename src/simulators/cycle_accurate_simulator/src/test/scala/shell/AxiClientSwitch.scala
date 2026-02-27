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
  val rSelectors =
    addresses.zipWithIndex
      .sortBy(_._1)
      .sliding(2)
      .map { case ((laddr, idl) :: (raddr, idr) :: Nil) =>
        idl -> enCondition(laddr, raddr, io.axis.ar.bits.addr)
      }
      .toMap

  val wSelectors =
    addresses.zipWithIndex
      .sortBy(_._1)
      .sliding(2)
      .map { case ((laddr, idl) :: (raddr, idr) :: Nil) =>
        idl -> enCondition(laddr, raddr, io.axis.aw.bits.addr)
      }
      .toMap

  io.axim.zipWithIndex.foreach { case (axim, id) =>
    // connect every interfaces
    axim <> io.axis
    // override ready valid signals to match selected client
    axim.ar.valid := io.axis.ar.valid && rSelectors(id)
    axim.r.ready := io.axis.r.ready && rSelectors(id)
    io.axis.ar.ready := axim.ar.ready && rSelectors(id)
    io.axis.r.valid := axim.r.valid && rSelectors(id)
    io.axis.r.bits.last := axim.r.bits.last && rSelectors(id)

    axim.aw.valid := io.axis.aw.valid && wSelectors(id)
    axim.w.valid := io.axis.w.valid && wSelectors(id)
    axim.w.bits.last := io.axis.w.bits.last && wSelectors(id)
    io.axis.aw.ready := axim.aw.ready && wSelectors(id)
    io.axis.w.ready := axim.w.ready && wSelectors(id)

    io.axis.b.valid := axim.b.valid && wSelectors(id)
    axim.b.ready := io.axis.b.ready && wSelectors(id)
  }

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
    simulate(new AxiClientSwitch(Seq(0, 10), 20)) { dut =>
      enableWaves()
      writeAxiWriteAddress(12, 1, 3)(dut.clock, dut.io.axis)
    }
  }

}
