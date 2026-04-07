package vta.shell
import chisel3._
import circt.stage.ChiselStage
import org.scalatest.matchers.should.Matchers
import vta.DefaultPynqConfig
import vta.parsers.DramInitParser.parseJsonMemoryInitFile
import vta.parsers.DramInitParser.parseMemorySections
import vta.test.VTAShellTest
import vta.util.MemoryConfig
import vta.util.MemoryInitializer
import vta.util.config.Parameters
import scala.util.Random
import unittest.AnyFlatSpecSim

class VTAShellSpec extends AnyFlatSpecSim with Matchers with VTAShellTest {
  behavior of "VTAShell"

  it should "run the full vta on random data" in {

    val dramInitJson =
      parseJsonMemoryInitFile(
        getClass.getClassLoader
          .getResource("examples_shell/dram_state.json")
          .getPath()
      )
    val defaultContent = parseMemorySections(dramInitJson)
    val content = defaultContent.collect {
      case ("INP" -> v) =>
        ("INP" -> (
          v._1,
          v._2.map(_ => Random.nextInt(Int.MaxValue / 2).U(32.W))
        ))
      case ("WGT" -> v) =>
        ("WGT" -> (
          v._1,
          v._2.map(_ => Random.nextInt(Int.MaxValue / 2).U(32.W))
        ))
      case ("ACC" -> v) =>
        ("ACC" -> (
          v._1,
          v._2.map(_ => Random.nextInt(Int.MaxValue / 2).U(32.W))
        ))
    }

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
      waves = true
    )

  }

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
      waves = true
    )

  }

  it should "export VTA in CHIRRTL" in {

    ChiselStage.emitCHIRRTLFile(
      new VTAShell,
      Array("-td", "build/circt/vta/")
    )
  }

}
