package vta.shell
import chisel3._
import org.scalatest.flatspec.AnyFlatSpec
import chisel3.simulator.scalatest.ChiselSim
import vta.core.CoreConfig
import vta.util.config.Parameters
import vta.interface.axi.{
  AXIAddress,
  AXIClient,
  AXILiteAddress,
  AXILiteClient,
  AXILiteMaster,
  AXIMaster,
  AxiClientWrapper
}
import vta.util.config.Config
import vta.DefaultPynqConfig
import org.scalatest.matchers.should.Matchers
import chisel3.simulator.scalatest.HasCliOptions
import chisel3.simulator.scalatest.Cli
import chisel3.simulator.HasSimulator
import _root_.util.SimulationUtils.verilatorWithWaveDump
import chisel3.util.experimental.loadMemoryFromFileInline
import firrtl.annotations.MemoryLoadFileType
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
import chisel3.simulator.PeekPokeAPI.TestableRecord
import chisel3.simulator.PeekPokeAPI.TestableEnum
import com.fasterxml.jackson.databind.ObjectMapper

import scala.io.Source
import com.fasterxml.jackson.module.scala.DefaultScalaModule
import chisel3.util.MuxCase
import chisel3.util.Cat
import vta.core.ISA
import vta.core.VTAISA.OpCode.LOAD
import chisel3.util.experimental.BoringUtils
import chisel3.simulator.stimulus.RunUntilFinished
import chisel3.util.HasExtModuleResource
import chisel3.util.HasBlackBoxResource
import vta.shell.InstructionGen.Load
import vta.shell.InstructionGen.Gemm
import svsim.CommonCompilationSettings
import svsim.CommonSettingsModifications
import _root_.util.SimulationUtils.EnableMemInitVerilog

