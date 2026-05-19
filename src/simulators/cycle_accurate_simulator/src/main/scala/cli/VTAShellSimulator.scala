package cli

import chisel3.simulator.HasSimulator
import chisel3.testing.HasTestingDirectory
import vta.parsers.DramInitParser
import vta.parsers.DramInitParser.getMemoryConfigurations
import vta.parsers.DramInitParser.parseJsonMemoryInitFile
import vta.parsers.DramInitParser.parseMemorySections
import vta.test.VTAShellTest
import vta.util.MemoryConfig
import vta.util.MemoryInitializer.exportHexFiles
import vta.util.MemoryInitializer.exportHexToMemFiles
import vta.util.SimulationUtils.verilatorWithWaveDump
import vta.util.BinaryReader.DataType._

import java.nio.file.Path
import java.nio.file.Paths
import scala.io.Source

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

  require(args.size >= 1)
  val suffix = if (args.size >= 2) {
    args(1)
  }

  val path = args.head

  val memoryFile = Source.fromFile(path + s"/memory_addresses${suffix}.csv")
  val addresses = memoryFile
    .getLines()
    .map(_.split(","))
    .map(e => (e.head -> e(1)))
    .toMap
  memoryFile.close()
  val output = os.pwd / "build" / "mem-bin"

  val files = Map(
    (INP, path + s"/input${suffix}.bin"),
    (WGT, path + s"/weight${suffix}.bin"),
    (UOP, path + s"/uop${suffix}.bin"),
    (OUT, path + s"/out_init.bin"),
    (ACC, path + s"/accumulator${suffix}.bin"),
    (INSN, path + s"/instructions${suffix}.bin")
  )
  import DramInitParser._
  val hex =
    DramInitParser.getHexFromBinaryFiles(
      files,
      false
    )
  val memFiles = exportHexToMemFiles(
    hex.map(p => (p._1.getName(), p._2._1)),
    output
  )

  implicit val simulatorWithFst = verilatorWithWaveDump
  val memoryConfigs = files
    .map(e =>
      MemoryConfig(
        name = e._1.getName(),
        path = memFiles(e._1.getName()).toString(),
        baseAddress =
          BigInt(addresses(e._1.getName()).split("x").last, 16).toInt,
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
  runVtaTestWithInitializedMem(memoryConfigs, timeout = 1000000, waves = true)
}
