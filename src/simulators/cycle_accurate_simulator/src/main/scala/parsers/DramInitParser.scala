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

  /** Parse a `metadata<suffix>.csv` file. Each line is `type,rows,columns`
    * (written by main_vta_compiler.py). Only the `BS` (block size + full-matrix
    * flag) and `C` (output matrix dimensions) rows are needed to size the OUT
    * region.
    */
  def parseMetadata(path: String): LayerMetadata = {
    val src = Source.fromFile(path)
    val rows =
      try {
        src
          .getLines()
          .map(_.split(","))
          .collect { case Array(t, r, c) => t.trim -> (r.trim, c.trim) }
          .toMap
      } finally src.close()
    val (bsSquare, bsBlock) = rows("BS")
    val (cRows, cCols) = rows("C")
    LayerMetadata(
      isSquare = bsSquare.toBoolean,
      blockSize = bsBlock.toInt,
      outRows = cRows.toInt,
      outCols = cCols.toInt
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

  /** Convert a byte array into one hex string per `bytesPerWord`-byte group.
    *
    * Each output string has exactly `2 * bytesPerWord` characters and is
    * written MSB-first so it reads as a single unsigned integer for
    * `$readmemh`.
    *
    * For `littleEndian` (the VTA case), file byte `i` of a group must occupy
    * bits `[i*8 +: 8]` of the word, so a final short group keeps its real bytes
    * in the LOW positions and zero-fills the HIGH (MSB) bytes. The padding must
    * therefore be applied AFTER reversing the group, never before: prepending
    * zeros then reversing would push the real bytes into the high half of the
    * word and zero the low half. That bug silently corrupted the last 64-bit
    * word of any file whose length is not a multiple of `bytesPerWord` -
    * notably UOP regions with an odd uop count (4 B/uop), whose final uop
    * became a zero uop and wrecked the last GEMM/ALU iteration (last output
    * row).
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
