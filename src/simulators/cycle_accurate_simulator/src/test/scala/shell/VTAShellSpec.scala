package vta.shell
import chisel3._
import chisel3.simulator.HasSimulator
import chisel3.simulator.scalatest.ChiselSim
import chisel3.simulator.scalatest.Cli
import chisel3.simulator.stimulus.RunUntilFinished
import chisel3.util.HasBlackBoxResource
import chisel3.util.HasExtModuleResource
import chisel3.util.experimental.BoringUtils
import circt.stage.ChiselStage
import firrtl.annotations.MemoryLoadFileType
import org.scalatest.flatspec.AnyFlatSpec
import org.scalatest.matchers.should.Matchers
import vta.DefaultPynqConfig
import vta.interface.axi.AXILiteClient
import vta.parsers.DramJsonParser.parseJsonMemoryInitFile
import vta.parsers.DramJsonParser.parseMemorySections
import vta.test.AxiFullSimUtils
import vta.test.AxiLiteSimUtils
import vta.test.MultiMemAxiClient
import vta.util.MemoryConfig
import vta.util.MemoryInitializer
import vta.util.SimulationUtils._
import vta.util.SimulationUtils.verilatorWithWaveDump
import vta.util.config.Parameters
import vta.test.VTAShellTest

class VTAShellSpec
    extends AnyFlatSpec
    with Matchers
    with ChiselSim
    with VTAShellTest {
  behavior of "VTAShell"

  implicit val hasWaveDumpVerilator: HasSimulator = verilatorWithWaveDump

  it should "run the full vta on a sample operation from resources" in {

    val dramInitJson =
      parseJsonMemoryInitFile(
        getClass.getClassLoader
          .getResource("examples_shell/dram_state.json")
          .getPath()
      )
    val content = parseMemorySections(dramInitJson)

    MemoryInitializer.exportHexFiles(
      content,
      os.pwd / "generatedResources" / "sample"
    )
    val memoryConfigs = parseMemorySections(dramInitJson)
      .map { case (a, (b, c)) =>
        MemoryConfig(
          name = a,
          path =
            (os.pwd / "generatedResources" / "sample" / (a + ".mem")).toString,
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
          m.copy(logging =
            true
          ) // enable the logging of outputs (FIXME: make a flag instead ? or pass a logfile path)
        case m: MemoryConfig => m
      }

    runVtaTestWithInitializedMem(
      memoryConfigs,
      timeout = 10000,
      waves = true
    )

  }
  it should "run the full vta on gemm_16x16 operation" in {

    val dramInitJson =
      parseJsonMemoryInitFile(
        (os.pwd / "examples_shell" / "gemm_16x16" / "dram_state.json").toString
      )
    val content = parseMemorySections(dramInitJson)

    MemoryInitializer.exportHexFiles(
      content,
      os.pwd / "generatedResources" / "gemm_16x16"
    )
    val memoryConfigs = parseMemorySections(dramInitJson)
      .map { case (a, (b, c)) =>
        MemoryConfig(
          name = a,
          path =
            (os.pwd / "generatedResources" / "gemm_16x16" / (a + ".mem")).toString,
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
          m.copy(logging =
            true
          ) // enable the logging of outputs (FIXME: make a flag instead ? or pass a logfile path)
        case m: MemoryConfig => m
      }

    runVtaTestWithInitializedMem(
      memoryConfigs,
      timeout = 10000,
      waves = true
    )

  }

  it should "export VTA in CHIRRTL" in {
    implicit val parameters: Parameters = new DefaultPynqConfig

    ChiselStage.emitCHIRRTLFile(new VTAShell, Array(""))
  }

}
