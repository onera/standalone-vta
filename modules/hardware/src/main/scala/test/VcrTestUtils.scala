package vta.test
import chisel3._
import vta.interface.axi.AXILiteClient
import vta.shell.VCRParams

trait VcrTestUtils extends AxiLiteSimUtils {

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
