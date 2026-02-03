package vta.shell
import chisel3._
import org.scalatest.flatspec.AnyFlatSpec
import chisel3.simulator.scalatest.ChiselSim
import vta.interface.axi.AXILiteClient

trait AxiLiteSimUtils extends AnyFlatSpec with ChiselSim {

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
    var istep = 0
    clock.step()
    clock.stepUntil(axi.r.valid, 1, timeout)

    axi.r.ready.poke(false.B)
    if (axi.r.valid.peekBoolean()) {
      Some(axi.r.bits.data.peek())
    } else None
  }

  def writeControlRegister(address: Int, data: Int)(implicit
      clock: Clock,
      axi: AXILiteClient
  ) = {
    implicit val timeout = 1
    writeAxiLiteWriteAddress(address)
    writeAxiLiteData(data)
  }
  def writeInstructionBaseAddress(
      baseAddress: Int
  )(implicit clock: Clock, axi: AXILiteClient) = {
    val vcr = VCRParams()
    writeVCRPtrs(0, baseAddress)
  }

  def writeInstructionCount(
      instructionCount: Int
  )(implicit clock: Clock, axi: AXILiteClient) =
    writeVCRVals(0, instructionCount)

  def writeInputBaseAddress(
      data: Int
  )(implicit clock: Clock, axi: AXILiteClient) = writeVCRPtrs(2, data)

  def writeWeightBaseAddress(
      data: Int
  )(implicit clock: Clock, axi: AXILiteClient) =
    writeVCRPtrs(3, data)

  def writeUopBaseAddress(
      data: Int
  )(implicit clock: Clock, axi: AXILiteClient) =
    writeVCRPtrs(1, data)

  def writeAccBaseAddress(
      data: Int
  )(implicit clock: Clock, axi: AXILiteClient) =
    writeVCRPtrs(4, data)

  def writeOutBaseAddress(
      data: Int
  )(implicit clock: Clock, axi: AXILiteClient) =
    writeVCRPtrs(5, data)

  def launchVTA()(implicit clock: Clock, axi: AXILiteClient) =
    writeControlRegister(0, 1)

  def writeVCRVals(add: Int, data: Int)(implicit
      clock: Clock,
      axi: AXILiteClient
  ) = {
    val vcr = VCRParams()
    val increment = vcr.nCtrl + vcr.nECnt
    writeControlRegister(4 * (increment + add), data)
  }
  def writeVCRPtrs(add: Int, data: Int)(implicit
      clock: Clock,
      axi: AXILiteClient
  ) = {
    val vcr = VCRParams()
    val increment = vcr.nCtrl + vcr.nECnt + vcr.nVals
    writeControlRegister(4 * (increment + add), data)
  }
}
