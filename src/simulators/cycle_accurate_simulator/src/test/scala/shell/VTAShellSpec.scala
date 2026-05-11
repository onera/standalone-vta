package vta.shell
import chisel3._
import org.scalatest.matchers.should.Matchers
import vta.parsers.DramInitParser.parseJsonMemoryInitFile
import vta.parsers.DramInitParser.parseMemorySections
import vta.test.VTAShellTest
import vta.util.MemoryConfig
import vta.util.MemoryInitializer
import vta.util.AnyFlatSpecSim
import vta.util.SimulationUtils.verilatorWithWaveDump
import vta.parsers.DramInitParser
import vta.util.BinaryReader.DataType._
import chisel3.simulator.HasSimulator

class VTAShellSpec extends AnyFlatSpecSim with Matchers with VTAShellTest {
  behavior of "VTAShell"

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
        numberOfData = values.size,
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

  it should "run the full vta on a sample operation from resources" in {

    runVtaTestWithInitializedMem(
      memoryConfigs,
      timeout = 10000,
      waves = false
    )

  }

  it should "run the full vta twice" in {

    runVtaTestWithInitializedMemTwice(
      memoryConfigs,
      timeout = 10000,
      waves = false
    )

  }

  it should "run the full VTA on binary data" in {

    implicit val simulatorWithWaves = verilatorWithWaveDump
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
      INSN -> path / "input.bin",
      WGT -> path / "weight.bin",
      UOP -> path / "uop.bin",
      OUT -> path / "out_init.bin",
      ACC -> path / "accumulator.bin",
      INSN -> path / "instructions.bin"
    )
    val hex =
      DramInitParser.getHexFromBinaryFiles(
        files.view.mapValues(_.toString()).toMap,
        false
      )
    import DramInitParser._
    val memFiles = MemoryInitializer.exportHexToMemFiles(
      hex.map(p => (p._1.getName(), p._2._1)),
      output
    )

    val memoryConfigs = files
      .map(e =>
        MemoryConfig(
          name = e._1.getName(),
          path = memFiles(e._1.getName()).toString(),
          baseAddress = {
            val s = addresses(e._1.getName())
            ("x" + s).U((s.size * 4).W).litValue.toInt
          },
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
    runVtaTestWithInitializedMem(
      content = memoryConfigs,
      timeout = 10000,
      waves = true
    )
  }
}
