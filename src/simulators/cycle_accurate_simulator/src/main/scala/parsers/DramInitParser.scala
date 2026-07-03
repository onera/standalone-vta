package vta.parsers

import chisel3._
import com.fasterxml.jackson.databind.ObjectMapper
import com.fasterxml.jackson.module.scala.DefaultScalaModule
import vta.models.DataType._
import vta.models.MemoryConfig
import vta.util.MemoryInitializer.exportHexToMemFile

import java.io.{BufferedInputStream, FileInputStream}
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

  /** Geometry of a layer's store/output matrix, read from a compiler
    * `metadata<suffix>.csv`. `isSquare`/`blockSize` come from the `BS` row,
    * `outRows`/`outCols` from the (unpadded) `C` row.
    */
  case class LayerMetadata(
      isSquare: Boolean,
      blockSize: Int,
      outRows: Int,
      outCols: Int
  )

  /** Parse a `metadata<suffix>.csv` for the BS (block size) and C (output dims
    * + full-matrix flag) rows. Accepts the new 4-column format (header row,
    * `type,rows,cols,square`) and the old 3-column `BS = type,square,block`.
    */
  def parseMetadata(path: String): LayerMetadata = {
    val src = Source.fromFile(path)
    // Key on column 0; the header and extra `square` column fall out as unused keys.
    val rows =
      try {
        src
          .getLines()
          .map(_.split(",").map(_.trim))
          .collect { case arr if arr.length >= 3 => arr(0) -> arr }
          .toMap
      } finally src.close()
    val bs = rows("BS")
    val c = rows("C")
    val (isSquare, blockSize) =
      if (bs.length >= 4)
        (c(3).toBoolean, bs(1).toInt) // new: square per-row, block in col1
      else
        (bs(1).toBoolean, bs(2).toInt) // old: square in BS col1, block in col2
    LayerMetadata(
      isSquare = isSquare,
      blockSize = blockSize,
      outRows = c(1).toInt,
      outCols = c(2).toInt
    )
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

  def fileBin2hex(
      fileIn: String,
      dirOut: os.Path,
      dt: DataTypeValue,
  ) = {
    if (fileIn.trim.isEmpty) {
      0
    } else {
      val bis = new BufferedInputStream(new FileInputStream(fileIn))
      val size = bis.available()
      try {
        val hexIt = Iterator
          .continually(readUpToNBytes(bis, 8))
          .takeWhile(_.nonEmpty)
          .map(bin2hexIt(_, bytesPerWord = 8, littleEndian = true))

        exportHexToMemFile(dt.name, hexIt, dirOut)
      } finally bis.close()
      size
    }
  }
  def bin2hexIt(
      bytes: Array[Byte],
      bytesPerWord: Int = 8,
      littleEndian: Boolean = false
  ): String = {
    require(
      bytesPerWord > 0,
      s"bytesPerWord must be positive, got $bytesPerWord"
    )
    val pad = Array.fill[Byte](bytesPerWord - bytes.length)(0)
    val ordered =
      if (littleEndian) pad ++ bytes.reverse
      else pad ++ bytes
    ordered.iterator.map(b => f"${b & 0xff}%02x").mkString
  }

  /** Read up to `n` bytes from `in`, returning exactly that many unless EOF is
    * reached first. An empty array signals EOF. Java 1.8 compatible replacement
    * for `InputStream.readNBytes(int)` (added in Java 9).
    */
  def readUpToNBytes(in: java.io.InputStream, n: Int): Array[Byte] = {
    val buf = new Array[Byte](n)
    var off = 0
    var r = 0
    while (off < n && { r = in.read(buf, off, n - off); r } != -1) off += r
    if (off == n) buf
    else java.util.Arrays.copyOf(buf, off)
  }

  /** Convert a byte array into one hex string per `bytesPerWord`-byte group.
    *
    * Each output string has exactly `2 * bytesPerWord` characters and is
    * written MSB-first so it reads as a single unsigned integer for
    * `$readmemh`.
    */
  def bin2hex(
      bytes: Array[Byte],
      bytesPerWord: Int = 8,
      littleEndian: Boolean = false
  ): Array[String] = {
    require(
      bytesPerWord > 0,
      s"bytesPerWord must be positive, got $bytesPerWord"
    )
    bytes
      .grouped(bytesPerWord)
      .map { g =>
        val pad = Array.fill[Byte](bytesPerWord - g.length)(0)
        val ordered =
          if (littleEndian) pad ++ g.reverse
          else pad ++ g
        ordered.iterator.map(b => f"${b & 0xff}%02x").mkString
      }
      .toArray
  }
}
