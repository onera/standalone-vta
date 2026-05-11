package vta.parsers

import chisel3._
import com.fasterxml.jackson.databind.ObjectMapper
import com.fasterxml.jackson.module.scala.DefaultScalaModule
import vta.util.BinaryReader
import vta.util.MemoryConfig

import scala.io.Source
import chisel3.simulator.PeekPokeAPI.TestableEnum

object DramInitParser {

  def parseJsonMemoryInitFile(
      file: String
  ): Map[String, Object] = {
    val bufferedSource =
      Source.fromFile(
        file
      )
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

  def parseMemorySection(name: String, map: Map[String, Object]) = {
    val address = map(name) match {
      case m: Map[String, String] => m("PhysicalAddr").toInt
    }
    val values = map(name) match {
      case m: Map[String, Object] =>
        m("values") match {
          case l: List[String] => l
        }
    }
    (address, values)
  }

  def parseMemorySections(map: Map[String, Object]) = map.map { p =>
    val address = p._2 match {
      case m: Map[String, String] => {
        val s = m("PhysicalAddr")
        ("x" + s).U((s.size * 4).W).litValue.toInt
      }
    }
    val values = p._2 match {
      case m: Map[String, Object] =>
        m("values") match {
          case l: List[String] => l.map { s => ("x" + s).U((s.size * 4).W) }
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

  def getHexFromBinaryFiles(
      files: Map[String, (BinaryReader.DataType.DataTypeValue, String)],
      fromResources: Boolean = true
  ) = {
    files.map { s =>
      val bytes = BinaryReader.readBinaryFile(s._2._2, fromResources).get
      val size = bytes.size
      s._1 -> (
        bin2hex(bytes, 8)
          .map(_.reverse)
          // .grouped(4) // groups by 32 bits
          // .foldLeft(Array.empty[Array[String]]) { (arr, word32) =>
          //   arr :+ bin2hex(word32, 4)
          // }
          // .grouped(2)
          // .flatMap(_.reverse) // invert endianness for 32 bits word
          // .map(_.reduce(_ ++ _))
          // // .map(g => g.map(String.format("%02x", _)).reduce(_ + _))
          .toArray,
        size
      )
    }.toMap
  }

  def bin2hex(bytes: Array[Byte], nbBytes: Int = 8) = {
    val hex = bytes.grouped(nbBytes).map { g =>
      val string = (if (g.size == nbBytes) g
                    else Array.fill[Byte](nbBytes - g.size)(0) ++ g)
        .map(b => String.format("%02x", b).toString)
        .reduce(_ ++ _)

      if (g.size == nbBytes) string
      else
        string.padTo(nbBytes, '0')
      string

    }
    hex.toArray
  }
}
