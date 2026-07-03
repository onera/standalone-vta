package vta.parsers

import vta.models.CompilerOutputModel.LayerMetadata

import scala.io.Source

/** Elaboration-time builder that turns a `compiler_output` directory into the
  * DRAM `MemoryConfig` list and the per-layer launch table consumed by both the
  * Scala multilayer spec and the synthesizable VtaHostDriver ROM.
  *
  * The relocation/layout strategy places each layer's regions at csvBase +
  * RELO_L (RELO_L = layerIndex * reloStride) so the VTA's
  * `baddr | (offset<<shift)` address math reduces to baddr + offset with no
  * cross-layer overlap.
  */
object CompilerOutputParser {

  /** One row of memory_addresses<layer>.csv: NAME,0xBASE,0xSIZE_BYTES. */
  case class MemoryRegion(name: String, base: Long, sizeBytes: Long)

 def parseAddressesCsv(
      compilerOutDir: String,
      layer: String
  ): Seq[MemoryRegion] = {
    val path = s"$compilerOutDir/memory_addresses$layer.csv"
    val src = Source.fromFile(path)
    try {
      src
        .getLines()
        .toList
        .map(_.split(",").map(_.trim))
        // Skip the header row and blanks: a data row's address column is hex.
        .filter(parts =>
          parts.length >= 2 && parts(1)
            .stripPrefix("0x")
            .matches("[0-9a-fA-F]+")
        )
        .map { parts =>
          require(
            parts.length >= 3,
            s"unexpected csv line in $path: ${parts.mkString(",")}"
          )
          MemoryRegion(
            name = parts(0),
            base = java.lang.Long.parseLong(parts(1).stripPrefix("0x"), 16),
            sizeBytes = java.lang.Long.parseLong(parts(2).stripPrefix("0x"), 16)
          )
        }
    } finally src.close()
  }


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


  private val insnBytes = 16

  /** Instruction count from actual .bin file size.
    */
  def insnCountFromFile(binPath: String, csvSize: Long): Long = {
    val p = os.Path(binPath, os.pwd)
    if (os.exists(p)) {
      val fileBytes = os.size(p)
      if (fileBytes % insnBytes != 0)
        println(
          s"WARNING: $binPath size $fileBytes not a multiple of $insnBytes"
        )
      fileBytes / insnBytes
    } else {
      println(s"WARNING: $binPath not found - falling back to CSV region size")
      csvSize / insnBytes
    }
  }
}
