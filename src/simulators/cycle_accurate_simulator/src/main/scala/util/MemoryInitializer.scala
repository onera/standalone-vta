package vta.util

import chisel3._
import java.io.File

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

  def exportHexToMemFiles(
      content: Map[String, Array[String]],
      file: os.Path
  ): Unit = {
    content.foreach { case (name, values) =>

      require(values.forall { l =>
        !values.exists(s => s.size != l.size)
      })
      os.write.over(
        file / (name + ".mem"),
        values.mkString("\n"),
        createFolders = true
      )
    }
  }
}
