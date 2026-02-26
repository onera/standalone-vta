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
import circt.stage.ChiselStage
import svsim.verilator.Backend.CompilationSettings
import svsim.BackendSettingsModifications
import svsim.CommonSettingsModifications
import svsim.CommonCompilationSettings

class SyncAxiDramSpec extends AnyFlatSpec with ChiselSim with AxiFullSimUtils {

  class InitMemInline(memoryFile: String = "", size: Int, width: Int)
      extends Module {
    val io = IO(new Bundle {
      val enable = Input(Bool())
      val write = Input(Bool())
      val addr = Input(UInt(10.W))
      val dataIn = Input(UInt(width.W))
      val dataOut = Output(UInt(width.W))
    })

    val mem = SyncReadMem(size, UInt(width.W))
    // Initialize memory
    if (memoryFile.trim().nonEmpty) {
      loadMemoryFromFileInline(mem, memoryFile)
    }
    io.dataOut := DontCare
    when(io.enable) {
      val rdwrPort = mem(io.addr)
      when(io.write) { rdwrPort := io.dataIn }
        .otherwise { io.dataOut := rdwrPort }
    }
  }

  "InitMemInline" should "be simulable" in {
    val resource = "examples_core/simple.mem"
    implicit val simulator = verilatorWithWaveDump

    val file = getClass.getClassLoader.getResource(resource).getFile()

    val compilationSettings = svsim.CommonCompilationSettings.default

    implicit object EnableMemInitVerilog extends CommonSettingsModifications {

      override def apply(
          v1: CommonCompilationSettings
      ): CommonCompilationSettings = {
        v1.copy(verilogPreprocessorDefines =
          compilationSettings.verilogPreprocessorDefines :+ CommonCompilationSettings
            .VerilogPreprocessorDefine("ENABLE_INITIAL_MEM_")
        )
      }

    }

    simulate(
      new InitMemInline(file, 16, 32),
      // Array("--verilator-cflags", "-DENABLE_MEM_INIT=1"),
      firtoolOpts = Array("--disable-all-randomization")
    ) { mem =>
      enableWaves()
      mem.io.enable.poke(true)
      for (i <- 1 until 10) {
        mem.io.dataIn.poke(i)
        mem.io.addr.poke(i)
        mem.io.write.poke(false)
        mem.clock.step()
        println(mem.io.dataOut.peek())
        // mem.io.dataOut.expect(i)
      }
    }
  }
  def mergeMemories(path: String, fromResources: Boolean = true) = {
    val instrFile = path + "/instructions.bin"
    val inputFile = path + "/input.bin"
    val weightFile = path + "/weight.bin"
    val addrFile = path + "/memory_addresses.csv"
    val uopFile = path + "/uop.bin"
    val outFile = path + "/out.bin"
    val accuFile = path + "/accumulator.bin"
    val addresses = BinaryReader.computeCSVFile(addrFile, true, true)
    for {
      instr <- BinaryReader.computeAddresses(
        instrFile,
        BinaryReader.DataType.INSN,
        "00000000",
        true,
        true
      )
      inputs <- BinaryReader.computeAddresses(
        inputFile,
        BinaryReader.DataType.INP,
        addresses("inp"),
        true,
        true
      )
      weights <- BinaryReader.computeAddresses(
        weightFile,
        BinaryReader.DataType.WGT,
        addresses("wgt"),
        true,
        true
      )
      uop <- BinaryReader.computeAddresses(
        uopFile,
        BinaryReader.DataType.UOP,
        addresses("uop"),
        true,
        true
      )
      accu <- BinaryReader.computeAddresses(
        accuFile,
        BinaryReader.DataType.ACC,
        addresses("acc"),
        true,
        true
      )
      out <- BinaryReader.computeAddresses(
        outFile,
        BinaryReader.DataType.OUT,
        addresses("out"),
        true,
        true
      )
    } yield {
      instr ++ inputs ++ weights ++ uop ++ accu ++ out
    }
  }
  it should "read a binary instruction file" in {
    val path = "examples_compute/16x16"
    for {
      mem <- mergeMemories(path)
    } {
      println(mem)
    }
  }
  it should "read a binary file" in {
    val path = "examples_compute/16x16/weight.bin"
    val stream = getClass.getClassLoader.getResourceAsStream(path)
    val bytes = stream.readAllBytes()
    stream.close()
    println(bytes.size)
  }
}
