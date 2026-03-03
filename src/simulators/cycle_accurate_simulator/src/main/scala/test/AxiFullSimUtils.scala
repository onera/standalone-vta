package vta.test
import chisel3._
import org.scalatest.flatspec.AnyFlatSpec
import chisel3.simulator.ChiselSim
import vta.interface.axi.AXILiteClient
import vta.interface.axi.AXIClient
import chisel3.simulator.PeekPokeAPI
import chiseltest.testableData

trait AxiFullSimUtils extends PeekPokeAPI {

  def writeAxiData(
      data: BigInt,
      isLast: Boolean = false
  )(implicit clock: Clock, axi: AXIClient, timeout: Int = 2): Unit = {
    if (!axi.w.ready.peekBoolean()) {
      clock.stepUntil(axi.w.ready, 1, timeout)
    }
    axi.w.valid.poke(true.B)
    axi.w.bits.data.poke(data.U)
    axi.w.bits.last.poke(isLast.B)
    clock.step()
    axi.w.valid.poke(false.B)
    axi.w.bits.last.poke(false.B)
  }
  def writeAxiWriteAddress(
      address: BigInt,
      burst: Int = 0,
      len: Int = 0
  )(implicit clock: Clock, axi: AXIClient, timeout: Int = 2): Unit = {
    if (!axi.aw.ready.peekBoolean()) {
      clock.stepUntil(axi.aw.ready, 1, timeout)
    }
    axi.aw.valid.poke(true.B)
    axi.aw.bits.addr.poke(address.U)
    axi.aw.bits.burst.poke(burst)
    axi.aw.bits.len.poke(len)
    clock.step()
    axi.aw.valid.poke(false.B)
  }

  def writeAxiReadAddress(
      address: BigInt,
      burst: Int = 0,
      len: Int = 0
  )(implicit clock: Clock, axi: AXIClient, timeout: Int = 2): Unit = {
    if (!axi.ar.ready.peekBoolean()) {
      clock.stepUntil(axi.ar.ready, 1, timeout)
    }
    axi.ar.valid.poke(true.B)
    axi.ar.bits.addr.poke(address.U)
    axi.ar.bits.burst.poke(burst)
    axi.ar.bits.len.poke(len)
    clock.step()
    axi.ar.valid.poke(false.B)
  }

  def readAxiData()(implicit
      clock: Clock,
      axi: AXIClient,
      timeout: Int = 2
  ): Option[UInt] = {
    // clock.stepUntil(axi.r.valid, 1, timeout)
    axi.r.ready.poke(true.B)
    val res = if (axi.r.valid.peekBoolean()) {
      Some(axi.r.bits.data.peek())
    } else None
    clock.step()
    axi.r.ready.poke(false.B)
    res
  }

  def writeAxiBurst(baseAddress: Int, data: Seq[Int])(implicit
      clock: Clock,
      axi: AXIClient,
      timeout: Int = 2
  ): Unit = {
    writeAxiWriteAddress(baseAddress, 1, data.size - 1)
    clock.step()
    for (d <- data.dropRight(1)) {
      writeAxiData(d)
    }
    writeAxiData(data.last, true)
  }

  def readAxiBurst(baseAddress: Int, size: Int)(implicit
      clock: Clock,
      axi: AXIClient,
      timeout: Int = 2
  ) = {
    writeAxiReadAddress(baseAddress, 1, size - 1)
    for {
      i <- 0 until size
      d <- readAxiData()
    } yield {
      d
    }
  }

}
