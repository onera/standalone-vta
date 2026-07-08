package vta.parsers

import chisel3._
import com.fasterxml.jackson.databind.ObjectMapper
import com.fasterxml.jackson.module.scala.DefaultScalaModule
import vta.models.CompilerOutputModel.LayerMetadata
import vta.models.MemoryConfig

import scala.io.Source

object DramInitParser {

  def parseJsonMemoryInitFile(
    file: String,
    fromResources: Boolean = false
  ): Map[String, Object] = {
    val bufferedSource =
      if (!fromResources) Source.fromFile(file)
      else
        Source.fromResource(file)
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

  /** Number of 64-bit DRAM words the store output (OUT region) occupies.
    *
    * Mirrors the compiler's `matrix_padding` (data_definition.py): the output
    * matrix columns are padded up to a multiple of `blockSize`, and the rows
    * are too when the full matrix is stored (`BS == True`). The padded element
    * count is scaled by the output element width (`outElemBytes`) and packed
    * into `bytesPerWord64`-byte memory words.
    *
    * This is what the OUT memory must hold; sizing it from the shared
    * `out_init.bin` placeholder instead undersizes the region (it reflects only
    * the last-compiled layer), which both drops written data and trips the
    * MultiMemAxiClient bounds assertion.
    */
  def outRegionWords64(
    meta: LayerMetadata,
    outElemBytes: Int,
    bytesPerWord64: Int = 8
  ): Int = {
    def ceilToBlock(n: Int): Int =
      ((n - 1) / meta.blockSize + 1) * meta.blockSize
    val paddedRows =
      if (meta.isSquare) ceilToBlock(meta.outRows) else meta.outRows
    val paddedCols = ceilToBlock(meta.outCols)
    val totalBytes = paddedRows * paddedCols * outElemBytes
    (totalBytes + bytesPerWord64 - 1) / bytesPerWord64
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

}
