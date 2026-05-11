package vta.util

import org.scalatest.flatspec.AnyFlatSpec
import org.scalatest.matchers.should.Matchers
import vta.util.BinaryReader.DataType._
import vta.parsers.DramInitParser._
class MemoryInitializerTest extends AnyFlatSpec with Matchers {
  "MemoryInitializer" should "read binary as hex strings" ignore {
    val paths = Map(
      // "ACC" -> "examples_compute/16x16/accumulator.bin",
      INP -> "examples_compute/16x16/input.bin",
      INSN -> "examples_compute/16x16/instructions.bin"
    )
    val hexSeq = getHexFromBinaryFiles(paths)
    MemoryInitializer.exportHexToMemFiles(
      hexSeq.map(p => (p._1.getName(), p._2._1)).toMap,
      os.pwd / "build" / "memTest"
    )

  }
}
