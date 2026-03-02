package vta.util

import org.scalatest.flatspec.AnyFlatSpec
import org.scalatest.matchers.should.Matchers

class MemoryInitializerTest extends AnyFlatSpec with Matchers {
  "MemoryInitializer" should "read binary as hex strings" in {
    val paths = os
      .list(os.pwd / "examples_shell" / "gemm_16x16")
      .filter(_.ext.matches("bin"))
      .map(s => s.last -> s.toString())
      .toMap
    val hexSeq = MemoryInitializer.getHexFromBinaryFiles(paths)
    print(hexSeq("instructions.bin"))
    hexSeq.foreach { l =>
      l._2.foreach(_.length() shouldBe 8)
    }

  }
}
