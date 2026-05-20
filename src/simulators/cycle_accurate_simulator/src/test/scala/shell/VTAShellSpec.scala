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
import scala.io.Source
import chisel3.simulator.stimulus.RunUntilFinished
import vta.test.VTAShellTestFull
import vta.util.SimulationUtils.EnableMemInitVerilog

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
}

class VTAShellBinSpec extends AnyFlatSpecSim with Matchers with VTAShellTest {
  behavior of "VTAShell"
  it should "run the full VTA on binary data" in {

    // implicit val simulatorWithWaves = verilatorWithWaveDump
    val path = "../../../compiler_output"
    // val path = os.pwd / "src" / "test" / "resources" / "examples_compute/16x16"

    val suffix = ""
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

    val offset = BigInt("0", 16).toInt
    val memoryConfigs = files
      .map(e =>
        MemoryConfig(
          name = e._1.getName(),
          path = memFiles(e._1.getName()).toString(),
          baseAddress = BigInt(
            addresses(e._1.getName()).split("x").last,
            16
          ).toInt + offset,
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

    implicit val enableMemoryInit = EnableMemInitVerilog
    simulate(
      new VTAShellTestFull(memoryConfigs),
      firtoolOpts = Array("--disable-all-randomization")
    ) { vta =>
      implicit val clock = vta.clock
      implicit val axiLiteClient = vta.io.host
      vta.io.host.b.ready.poke(true.B)

      writeInstructionBaseAddress(
        memoryConfigs.find(_.name.matches("INSN")).get.baseAddress
      )
      writeUopBaseAddress(offset)
      writeInputBaseAddress(offset)
      writeWeightBaseAddress(offset)
      writeAccBaseAddress(offset)
      writeOutBaseAddress(offset)
      // Configure instruction size

      writeInstructionCount(
        memoryConfigs.find(_.name.matches("INSN")).get.numberOfData
      )

      // launch the processing of VTA
      launchVTA()

      // step clock until the computation is over
      // clock.step(timeout)
      RunUntilFinished.module(1000)
    }
    // runVtaTestWithInitializedMem(
    //   content = memoryConfigs,
    //   timeout = 10000,
    //   waves = false
    // )
  }
}
