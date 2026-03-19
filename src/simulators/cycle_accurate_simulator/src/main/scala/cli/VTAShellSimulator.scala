package cli

import chisel3.testing.HasTestingDirectory
import vta.parsers.DramInitParser
import vta.parsers.DramInitParser.getMemoryConfigurations
import vta.parsers.DramInitParser.parseJsonMemoryInitFile
import vta.parsers.DramInitParser.parseMemorySections
import vta.test.VTAShellTest
import vta.util.BinaryReader
import vta.util.MemoryConfig
import vta.util.MemoryInitializer.exportHexFiles
import vta.util.MemoryInitializer.exportHexToMemFiles
import vta.util.SimulationUtils.verilatorWithWaveDump

import java.nio.file.Path
import java.nio.file.Paths

// FIXME: simple app, needs refinement
object VTAShellSimulator extends App with VTAShellTest {

  require(args.size >= 1)
  val dramInit = parseJsonMemoryInitFile(args.head)

  exportHexFiles(parseMemorySections(dramInit), os.pwd / "build" / "mem")

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

object VTAShellSimBinary extends App with VTAShellTest {

  val path = os.rel /
    "examples_compute" / "16x16"
  println((path / "memory_addresses.csv").toString())
  val file =
    getClass.getClassLoader.getResourceAsStream(
      (path / "memory_addresses.csv").toString()
    )

  val addresses = BinaryReader.readFile(
    (path / "memory_addresses.csv").toString(),
    true
  )
  val output = os.pwd / "build" / "mem-bin"

  val files = Map(
    "INP" -> path / "input.bin",
    "WGT" -> path / "weight.bin",
    "OUT" -> path / "uop.bin",
    "ACC" -> path / "accumulator.bin",
    "INSN" -> path / "instructions.bin"
  )
  val hex =
    DramInitParser.getHexFromBinaryFiles(
      files.view.mapValues(_.toString()).toMap,
      false
    )
  exportHexToMemFiles(
    hex,
    output
  )
}
