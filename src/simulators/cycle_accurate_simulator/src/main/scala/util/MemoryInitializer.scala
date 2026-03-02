package vta.util

import chisel3._
import scala.io.Source
import java.io.File
import java.nio.file.Files
import java.nio.file.Path
import chisel3.simulator.PeekPokeAPI.TestableEnum

/** Utility case class for defining mock memories for simulation
  *
  * @param name
  *   the name of the memory
  * @param path
  *   initialization file
  * @param baseAddress
  *   base address of the memory
  * @param initialSize
  *   number of data (before resizing in 64 bits)
  * @param words64
  *   number of 64bits words
  * @param logfile
  *   an optional logfile to store the memory (written during simulation)
  */
case class MemoryConfig(
    name: String,
    path: String,
    baseAddress: Int,
    initialSize: Int,
    words64: Int,
    logging: Boolean = false
)
object MemoryInitializer {
  def exportHexFiles(
      content: Map[String, (Int, List[UInt])],
      file: os.Path,
      targetBytes: Int = 16
  ): Unit = {
    content.foreach { case (name, (_, values)) =>

      val hexStrings =
        values
          .map(uint => {
            val bits = uint.getWidth
            val bytes = bits / 4
            val v = uint.litValue.toString(16)

            val str = Array.fill(bytes - v.size)("0").mkString + v
            // val s = f"$v%0x"
            str
          })

      require(hexStrings.forall { l =>
        !hexStrings.exists(s => s.size != l.size)
      })
      val groupSize = targetBytes / (hexStrings.head.size)

      val reshapedHex = if (groupSize > 1) {
        hexStrings
          .grouped(groupSize)
          .map {
            case ls: List[String] if ls.size == groupSize =>
              ls.reduceLeft { _ + _ }
            case ls: List[String] if ls.size == 1 =>
              ls.head + Array.fill(targetBytes - ls.head.size)("0").mkString
          }
          .toList
      } else if (groupSize < 1) {
        hexStrings.flatMap(s => s.grouped(targetBytes).toList.reverse)
      } else {
        hexStrings
      }
      os.write.over(
        file / (name + ".mem"),
        reshapedHex.mkString("\n"),
        createFolders = true
      )
    }
  }
  def getHexFromBinaryFiles(files: Map[String, String]) = {
    files.map { s =>
      val bytes = Files.readAllBytes(Path.of(s._2))
      s._1 -> bin2hex(bytes)
    }.toMap
  }
  def bin2hex(bytes: Array[Byte], targetBytes: Int = 8) = {
    val hex = bytes.grouped(targetBytes).map { g =>
      val sb = new StringBuilder

      val string = (if (g.size == targetBytes) g
                    else g ++ Array.fill[Byte](targetBytes - g.size)(0))
        .map(b => String.format("%x", Byte.box(b)))
        .reduce(_.toString() + _.toString())

      if (g.size == targetBytes) string
      else
        string.padTo(targetBytes, '0')

    }
    hex.toSeq
  }
}
