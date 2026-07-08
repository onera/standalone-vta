package vta.test

import vta.models.{DataType, MemoryConfig}
import vta.parsers.MetadataParser.{insnCountFromFile, loadLayerRegions}
import vta.util.ByteCodec
import vta.util.ByteCodec.readUpToNBytes

import java.io.{BufferedInputStream, FileInputStream}

/** Elaboration-time builder that turns a `compiler_output` directory into the
  * DRAM `MemoryConfig` list and the per-layer launch table consumed by both the
  * Scala multilayer spec and the synthesizable VtaHostDriver ROM.
  *
  */
object TestBenchLayout {

  /** Per-layer launch parameters: VCR insn base, instruction count, relocation.
    */
  case class LaunchParams(insnBaddr: BigInt, insnCount: Int, relo: BigInt)

  /** Read a binary file, convert it to 64-bit hex words, and write a `.mem`
    * file under `dirOut`. The file is named after `outName` when given (callers
    * that need a per-region/per-layer file, e.g. CompilerOutputLayout), else
    * after the data-type name.
    *
    * @return
    *   the number of 64-bit hex words written (= number of lines in the `.mem`
    *   file), or 0 if `fileIn` is blank.
    */
  def fileBin2hex(
      fileIn: String,
      dirOut: os.Path,
      dt: DataType.DataTypeValue,
      outName: String = ""
  ): Int = {
    if (fileIn.trim.isEmpty) {
      0
    } else {
      val bis = new BufferedInputStream(new FileInputStream(fileIn))
      val size = bis.available()
      try {
        val hexIt = Iterator
          .continually(readUpToNBytes(bis, 8))
          .takeWhile(_.nonEmpty)
          .map(ByteCodec.bytesToHexWord(_, bytesPerWord = 8, littleEndian = true))

        val name = if (outName.nonEmpty) outName else dt.name
        os.write.over(dirOut / (name + ".mem"), hexIt.mkString("\n"))
      } finally bis.close()
      // Return word (line) count, not byte count, so callers that compare
      // this to os.read.lines(...).size get a consistent value.
      ((size + 7) / 8).toInt
    }
  }
  // Standard compiler binary for a region, used only to page-align the size of
  // the globally last region (see CompilerOutputParser.loadLayerRegions).
  private def lastBinFor(
      compilerOutDir: String
  ): (String, String) => Option[String] =
    (layer, name) =>
      name match {
        case "INSN" => Some(s"$compilerOutDir/instructions$layer.bin")
        case "UOP"  => Some(s"$compilerOutDir/uop$layer.bin")
        case "WGT"  => Some(s"$compilerOutDir/weight$layer.bin")
        case "ACC"  => Some(s"$compilerOutDir/accumulator$layer.bin")
        case "INP"  => Some(s"$compilerOutDir/input$layer.bin")
        case _      => None // OUT has no backing bin
      }

  private def fileFor(
      compilerOutDir: String,
      inpDir: String,
      layer: String,
      regionName: String,
      accFromDump: Boolean
  ): Option[String] =
    regionName match {
      case "INSN" => Some(s"$compilerOutDir/instructions$layer.bin")
      case "UOP"  => Some(s"$compilerOutDir/uop$layer.bin")
      // For int32/ALU layers (e.g. MaxPool: an ACC region but no INP) the layer's
      // INPUT lives in ACC, not a static bias - load it from the fsim/vsim dump
      // (input$layer.bin) too. Conv layers keep ACC = the compiler's bias.
      case "ACC" =>
        if (accFromDump) Some(s"$inpDir/input$layer.bin")
        else Some(s"$compilerOutDir/accumulator$layer.bin")
      // The compiler's per-op input$layer.bin is a placeholder (all zeros) - the
      // real input only exists at runtime (im2row / previous layer's output).
      // Load the actual GEMM-ready, block-tiled input that fsim/vsim dumps with
      // `--dump-layers` into simulators_output instead (inpDir).
      case "INP" => Some(s"$inpDir/input$layer.bin")
      case "WGT" => Some(s"$compilerOutDir/weight$layer.bin")
      case "OUT" => None
      case other =>
        throw new IllegalArgumentException(s"unknown region $other in $layer")
    }


