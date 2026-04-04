package vta.test
import chisel3._
import chisel3.simulator.PeekPokeAPI
import vta.interface.axi.AXILiteClient

trait AxiLiteSimUtils extends PeekPokeAPI {

  def writeAxiLiteData(
      data: BigInt
  )(implicit clock: Clock, axi: AXILiteClient, timeout: Int = 2): Unit = {
    if (!axi.w.ready.peekBoolean()) {
      clock.stepUntil(axi.w.ready, 1, timeout)
    }
    axi.w.valid.poke(true.B)
    axi.w.bits.data.poke(data.U)
    clock.step()
    axi.w.valid.poke(false.B)
  }
  def writeAxiLiteWriteAddress(
      data: BigInt
  )(implicit clock: Clock, axi: AXILiteClient, timeout: Int = 2): Unit = {
    if (!axi.aw.ready.peekBoolean()) {
      clock.stepUntil(axi.aw.ready, 1, timeout)
    }
    axi.aw.valid.poke(true.B)
    axi.aw.bits.addr.poke(data.U)
    clock.step()
    axi.aw.valid.poke(false.B)
  }

  def writeAxiLiteReadAddress(
      data: BigInt
  )(implicit axi: AXILiteClient, clock: Clock, timeout: Int = 2): Unit = {
    if (!axi.ar.ready.peekBoolean()) {
      clock.stepUntil(axi.ar.ready, 1, timeout)
    }
    axi.ar.valid.poke(true.B)
    axi.ar.bits.addr.poke(data.U)
    clock.step()
    axi.w.valid.poke(false.B)
  }

  def readAxiLiteData()(implicit
      clock: Clock,
      axi: AXILiteClient,
      timeout: Int = 2
  ): Option[UInt] = {
    axi.r.ready.poke(true.B)
    clock.step()
    clock.stepUntil(axi.r.valid, 1, timeout)

    axi.r.ready.poke(false.B)
    if (axi.r.valid.peekBoolean()) {
      Some(axi.r.bits.data.peek())
    } else None
  }

}
