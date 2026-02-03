package vta.shell
import chisel3._
import org.scalatest.flatspec.AnyFlatSpec
import chisel3.simulator.scalatest.ChiselSim
import vta.interface.axi.AXILiteClient
import vta.interface.axi.AXIClient

trait AxiFullSimUtils extends AnyFlatSpec with ChiselSim {

  def writeAxiData(
      data: BigInt
  )(implicit clock: Clock, axi: AXIClient, timeout: Int = 2): Unit = {
    if (!axi.w.ready.peekBoolean()) {
      clock.stepUntil(axi.w.ready, 1, timeout)
    }
    axi.w.valid.poke(true.B)
    axi.w.bits.data.poke(data.U)
    clock.step()
    axi.w.valid.poke(false.B)
  }
  def writeAxiWriteAddress(
      address: BigInt
  )(implicit clock: Clock, axi: AXIClient, timeout: Int = 2): Unit = {
    if (!axi.aw.ready.peekBoolean()) {
      clock.stepUntil(axi.aw.ready, 1, timeout)
    }
    axi.aw.valid.poke(true.B)
    axi.aw.bits.addr.poke(address.U)
    clock.step()
    axi.aw.valid.poke(false.B)
  }

  def writeAxiReadAddress(
      address: BigInt
  )(implicit axi: AXIClient, clock: Clock, timeout: Int = 2): Unit = {
    if (!axi.ar.ready.peekBoolean()) {
      clock.stepUntil(axi.ar.ready, 1, timeout)
    }
    axi.ar.valid.poke(true.B)
    axi.ar.bits.addr.poke(address.U)
    clock.step()
    axi.w.valid.poke(false.B)
  }

  def readAxiData()(implicit
      clock: Clock,
      axi: AXIClient,
      timeout: Int = 2
  ): Option[UInt] = {
    axi.r.ready.poke(true.B)
    var istep = 0
    clock.step()
    clock.stepUntil(axi.r.valid, 1, timeout)

    axi.r.ready.poke(false.B)
    if (axi.r.valid.peekBoolean()) {
      Some(axi.r.bits.data.peek())
    } else None
  }

}
