package vta.util

import org.scalatest.flatspec.AnyFlatSpec
import org.scalatest.matchers.should.Matchers
import vta.parsers.DramInitParser
import vta.util.BinaryReader.DataType._

class MemoryInitializerTest extends AnyFlatSpec with Matchers {
  "MemoryInitializer" should "read binary as hex strings" ignore {
    val paths = Map(
      // "ACC" -> "examples_compute/16x16/accumulator.bin",
      "INP" -> (INSN, "examples_compute/16x16/input.bin"),
      "INSN" -> (WGT, "examples_compute/16x16/instructions.bin")
    )
    val hexSeq = DramInitParser.getHexFromBinaryFiles(paths)
    MemoryInitializer.exportHexToMemFiles(
      hexSeq.view.mapValues(_._1).toMap,
      os.pwd / "build" / "memTest"
    )

  }
}