  /** Build the full DRAM MemoryConfig list spanning all layers and the
    * per-layer launch parameters (in `layers` order).
    */
  def build(
      compilerOutDir: String,
      layers: Seq[String],
      reloStride: BigInt,
      memOutDir: os.Path,
      simOutDir: String = ""
  ): (Seq[MemoryConfig], Seq[LaunchParams]) = {
    // INP regions are loaded from simOutDir (fsim/vsim --dump-layers output) when
    // given, since the compiler's input$layer.bin is a zero placeholder; all other
    // regions come from compilerOutDir. Empty simOutDir falls back to compilerOutDir.
    val inpDir = if (simOutDir.nonEmpty) simOutDir else compilerOutDir
    os.makeDir.all(memOutDir)

    // Parse all layers up front so byte sizes are derived from the global
    // physical layout (gap to the next region), not the per-row logical address.
    val parsedLayers =
      loadLayerRegions(
        compilerOutDir,
        layers,
        lastBinFor(compilerOutDir)
      )

    val layerResults = parsedLayers.zipWithIndex.map {
      case ((layer, regionsRaw), idx) =>
        val relo = reloStride * idx
        // Route OUT last so reads at addresses where OUT overlaps UOP/INSN find
        // the non-OUT (initialized) entry first in MultiMemAxiClient's MuxCase.
        val regions = regionsRaw.sortBy(r => if (r.name == "OUT") 1 else 0)
        // int32/ALU layers (MaxPool) have no INP region; input arrives in ACC.
        val accFromDump = !regions.exists(_.name == "INP")

        val layerConfigs = regions.map { r =>
          val dt = DataType.fromName(r.name)
          val pathOpt =
            fileFor(compilerOutDir, inpDir, layer, r.name, accFromDump)

          val (memPath, numberOfData, words64) = pathOpt match {
            case Some(binPath) =>
              val memName = s"${r.name}_${layer}_init"
              val memFile = memOutDir / s"$memName.mem"
              val binJava = new java.io.File(binPath)
              val binSize = binJava.length()
              val cacheValid =
                memFile.toIO.exists() &&
                  memFile.toIO.lastModified() >= binJava.lastModified()
              val wordCount = if (cacheValid) {
                os.read.lines(memFile).size
              } else {
                // Write the per-layer init file the MultiMemAxiClient $readmemh's
                // (named memName == the recorded memPath basename), and return its
                // 64-bit word count.
                fileBin2hex(
                  binPath,
                  memOutDir,
                  dt,
                  outName = memName
                )
              }
              val numData =
                if (r.name == "INSN") wordCount / 2 else binSize.toInt
              (memFile.toString, numData, wordCount)
            case None =>
              val sizeWords64 = ((r.byteSize.getOrElse(0L) + 7) / 8).toInt
              ("", (r.byteSize.getOrElse(0L) / 4).toInt, sizeWords64)
          }

          val finalBase = BigInt(r.offset) + relo
          require(
            finalBase >= 0 && finalBase <= BigInt(Int.MaxValue),
            s"relocated base 0x${finalBase.toString(16)} for $layer.${r.name} " +
              s"exceeds 32-bit signed int (used by MemoryConfig.baseAddress)"
          )

          val entryName =
            if (r.name == "OUT") s"OUT_${layer}" else s"${r.name}_${layer}"

          MemoryConfig(
            name = entryName,
            path = memPath,
            baseAddress = finalBase.toInt,
            numberOfData = numberOfData,
            words64 = words64,
            logging = (r.name == "OUT")
          )
        }

        val insnRegion = regions
          .find(_.name == "INSN")
          .getOrElse(
            throw new RuntimeException(s"No INSN region for layer $layer")
          )
        val insnCount = insnCountFromFile(s"$compilerOutDir/instructions$layer.bin", 0L)
            .toInt
        val launch = LaunchParams(
          BigInt(insnRegion.offset) + relo,
          insnCount,
          relo
        )

        (layerConfigs, launch)
    }

    val (configsPerLayer, launchParams) = layerResults.unzip
    (configsPerLayer.flatten, launchParams)
  }
}
