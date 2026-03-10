package vta.util

import org.scalatest.flatspec.AnyFlatSpec
import org.scalatest.matchers.should.Matchers
import vta.parsers.DramInitParser

class MemoryInitializerTest extends AnyFlatSpec with Matchers {
  "MemoryInitializer" should "read binary as hex strings" in {
    val paths = Map(
      // "ACC" -> "examples_compute/16x16/accumulator.bin",
      "INP" -> "examples_compute/16x16/input.bin",
      "INSN" -> "examples_compute/16x16/instructions.bin"
    )
    val hexSeq = DramInitParser.getHexFromBinaryFiles(paths)
    MemoryInitializer.exportHexToMemFiles(
      hexSeq,
      os.pwd / "build" / "memTest"
    )

  }
}
