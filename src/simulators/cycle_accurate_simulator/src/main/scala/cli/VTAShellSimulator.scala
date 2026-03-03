package cli

import vta.test.VTAShellTest
import vta.parsers.DramInitParser.parseJsonMemoryInitFile
import vta.parsers.DramInitParser.parseMemorySections
import vta.util.MemoryInitializer.exportHexFiles
import vta.parsers.DramInitParser.getMemoryConfigurations
import vta.util.MemoryConfig
import vta.util.SimulationUtils.verilatorWithWaveDump
import chisel3.testing.HasTestingDirectory
import java.nio.file.Path
import java.nio.file.Paths

// FIXME: simple app, needs refinement
object VTAShellSimulator extends App with VTAShellTest {

  require(args.size >= 1)
  val dramInit = parseJsonMemoryInitFile(args.head)

  exportHexFiles(parseMemorySections(dramInit), os.pwd / "generatedResources")

  implicit val simulator = verilatorWithWaveDump

  implicit val hasTestingDirectory = if (args.size >= 2) {
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
