package vta.test

import vta.models.{DataType, MemoryConfig}
import vta.parsers.CompilerOutputParser.parseAddressesCsv
import vta.parsers.DramInitParser


object TestBenchLayout {



  /** Per-layer launch parameters: VCR insn base, instruction count, relocation.
    */
  case class LaunchParams(insnBaddr: BigInt, insnCount: Int, relo: BigInt)


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
    val cfgs = scala.collection.mutable.ListBuffer.empty[MemoryConfig]
    val perLayer = scala.collection.mutable.ListBuffer.empty[LaunchParams]

    for ((layer, idx) <- layers.zipWithIndex) {
      val relo = reloStride * idx
      val regionsRaw = parseAddressesCsv(compilerOutDir, layer)
      // Route OUT last so reads at addresses where OUT overlaps UOP/INSN find
      // the non-OUT (initialized) entry first in MultiMemAxiClient's MuxCase.
      val regions = regionsRaw.sortBy(r => if (r.name == "OUT") 1 else 0)
      // int32/ALU layers (MaxPool) have no INP region; their input arrives in ACC.
      val accFromDump = !regions.exists(_.name == "INP")

      for (r <- regions) {
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
              DramInitParser.fileBin2hex(
                binPath,
                memOutDir,
                dt,
              )
            }
            val numData =
              if (r.name == "INSN") wordCount / 2 else binSize.toInt
            (memFile.toString, numData, wordCount)
          case None =>
            val sizeWords64 = ((r.sizeBytes + 7) / 8).toInt
            ("", (r.sizeBytes / 4).toInt, sizeWords64)
        }

        val finalBase = BigInt(r.base) + relo
        require(
          finalBase >= 0 && finalBase <= BigInt(Int.MaxValue),
          s"relocated base 0x${finalBase.toString(16)} for $layer.${r.name} " +
            s"exceeds 32-bit signed int (used by MemoryConfig.baseAddress)"
        )

        val entryName =
          if (r.name == "OUT") s"OUT_${layer}" else s"${r.name}_${layer}"

        cfgs += MemoryConfig(
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
      val insnBinSize =
        new java.io.File(s"$compilerOutDir/instructions$layer.bin").length()
      val insnCount = (insnBinSize / 16).toInt
      perLayer += LaunchParams(BigInt(insnRegion.base) + relo, insnCount, relo)
    }

    (cfgs.toList, perLayer.toList)
  }

}
