package cli

import chisel3.simulator.HasSimulator
import chisel3.testing.HasTestingDirectory
import vta.exporters.MemHexExporter.exportHexFiles
import vta.models.MemoryConfig
import vta.parsers.DramInitParser.{
  getMemoryConfigurations,
  parseJsonMemoryInitFile,
  parseMemorySections
}
import vta.test.{TestBenchLayout, VTAShellTest}
import vta.util.SimulationUtils.{EnableMemInitVerilog, verilatorWithWaveDump}

import java.nio.file.{Path, Paths}

// FIXME: simple app, needs refinement
object VTAShellSimulator extends App with VTAShellTest {

  require(args.size >= 1)
  val dramInit = parseJsonMemoryInitFile(args.head)

  exportHexFiles(parseMemorySections(dramInit), os.pwd / "build" / "mem")

  implicit val simulator: HasSimulator = verilatorWithWaveDump
  implicit val enableMemoryInit: svsim.CommonSettingsModifications =
    EnableMemInitVerilog

  implicit val hasTestingDirectory: HasTestingDirectory = if (args.size >= 2) {
    new HasTestingDirectory {

      override def getDirectory: Path = {

        Paths.get(args(1))
      }

    }
  } else HasTestingDirectory.default
  runVtaTestWithInitializedMem(
    getMemoryConfigurations(args.head).map {
      case m: MemoryConfig if m.name.matches("OUT") => m.copy(logging = true)
      case m: MemoryConfig                          => m
    },
    1000,
    true
  )
}

/** Main simulator application.
  */
object VTAShellSimBinary extends App with VTAShellTest {

  require(args.size >= 1)
  val suffix = if (args.size >= 2) {
    args(1)
  } else ""

  val path = args.head

  val output = os.pwd / "build" / "mem-bin"

  val (memoryConfigs, _) = TestBenchLayout.build(
    compilerOutDir = path,
    layers = Seq(suffix),
    reloStride = 0,
    memOutDir = output
  )

  implicit val simulatorWithFst: HasSimulator = verilatorWithWaveDump
  implicit val enableMemoryInit: svsim.CommonSettingsModifications =
    EnableMemInitVerilog

  runVtaTestWithInitializedMem(memoryConfigs, timeout = 1000000, waves = true)
}
