package vta.parsers

import chisel3._
import com.fasterxml.jackson.databind.ObjectMapper
import scala.io.Source
import com.fasterxml.jackson.module.scala.DefaultScalaModule
import vta.util.MemoryConfig

object DramJsonParser {

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
        path =
          (os.pwd / "generatedResources" / "sample" / (a + ".mem")).toString,
        baseAddress = b,
        initialSize = c.size,
        words64 = {
          val n = c.map(_.getWidth).sum
          if (n % 64 == 0) n / 64 else (n / 64) + 1
        }
      )
    }.toSeq
  }
}
