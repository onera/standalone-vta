package vta.shell
import chisel3._
import org.scalatest.flatspec.AnyFlatSpec
import chisel3.simulator.scalatest.ChiselSim
import vta.core.CoreConfig
import vta.util.config.Parameters
import vta.interface.axi.AXILiteClient
import vta.interface.axi.AXILiteAddress
import vta.interface.axi.AXILiteMaster



class VTAShellSpec extends AnyFlatSpec with ChiselSim {
behavior of "VTAShell"

  def writeAxiData(
      data: BigInt,
      timeout: Int = 100
  )( implicit clock: Clock, axi: AXILiteClient): Unit = {
    axi.w.valid.poke(true.B)
    axi.w.bits.data.poke(data.U)
    var istep = 0
    clock.step()
    while (!axi.w.ready.peek().litToBoolean && istep < timeout) {
      clock.step()
      istep = istep + 1
    }
    axi.w.valid.poke(false.B)
  }
  def writeAxiWriteAddress(
      data: BigInt,
      timeout: Int = 100
  )( implicit clock: Clock, axi: AXILiteClient): Unit = {
    axi.aw.valid.poke(true.B)
    axi.aw.bits.addr.poke(data.U)
    var istep = 0
    clock.step()
    while (!axi.aw.ready.peek().litToBoolean && istep < timeout) {
      clock.step()
      istep = istep + 1
    }
    axi.aw.valid.poke(false.B)
  }

  def writeAxiReadAddress(
      data: BigInt,
      timeout: Int = 100
  )(implicit axi: AXILiteClient,clock: Clock): Unit = {
    axi.ar.valid.poke(true.B)
    axi.ar.bits.addr.poke(data.U)
    var istep = 0
    clock.step()
    while (!axi.ar.ready.peek().litToBoolean && istep < timeout) {
      clock.step()
      istep = istep + 1
    }
    axi.w.valid.poke(false.B)
  }

  def readAxiData(timeout: Int = 100)(implicit clock: Clock, axi: AXILiteClient): UInt = {
    axi.r.ready.poke(true.B)
    var istep = 0
    clock.step()
    while (!axi.r.valid.peek().litToBoolean && istep < timeout) {
      clock.step()
      istep = istep + 1
    }
//    assert(istep != timeout)
    axi.r.ready.poke(false.B)
    axi.r.bits.data.peek()
  }
 it should "correctly handle a single write transaction from the host" in {
   implicit val parameters: Parameters = new CoreConfig
   simulate(new VTAShell) {
     dut => 
       implicit val clock = dut.clock
       implicit val axiLiteClient = dut.io.host
       writeAxiWriteAddress(2,4)
       writeAxiData(32,4)
       writeAxiReadAddress(2,4)
       val dataRead = readAxiData()
   }
 } 
} 
