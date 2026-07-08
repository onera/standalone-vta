package vta.parsers

import vta.models.CompilerOutputModel.MemoryRegion

/** Elaboration-time builder that turns a `compiler_output` directory into the
  * DRAM `MemoryConfig` list and the per-layer launch table consumed by both the
  * Scala multilayer spec and the synthesizable VtaHostDriver ROM.
  *
  * The relocation/layout strategy places each layer's regions at csvBase +
  * RELO_L (RELO_L = layerIndex * reloStride) so the VTA's
  * `baddr | (offset<<shift)` address math reduces to baddr + offset with no
  * cross-layer overlap.
  */
object MetadataParser {

  private val page = 0x1000L
  def alignPage(n: Long): Long = ((n + page - 1) / page) * page

  /** Parse CSV lines into regions, leaving `byteSize` at 0. Accepts both
    * 2-column (name, address) and 3-column (name, physical, logical) formats.
    * Skips the header and blank rows: a data row's address column (col 1) must
    * be hex.
    */
  def parseAddresses[T <: Iterable[String]](lines: T): Seq[MemoryRegion] =
    lines
      .map(_.split(",").map(_.trim))
      .filter(p =>
        p.length >= 2 && p(1).stripPrefix("0x").matches("[0-9a-fA-F]+")
      )
      .map { p =>
        MemoryRegion(
          name = p(0).toUpperCase,
          offset = BigInt(p(1).stripPrefix("0x"), 16).toLong,
          logicalAddr =
            if (p.length >= 3)
              Some(BigInt(p(2).stripPrefix("0x"), 16).toLong)
            else None,
          byteSize = 0L
        )
      }
      .toSeq

  /** Base-address map for the sim: buffer name -> 8-hex-digit physical address,
    * with `zero` buffers forced to all-zeros (the sim loads INP/WGT/OUT from
    * DRAM at base 0).
    */
  def baseAddrMap(
      regions: Seq[MemoryRegion],
      zero: Set[String] = Set("INP", "WGT", "OUT")
  ): Map[String, String] =
    regions
      .map(r =>
        r.name -> (if (zero.contains(r.name)) "00000000"
                   else f"${r.offset}%08X")
      )
      .toMap

  /** Read each layer's `memory_addresses<layer>.csv` and fill each region's
    * `byteSize` from the global physical layout: regions across all layers are
    * ordered by physical offset, each region's size is the gap to the next, and
    * the globally last region is the page-aligned size of its backing binary.
    * `lastBinFor(layer, name)` resolves that backing binary path (only
    * consulted for the globally last region); return `None` when there is no
    * backing file.
    *
    * @return
    *   per-layer regions, in `layers` order, with `byteSize` populated.
    */
  def loadLayerRegions(
      compilerOutDir: String,
      layers: Seq[String],
      lastBinFor: (String, String) => Option[String]
  ): Seq[(String, Seq[MemoryRegion])] = {
    val perLayer = layers.map { l =>
      l -> parseAddresses(
        os.read.lines(
          os.Path(s"$compilerOutDir/memory_addresses$l.csv", os.pwd)
        )
      )
    }
    val flatSorted =
      perLayer
        .flatMap { case (l, rs) => rs.map(r => (r.offset, l, r)) }
        .sortBy(_._1)
        .toVector
    val sizeByOffset: Map[Long, Long] = flatSorted.zipWithIndex.map {
      case ((off, layer, r), i) =>
        val size =
          if (i + 1 < flatSorted.length) flatSorted(i + 1)._1 - off
          else
            lastBinFor(layer, r.name)
              .map(p => os.Path(p, os.pwd))
              .filter(os.exists)
              .map(p => alignPage(os.size(p)))
              .getOrElse(0L)
        off -> size
    }.toMap
    perLayer.map { case (l, rs) =>
      l -> rs.map(r => r.copy(byteSize = sizeByOffset.getOrElse(r.offset, 0L)))
    }
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
