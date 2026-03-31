package vta.shell
import chisel3.simulator.HasSimulator
import chisel3.simulator.scalatest.ChiselSim
import circt.stage.ChiselStage
import org.scalatest.flatspec.AnyFlatSpec
import org.scalatest.matchers.should.Matchers
import vta.DefaultPynqConfig
import vta.parsers.DramInitParser.parseJsonMemoryInitFile
import vta.parsers.DramInitParser.parseMemorySections
import vta.test.VTAShellTest
import vta.util.MemoryConfig
import vta.util.MemoryInitializer
import vta.util.SimulationUtils.verilatorWithWaveDump
import vta.util.config.Parameters

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
      os.pwd / "build" / "mem"
    )
    val memoryConfigs = parseMemorySections(dramInitJson)
      .map { case (name, (addr, values)) =>
        MemoryConfig(
          name = name,
          path = (os.pwd / "build" / "mem" / (name + ".mem")).toString,
          baseAddress = addr,
          initialSize = values.size,
          words64 = {
            val n = values.map(_.getWidth).sum
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
      waves = false
    )

  }

  it should "export VTA in CHIRRTL" in {
    implicit val parameters: Parameters = new DefaultPynqConfig

    ChiselStage.emitCHIRRTLFile(
      new VTAShell,
      Array("-td", "build/circt/vta/")
    )
  }

}
