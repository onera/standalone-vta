package vta.shell
import chisel3._
import org.scalatest.flatspec.AnyFlatSpec
import chisel3.simulator.scalatest.ChiselSim
import vta.core.CoreConfig
import vta.util.config.Parameters
import vta.interface.axi.AXILiteClient
import vta.interface.axi.AXILiteAddress
import vta.interface.axi.AXILiteMaster
import vta.util.config.Config
import vta.DefaultPynqConfig
import org.scalatest.matchers.should.Matchers
import chisel3.simulator.scalatest.HasCliOptions
import chisel3.simulator.scalatest.Cli
import chisel3.simulator.HasSimulator
import _root_.util.SimulationUtils.verilatorWithWaveDump
import vta.interface.axi.AXIMaster
import vta.interface.axi.AXIClient
import chisel3.util.experimental.loadMemoryFromFileInline
import firrtl.annotations.MemoryLoadFileType

class VTAShellSpec
    extends AnyFlatSpec
    with Matchers
    with ChiselSim
    with Cli.EmitFsdb
    with AxiVcrSim {
  behavior of "VTAShell"

  implicit val hasWaveDumpVerilator: HasSimulator = verilatorWithWaveDump
  it should "initiate processing with some configuration from host" in {

    implicit val parameters: Parameters = new DefaultPynqConfig
    simulate(new VTAShell) { vta =>
      enableWaves()
      implicit val clock = vta.clock
      implicit val axiLiteClient = vta.io.host
      implicit val timeout = 1
      vta.io.host.b.ready.poke(true.B)

      // Configure memory pointers
      writeInstructionBaseAddress(0)
      writeUopBaseAddress(100)
      writeInputBaseAddress(200)
      writeWeightBaseAddress(300)
      writeAccBaseAddress(400)
      writeOutBaseAddress(500)

      // Configure instruction size

      writeInstructionCount(5)

      // launch the processing of VTA
      launchVTA()

      clock.stepUntil(vta.vcr.io.vcr.finish, 1, 10)
    }
  }

  class SyncAxiDram(memoryFile: String = "")(implicit p: Parameters)
      extends Module {
    val io = IO(new AXIClient(p(ShellKey).memParams))
    val mem = SyncReadMem(1024, UInt(32.W))
    if (memoryFile.trim().nonEmpty) {
      loadMemoryFromFileInline(mem, memoryFile, MemoryLoadFileType.Binary)
    }
    val address = Reg(io.ar.bits.addr)
    when(io.ar.fire) {
      address := ???
    }

  }
  class VTAShellTestbench(implicit p: Parameters) extends Module {
    val io = IO(new Bundle {
      val host = new AXILiteClient(p(ShellKey).hostParams)
    })
    val vta = Module(new VTAShell)
    val mem = Module(new SyncAxiDram(""))
    vta.io.host <> io.host
    vta.io.mem <> mem.io
  }
  it should "execute the LeNet5 model" in {

    implicit val parameters: Parameters = new DefaultPynqConfig
  }
}
