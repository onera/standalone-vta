package vta.shell
import chisel3._
import org.scalatest.flatspec.AnyFlatSpec
import org.scalatest.matchers.should.Matchers
import chisel3.simulator.scalatest.ChiselSim
import vta.util.config.Parameters
import vta.DefaultPynqConfig

import vta.interface.axi.AXILiteClient
import vta.shell.VCRParams
import _root_.util.SimulationUtils.verilatorWithWaveDump
import chisel3.simulator.HasSimulator

trait AxiVcrSim extends AnyFlatSpec with ChiselSim {

  def writeAxiData(
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
  def writeAxiWriteAddress(
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

  def writeAxiReadAddress(
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

  def readAxiData()(implicit
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
    writeAxiWriteAddress(address)
    writeAxiData(data)
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
class VCRSpec extends AnyFlatSpec with Matchers with ChiselSim with AxiVcrSim {
  behavior of "VCR"
  implicit val verilator: HasSimulator = verilatorWithWaveDump
  "Control registers" should "be writable from the host" in {
    implicit val parameters: Parameters = new DefaultPynqConfig
    simulate(new VCR) { vcr =>
      enableWaves()
      implicit val axi = vcr.io.host
      implicit val clock = vcr.clock
      vcr.io.host.b.ready.poke(true.B)
      for (i <- (0 to 9)) {
        writeControlRegister(i * 4, i + 11)
      }
    }
  }

  "Launch" should "be configurable from the host" in {
    implicit val parameters: Parameters = new DefaultPynqConfig
    simulate(new VCR) { vcr =>
      enableWaves()
      implicit val axi = vcr.io.host
      implicit val clock = vcr.clock
      vcr.io.host.b.ready.poke(true.B)

      launchVTA()
    }
  }

  "VCR" should "be configurable from the host" in {
    implicit val parameters: Parameters = new DefaultPynqConfig
    simulate(new VCR) { vcr =>
      enableWaves()
      implicit val axi = vcr.io.host
      implicit val clock = vcr.clock
      vcr.io.host.b.ready.poke(true.B)

      // Configure memory pointers
      writeInstructionBaseAddress(0)
      writeInstructionCount(5)
      writeUopBaseAddress(100)
      writeInputBaseAddress(200)
      writeWeightBaseAddress(300)
      writeAccBaseAddress(400)
      writeOutBaseAddress(500)

      launchVTA()
      clock.stepUntil(vcr.io.vcr.finish, 1, 10)
    }
  }
}