class VTAShellSpec
    extends AnyFlatSpec
    with Matchers
    with ChiselSim
    with Cli.EmitFsdb
    with AxiLiteSimUtils
    with AxiFullSimUtils {
  behavior of "VTAShell"

  implicit val hasWaveDumpVerilator: HasSimulator = verilatorWithWaveDump
  def parseJsonMemoryInitFile(file: String) = {
    val bufferedSource =
      Source.fromURL(
        getClass.getClassLoader().getResource(file)
      )
    val mapper = new ObjectMapper()
    mapper.registerModule(DefaultScalaModule)
    val dramInitJson =
      mapper.readValue(
        bufferedSource.reader(),
        classOf[Map[String, Map[String, Object]]]
      )
    bufferedSource.close
    dramInitJson("QLinearConv1")
  }
  def parseMemorySection(name: String, map: Map[String, Object]) = {
    val address = map(name) match {
      case m: Map[String, String] => m("PhysicalAddr").toInt
    }
    val values = map(name) match {
      case m: Map[String, Object] =>
        m("values") match {
          case l: List[String] => l
        }
    }
    (address, values)
  }

  def parseMemorySections(map: Map[String, Object]) = map.map { p =>
    val address = p._2 match {
      case m: Map[String, String] => {
        val s = m("PhysicalAddr")
        ("x" + s).U((s.size * 4).W).litValue.toInt
      }
    }
    val values = p._2 match {
      case m: Map[String, Object] =>
        m("values") match {
          case l: List[String] => l.map { s => ("x" + s).U((s.size * 4).W) }
        }
    }
    (p._1 -> (address, values))
  }

  val dramInitJson =
    parseJsonMemoryInitFile("examples_core/dram_state.json")

  val instr = parseMemorySection("INSN", dramInitJson)
  val instrAddress = instr._1
  val instructionHexSeq = instr._2
  val instructionHexWord64 =
    instructionHexSeq.map(instr =>
      instr.drop(1).grouped((instr.size - 1) / 2).toSeq.reverse
    )
  val instructions =
    instructionHexWord64.flatten.map(s => ("x" + s).U(64.W))

  def getAddress(name: String, size: Int) = {
    val data = parseMemorySection(name, dramInitJson)
    val address = data._1
    address
  }

  def getValues(name: String, size: Int) = {
    val data = parseMemorySection(name, dramInitJson)
    val address = data._1
    val values = data._2.map(s => ("x" + s).U(size.W))
    values
  }
  def inputs = getValues("INP", 32)
  def weights = getValues("WGT", 32)
  def accs = getValues("ACC", 32)
  def outputs = getValues("OUT", 32)
  def uops = getValues("UOP", 32)

  val inputAddress = getAddress("INP", 32)
  val weightAddress = getAddress("WGT", 32)
  val accAddress = getAddress("ACC", 32)
  val outAddress = getAddress("OUT", 32)
  val uopAddress = getAddress("UOP", 32)

  class DramWithInit(memoryFile: String, size: Int)(implicit p: Parameters)
      extends Module
      with AxiClientWrapper {
    val io = IO(new AXIClient(p(ShellKey).memParams))

    val mem = SyncReadMem(
      size,
      UInt(p(ShellKey).memParams.dataBits.W)
    )
    if (memoryFile.trim().nonEmpty) {
      loadMemoryFromFile(mem, memoryFile)
    }
    val readHandle = readHandler(io, true.B)

    val writeHandle = writeHandler(io, true.B)

    io.r.bits.data := mem.read(readHandle)
    when(io.w.fire) {
      mem.write(writeHandle, io.w.bits.data)
      io.b.valid := true.B
    }

    io.b.bits.user := DontCare
    io.r.bits.user := DontCare
  }

  class DramMockModule(content: Map[String, (Int, Seq[UInt])])(implicit
      p: Parameters
  ) extends Module
      with AxiClientWrapper {
    val io = IO(new AXIClient(p(ShellKey).memParams))
    // io.tieoff()

    def reshapeMem(data: Seq[UInt]) = VecInit(
      data
        .grouped(2)
        .map {
          case l if l.size == 2 => Cat(l.head, l.last).asTypeOf(UInt(64.W))
          case l if l.size == 1 => Cat(l.head, 0.U(32.W)).asTypeOf(UInt(64.W))
        }
        .toSeq
    )
    val inputsVec = reshapeMem(content("INP")._2)
    val weightsVec = reshapeMem(content("WGT")._2)
    val accsVec = reshapeMem(content("ACC")._2)
    val outputsVec = reshapeMem(content("OUT")._2)
    val uopsVec = VecInit(content("UOP")._2)
    val instrVec = VecInit(
      content("INSN")._2.flatMap(u =>
        Seq(u(63, 0), u(127, 64))
      ) // split instructions in 64 words
    )
    val inputAddress = content("INP")._1
    val instrAddress = content("INSN")._1
    val weightAddress = content("WGT")._1
    val accAddress = content("ACC")._1
    val outAddress = content("OUT")._1
    val uopAddress = content("UOP")._1
    val readHandle = readHandler(io, true.B)
    val writeHandle = writeHandler(io, true.B)

    def enCondition(addr: Int, size: Int) = WireInit(
      addr.U <= readHandle && readHandle < (addr + size).U
    )
    val enInp = enCondition(inputAddress, inputsVec.size)

    val enInstr = WireInit(
      instrAddress.U <= readHandle && readHandle < (instrAddress + weights.size).U
    )
    val enWgt = WireInit(
      weightAddress.U <= readHandle && readHandle < (weightAddress + weights.size).U
    )
    val enAcc = WireInit(
      accAddress.U <= readHandle && readHandle < (accAddress + accs.size).U
    )
    val enUop = WireInit(
      uopAddress.U <= readHandle && readHandle < (uopAddress + uops.size).U
    )

    val enOut = WireInit(
      outAddress.U <= readHandle && readHandle < (outAddress + outputs.size).U
    )

    val enWrOut = WireInit(
      outAddress.U <= writeHandle && writeHandle < (outAddress + outputs.size).U
    )
    val mem = Reg(Vec(outputs.size, UInt(64.W)))

    io.r.bits.data := MuxCase(
      DontCare,
      // "xdeadbeef".U,
      Seq(
        enInstr -> instrVec(
          readHandle - instrAddress.U
        ),
        enInp -> inputsVec(
          readHandle - inputAddress.U
        ),
        enWgt -> weightsVec(
          readHandle - weightAddress.U
        ),
        enAcc -> accsVec(
          readHandle - accAddress.U
        ),
        enUop -> uopsVec(
          readHandle - uopAddress.U
        ),
        enOut ->
          mem(readHandle - outAddress.U)
      )
    )
    when(io.w.fire && enWrOut) {
      mem(writeHandle - outAddress.U) := io.w.bits.data
      io.b.valid := true.B
    }
    io.b.bits.user := DontCare
    io.r.bits.user := DontCare
  }

  class VTAShellTestbenchFileInit(
      content: Seq[MemoryConfig]
  )(implicit
      param: Parameters
  ) extends Module {
    val io = IO(new Bundle {
      val host = new AXILiteClient(param(ShellKey).hostParams)
    })
    val vta = Module(new VTAShell(true))

    val dramMock = Module(
      new MultiMemAxiClient(content)(param(ShellKey).memParams)
    )
    val stop_read = dontTouch(
      WireInit(BoringUtils.tapAndRead(vta.vcr.io.vcr.finish))
    )
    when(stop_read) {
      stop()
    }
    vta.io.host <> io.host
    vta.io.mem <> dramMock.io
  }

  class VTAShellTestbench(content: Map[String, (Int, Seq[UInt])])(implicit
      p: Parameters
  ) extends Module {
    val io = IO(new Bundle {
      val host = new AXILiteClient(p(ShellKey).hostParams)
    })
    val vta = Module(new VTAShell(true))

    val mem = Module(new DramMockModule(content))

    val stop_read = dontTouch(
      WireInit(BoringUtils.tapAndRead(vta.vcr.io.vcr.finish))
    )
    when(stop_read) {
      stop()
    }
    vta.io.host <> io.host
    vta.io.mem <> mem.io
  }

  def runVtaTestWithMockDram(
      content: Map[String, (Int, Seq[UInt])],
      timeout: Int = 100,
      waves: Boolean = false
  ) = {
    implicit val parameters: Parameters = new DefaultPynqConfig

    // val content = parseMemorySections(dramInitJson)
    simulate(new VTAShellTestbench(content)) { vta =>
      implicit val clock = vta.clock
      implicit val axiLiteClient = vta.io.host
      vta.io.host.b.ready.poke(true.B)

      if (waves) {
        enableWaves()
      }

      // Configure memory physical addresses
      writeInstructionBaseAddress(content("INSN")._1)
      writeUopBaseAddress(0)
      writeInputBaseAddress(0)
      writeWeightBaseAddress(0)
      writeAccBaseAddress(0)
      writeOutBaseAddress(0)
      // Configure instruction size

      writeInstructionCount(content("INSN")._2.size)

      // launch the processing of VTA
      launchVTA()

      clock.step(timeout)
      // step clock until the computation is over
      RunUntilFinished(timeout)
    }
  }
  def runVtaTestWithInitializedMem(
      content: Seq[MemoryConfig],
      timeout: Int = 100,
      waves: Boolean = false
  ) = {
    implicit val parameters: Parameters = new DefaultPynqConfig

    val compilationSettings = svsim.CommonCompilationSettings.default

    implicit val enableMemoryInit = EnableMemInitVerilog
    // val content = parseMemorySections(dramInitJson)
    simulate(
      new VTAShellTestbenchFileInit(content),
      firtoolOpts = Array("--disable-all-randomization")
    ) { vta =>
      implicit val clock = vta.clock
      implicit val axiLiteClient = vta.io.host
      vta.io.host.b.ready.poke(true.B)

      if (waves) {
        enableWaves()
      }

      writeInstructionBaseAddress(
        content.find(_.name.matches("INSN")).get.baseAddress
      )
      writeUopBaseAddress(0)
      writeInputBaseAddress(0)
      writeWeightBaseAddress(0)
      writeAccBaseAddress(0)
      writeOutBaseAddress(0)
      // Configure instruction size

      writeInstructionCount(
        content.find(_.name.matches("INSN")).get.initialSize
      )

      // launch the processing of VTA
      launchVTA()

      // step clock until the computation is over
      clock.step(timeout)
      RunUntilFinished(timeout)
    }
  }

  it should "run with initialization from JSON file" in {
    implicit val parameters: Parameters = new DefaultPynqConfig

    val content = parseMemorySections(dramInitJson).map {
      case ("INP", (i, s)) =>
        "INP" -> (
          i,
          (0 until s.size).map(v => v.toInt.U(32.W))
        )
      case l => l
    }
    runVtaTestWithMockDram(
      content,
      timeout = 10000,
      waves = true
    )
  }

  it should "run with initialization from Hex files" in {

    implicit val parameters: Parameters = new DefaultPynqConfig

    val content = parseMemorySections(dramInitJson)
      .map { case (a, (b, c)) =>
        MemoryConfig(
          name = a,
          path = (os.pwd / "generatedResources" / (a + ".mem")).toString,
          baseAddress = b,
          initialSize = c.size,
          words64 = {
            val n = c.map(_.getWidth).sum
            if (n % 64 == 0) n / 64 else (n / 64) + 1
          }
        )
      }
      .toSeq
      .map {
        case m: MemoryConfig if m.name.matches("OUT") =>
          m.copy(logging = true)
        case m: MemoryConfig => m
      }

    runVtaTestWithInitializedMem(
      content,
      timeout = 10000,
      waves = true
    )

  }

  it should "print the sizes of content" in {
    val content = parseMemorySections(dramInitJson)
    val sizes = content.view.mapValues { case (i, s) =>
      (i, s.size)
    }.toMap
    println(sizes)
    val countInp = content("INP")._2.count(_.litValue.toInt != 0)
    println(countInp)

  }

  it should "write a burst in Mock Dram and read" in {
    implicit val parameters: Parameters = new DefaultPynqConfig
    val content = parseMemorySections(dramInitJson)
    simulate(new DramMockModule(content)) { dut =>
      enableWaves()
      implicit val clock = dut.clock
      implicit val axi = dut.io
      implicit val timeout = 10
      writeAxiBurst(content("OUT")._1, (0 until 10))
      val res = readAxiBurst(content("OUT")._1, 10)
      println(res)
      res.size shouldBe 10
    }
  }

  it should "export VTA" in {
    implicit val parameters: Parameters = new DefaultPynqConfig

    ChiselStage.emitCHIRRTLFile(new VTAShell, Array(""))
  }

  it should "export the content in hex files" in {
    val content = parseMemorySections(dramInitJson)

    MemoryInitializer.exportHexFiles(
      content,
      os.pwd / "generatedResources"
    )
  }
}
