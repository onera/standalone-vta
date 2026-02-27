package vta.shell

import chisel3._

object MemoryInitializer {
  def exportHexFiles(
      content: Map[String, (Int, List[UInt])],
      file: os.Path
  ): Unit = {
    content.foreach { case (name, (_, values)) =>

      os.write.over(
        file / (name + ".hex"),
        values
          .map(uint => {
            val bits = uint.getWidth
            val bytes = bits / 4
            val v = uint.litValue.toString(16)

            val str = Array.fill(bytes - v.size)("0").mkString + v
            // val s = f"$v%0x"
            str
          })
          .mkString("\n"),
        createFolders = true
      )
    }
  }
}
