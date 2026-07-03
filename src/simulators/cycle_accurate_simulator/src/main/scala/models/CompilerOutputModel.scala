package vta.models

object CompilerOutputModel {

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

  /** One row of `memory_addresses<layer>.csv`.
    *
    * @param name
    *   buffer type (INP/WGT/ACC/OUT/UOP/INSN), upper-cased
    * @param offset
    *   physical address (col 1), relative to the DDR base
    * @param logicalAddr
    *   col 2 = compiler logical address (offset / elemSize);
    * @param byteSize
    *   real allocated size in bytes; 0 until filled by [[parseLayers]] from the
    *   global physical layout
    */
  case class Region(
      name: String,
      offset: Long,
      logicalAddr: Long,
      byteSize: Long
  )

  /** One layer-details row of dependency.csv. */
  case class LayerDependency(
      processor: String,
      reshapeInfo: String,
      offsetA: Int,
      scaleA: Double,
      offsetB: Int,
      scaleB: Double,
      offsetU: Int,
      scaleU: Double,
      offsetV: Int,
      scaleV: Double,
      tensorCh: Int,
      tensorH: Int,
      tensorW: Int,
      kh: Int,
      kw: Int,
      sh: Int,
      sw: Int,
      pad: (Int, Int, Int, Int),
      outCh: Int,
      outH: Int,
      outW: Int,
      offsetC: Int,
      scaleC: Double,
      scale: Double,
      nbInp: Int,
      deps: Seq[String]
  )

  case class DependencyInfo(
      executionOrder: Seq[(Int, String, String)],
      layers: Map[String, LayerDependency],
      imageH: Int,
      imageW: Int,
      outputLayer: String
  )
}
