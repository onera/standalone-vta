package vta.parsers

import org.scalatest.flatspec.AnyFlatSpec
import org.scalatest.matchers.should.Matchers
import vta.util.MemoryInitializer.getHexFromBinaryFiles
import vta.parsers.DramInitParser.getHexFromBinary
import vta.util.BinaryReader

class DramInitParserTest extends AnyFlatSpec with Matchers {
  it should "read binary file and convert to hex 64" in {

    val file =
      getClass.getClassLoader.getResource(
        "examples_compute/16x16/input.bin"
      )

    val hexV1 = for {

      s <- getHexFromBinary(file.getPath())
    } yield {
      println(s.toSeq)
      require(s.size == 17)
    }

    // val hexV2 = getHexFromBinaryFiles(Map("INP" -> file.getPath()))
    // println(hexV2("INP").mkString("\n"))
  }
}
