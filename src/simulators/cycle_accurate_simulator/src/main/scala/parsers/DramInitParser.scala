package vta.parsers

import chisel3._
import com.fasterxml.jackson.databind.ObjectMapper
import com.fasterxml.jackson.module.scala.DefaultScalaModule
import vta.util.BinaryReader.DataType._
import vta.util.MemoryConfig

import scala.io.Source
import vta.util.BinaryReader.readBinaryFile

object DramInitParser {

  implicit class DataTypeHasName(datatype: DataTypeValue) {

    def getName(): String =
      datatype match {
        case INSN => "INSN"
        case UOP  => "UOP"
        case OUT  => "OUT"
        case INP  => "INP"
        case ACC  => "ACC"
        case WGT  => "WGT"
      }
  }

  def parseJsonMemoryInitFile(
      file: String
  ): Map[String, Object] = {
    val bufferedSource = Source.fromFile(file)
    val mapper = new ObjectMapper()
    mapper.registerModule(DefaultScalaModule)
    val dramInitJson =
      mapper.readValue(
        bufferedSource.reader(),
        classOf[Map[String, Map[String, Object]]]
      )
    bufferedSource.close
    dramInitJson.head._2
  }

  def parseMemorySections(map: Map[String, Object]) = map.map { p =>
    val address = p._2 match {
      case m: Map[String, String] @unchecked => {
        val s = m("PhysicalAddr")
        ("x" + s).U((s.size * 4).W).litValue.toInt
      }
    }
    val values = p._2 match {
      case m: Map[String, Object] @unchecked =>
        m("values") match {
          case l: List[String] @unchecked =>
            l.map { s => ("x" + s).U((s.size * 4).W) }
        }
    }
    (p._1 -> (address, values))
  }

  def getMemoryConfigurations(file: String) = {
    val json = parseJsonMemoryInitFile(file)
    val content = parseMemorySections(json)
    content.map { case (a, (b, c)) =>
      MemoryConfig(
        name = a,
        path = (os.pwd / "build" / "mem" / (a + ".mem")).toString,
        baseAddress = b,
        numberOfData = c.size,
        words64 = {
          val n = c.map(_.getWidth).sum
          if (n % 64 == 0) n / 64 else (n / 64) + 1
        }
      )
    }.toSeq
  }

  /** Read each binary file and convert it to one hex string per 64-bit memory
    * word, ready to be consumed by `$readmemh`.
    *
    * Source files are interpreted as little-endian byte streams, so the byte
    * order is swapped within each 64-bit word: byte `i` of the file lands in
    * bits `[i*8+7 : i*8]` of the memory word.
    *
    * @return for each data type: (hex-strings array, raw byte count)
    */
  def getHexFromBinaryFiles(
      files: Map[DataTypeValue, String],
      fromResources: Boolean = true
  ): Map[DataTypeValue, (Array[String], Int)] = {
    files.map { case (dt, path) =>
      val bytes = readBinaryFile(path, fromResources).get
      dt -> (bin2hex(bytes, bytesPerWord = 8, littleEndian = true), bytes.size)
    }.toMap
  }

  /** Convert a byte array into one hex string per `bytesPerWord`-byte group.
    *
    * Each output string has exactly `2 * bytesPerWord` characters. A final
    * short group is zero-padded on the high-order side. When `littleEndian`
    * is true, each group's bytes are reversed before formatting so the result
    * reads MSB-first as a single unsigned integer.
    */
  def bin2hex(
      bytes: Array[Byte],
      bytesPerWord: Int = 8,
      littleEndian: Boolean = false
  ): Array[String] = {
    require(bytesPerWord > 0, s"bytesPerWord must be positive, got $bytesPerWord")
    bytes.grouped(bytesPerWord).map { g =>
      val padded =
        if (g.length == bytesPerWord) g
        else Array.fill[Byte](bytesPerWord - g.length)(0) ++ g
      val ordered = if (littleEndian) padded.reverse else padded
      ordered.iterator.map(b => f"${b & 0xff}%02x").mkString
    }.toArray
  }
}
