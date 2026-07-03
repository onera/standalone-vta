package cli

import chisel3.simulator.HasSimulator
import chisel3.testing.HasTestingDirectory
import vta.models.DataType._
import vta.models.MemoryConfig
import vta.parsers.CompilerOutputParser.parseMetadata
import vta.parsers.DramInitParser
import vta.parsers.DramInitParser.{
  getMemoryConfigurations,
  parseJsonMemoryInitFile,
  parseMemorySections
}
import vta.test.VTAShellTest
import vta.util.MemoryInitializer.{exportHexFiles, exportHexToMemFiles}
import vta.util.SimulationUtils.{EnableMemInitVerilog, verilatorWithWaveDump}

import java.io.File
import java.nio.file.{Path, Paths}
import scala.io.Source

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
    (OUT, ""),
    (ACC, path + s"/accumulator${suffix}.bin"),
    (INSN, path + s"/instructions${suffix}.bin")
  )
  val hex =
    DramInitParser.getHexFromBinaryFiles(
      files,
      false
    )
  val memFiles = exportHexToMemFiles(
    hex.map(p => (p._1.name, p._2._1)),
    output
  )

  implicit val simulatorWithFst: HasSimulator = verilatorWithWaveDump
  implicit val enableMemoryInit: svsim.CommonSettingsModifications =
    EnableMemInitVerilog

  // The OUT region must be sized for *this* layer's store output. out_init.bin
  // is shared across layers (it only reflects the last-compiled one), so size
  // OUT from the layer metadata instead: the output element count, padded the
  // same way the compiler pads it, times the configured OUT element width.
  val outElemBytes = {
    val configFile = System.getProperty("vta.config.file", "vta_config.json")
    val fromResources =
      System.getProperty("vta.config.fromResources", "false").toBoolean
    vta.parsers.BinaryReader
      .computeJSONFile(configFile, fromResources)("LOG_OUT_WIDTH") / 8
  }
  val metadataFile = new File(path + s"/metadata${suffix}.csv")
  val outWords64 = if (metadataFile.isFile()) {

    DramInitParser.outRegionWords64(
      parseMetadata(path + s"/metadata${suffix}.csv"),
      outElemBytes
    )
  } else 1000
  val memoryConfigs = files
    .map(e =>
      MemoryConfig(
        name = e._1.name,
        path = memFiles(e._1.name).toString(),
        baseAddress =
          BigInt(addresses(e._1.name).split("x").last, 16).toInt,
        numberOfData = hex(e._1)._2,
        words64 = hex(e._1)._1.size
      )
    )
    .toSeq
    .map {
      case m: MemoryConfig if m.name.matches("OUT") =>
        m.copy(
          logging = true, // Enable logging the output
          words64 = outWords64 // size OUT for this layer, not out_init.bin
        )
      case m: MemoryConfig if m.name.matches("INSN") =>
        m.copy(numberOfData =
          m.words64 / 2
        ) // the instructions are 128 bits, so 1/2 instruction per word64
      case m: MemoryConfig => m
    }
  runVtaTestWithInitializedMem(memoryConfigs, timeout = 1000000, waves = true)
}
