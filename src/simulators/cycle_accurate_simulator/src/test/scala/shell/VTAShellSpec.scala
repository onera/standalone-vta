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
import vta.interface.axi.AxiClientWrapper
import _root_.util.BinaryReader
import chisel3.util.BinaryMemoryFile
import chisel3.util.SRAM
import circt.stage.ChiselStage
import chisel3.util.MemoryFile
import chisel3.util.HexMemoryFile
import chisel3.util.SRAMInterface
import chisel3.util.experimental.loadMemoryFromFile
import java.io.File
import os.Path

class VTAShellSpec
    extends AnyFlatSpec
    with Matchers
    with ChiselSim
    with Cli.EmitFsdb
    with AxiLiteSimUtils
    with AxiFullSimUtils {
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
      writeInstructionBaseAddress(10)
      writeUopBaseAddress(100)
      writeInputBaseAddress(200)
      writeWeightBaseAddress(300)
      writeAccBaseAddress(400)
      writeOutBaseAddress(500)

      // Configure instruction size

      writeInstructionCount(5)

      val instructions = Seq(
        "0xFFFFFFFF"
      )
      // Mock DRAM ready
      vta.io.mem.ar.ready.poke(true)
      vta.io.mem.r.valid.poke(true)
      vta.io.mem.aw.ready.poke(true)
      vta.io.mem.w.ready.poke(true)

      // launch the processing of VTA
      launchVTA()

      clock.step(100)
      // clock.stepUntil(vta.vcr.io.vcr.finish, 1, 10)
    }
  }

  class SyncAxiDram(file: String, size: Int)(implicit
      p: Parameters
  ) extends Module
      with AxiClientWrapper {
    val io = IO(new AXIClient(p(ShellKey).memParams))

    io.tieoff()
    // val mem = SRAM(size, UInt(32.W), 1, 1, 0, file)
    val mem = SyncReadMem(size, UInt(32.W))
    loadMemoryFromFile(mem, file)

    val readEnable = Wire(Bool())
    val axiReadAddress = readHandler(io, readEnable)
    val writeEnable = Wire(Bool())
    val axiWriteAddr = writeHandler(io, writeEnable)

    readEnable := true.B
    writeEnable := true.B

    io.r.bits.data := mem.read(axiReadAddress, readEnable, clock)
    when(io.w.fire) {
      mem.write(axiWriteAddr, io.w.bits.data)
    }
  }
  class VTAShellTestbench(file: String, size: Int)(implicit p: Parameters)
      extends Module {
    val io = IO(new Bundle {
      val host = new AXILiteClient(p(ShellKey).hostParams)
    })
    val vta = Module(new VTAShell)

    val mem = Module(new SyncAxiDram(file, size))

    vta.io.host <> io.host
    vta.io.mem <> mem.io
  }

  it should "run with fake DRAM" in {

    implicit val parameters: Parameters = new DefaultPynqConfig
    val path = "examples_core/simple.mem"
    val file =
      getClass.getClassLoader.getResourceAsStream(path)
    val size = file.available()
    file.close()
    simulate(new VTAShellTestbench(path, size)) { vta =>
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

      clock.step(100)
    }
  }

  "Fake DRAM" should "init mem from file" in {
    implicit val parameters: Parameters = new DefaultPynqConfig
    val memoryFile = "examples_core/simple.mem"
    val file =
      getClass.getClassLoader.getResource(memoryFile).getPath()

    val targetPath = Path(
      buildDir.toAbsolutePath().toString
    ) / "VTAShellSpec" / "Fake-DRAM" / "should-init-mem-from-file"

    val targetFile = targetPath / "primary-sources" / "simple.mem"
    os.copy(
      Path(file),
      targetFile,
      createFolders = true,
      replaceExisting = true
    )
    val size = 16

    simulate(
      new SyncAxiDram("../primary-souces/simple.mem", size)
    ) { dut =>
      enableWaves()
      implicit val clock = dut.clock
      implicit val axiFull = dut.io
      for (i <- 0 until 16) {
        writeAxiReadAddress(i)
        val d = readAxiData()
        println(d)
        dut.clock.step()
      }
      dut.clock.step()
    }
  }
}
