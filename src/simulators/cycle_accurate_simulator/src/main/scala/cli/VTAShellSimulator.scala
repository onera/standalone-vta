package cli

import chisel3.simulator.HasSimulator
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
import vta.util.BinaryReader.DataType._

import java.nio.file.Path
import java.nio.file.Paths
import vta.core.CoreKey
import chisel3.Mem

// FIXME: simple app, needs refinement
object VTAShellSimulator extends App with VTAShellTest {

  require(args.size >= 1)
  val dramInit = parseJsonMemoryInitFile(args.head)

  exportHexFiles(parseMemorySections(dramInit), os.pwd / "build" / "mem")

  implicit val simulator: HasSimulator = verilatorWithWaveDump

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

object VTAShellSimBinary extends App with VTAShellTest {

  val path = os.pwd / "compiler_output"
  // val path = os.pwd / "src" / "test" / "resources" / "examples_compute/16x16"

  val addresses = os
    .read(path / "memory_addresses.csv")
    .split("\n")
    .map(_.split(","))
    .map(e => (e.head -> e(1)))
    .toMap
  val output = os.pwd / "build" / "mem-bin"

  val files = Map(
    "INP" -> (INSN, path / "input.bin"),
    "WGT" -> (WGT, path / "weight.bin"),
    "UOP" -> (UOP, path / "uop.bin"),
    "OUT" -> (OUT, path / "out_init.bin"),
    "ACC" -> (ACC, path / "accumulator.bin"),
    "INSN" -> (INSN, path / "instructions.bin")
  )
  val hex =
    DramInitParser.getHexFromBinaryFiles(
      files.view.mapValues(p => (p._1, p._2.toString())).toMap,
      false
    )
  val memFiles = exportHexToMemFiles(
    hex.view.mapValues(_._1).toMap,
    output
  )

  implicit val simulatorWithFst = verilatorWithWaveDump
  val memoryConfigs = files
    .map(e =>
      MemoryConfig(
        name = e._1,
        path = memFiles(e._1).toString(),
        baseAddress = BigInt(addresses(e._1).split("x").last, 16).toInt,
        numberOfData = hex(e._1)._2,
        words64 = hex(e._1)._1.size
      )
    )
    .toSeq
    .map {
      case m: MemoryConfig if m.name.matches("OUT") =>
        m.copy(logging = true) // Enable logging the output
      case m: MemoryConfig if m.name.matches("INSN") =>
        m.copy(numberOfData =
          m.words64 / 2
        ) // the instructions are 128 bits, so 1/2 instruction per word64
      case m: MemoryConfig => m
    }
  runVtaTestWithInitializedMem(memoryConfigs, waves = true)
}
