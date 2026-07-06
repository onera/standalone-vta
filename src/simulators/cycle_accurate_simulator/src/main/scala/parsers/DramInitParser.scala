package vta.parsers

import chisel3._
import com.fasterxml.jackson.databind.ObjectMapper
import com.fasterxml.jackson.module.scala.DefaultScalaModule
import vta.models.CompilerOutputModel.LayerMetadata
import vta.models.DataType._
import vta.models.MemoryConfig
import vta.util.ByteCodec.bin2hex

import scala.io.Source

import BinaryReader.readBinaryFile

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

  /** Read each binary file and convert it to one hex string per 64-bit memory
    * word, ready to be consumed by `$readmemh`.
    *
    * Source files are interpreted as little-endian byte streams, so the byte
    * order is swapped within each 64-bit word: byte `i` of the file lands in
    * bits `[i*8+7 : i*8]` of the memory word.
    *
    * @return
    *   for each data type: (hex-strings array, raw byte count)
    */
  def getHexFromBinaryFiles(
      files: Map[DataTypeValue, String],
      fromResources: Boolean = true
  ): Map[DataTypeValue, (Array[String], Int)] = {
    files.map { case (dt, path) =>
      if (path.trim.isEmpty) {
        // No init file (e.g. OUT is a pure write target): start empty/zeroed.
        dt -> (Array.empty[String], 0)
      } else {
        val bytes = readBinaryFile(path, fromResources).get
        dt -> (
          bin2hex(bytes, bytesPerWord = 8, littleEndian = true),
          bytes.size
        )
      }
    }.toMap
  }

}
