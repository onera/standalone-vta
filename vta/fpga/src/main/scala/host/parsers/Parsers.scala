package fpga.host.parsers

import vta.configs.DefaultPynqConfig
import vta.models.CompilerOutputModel.{DependencyInfo}
import vta.models.DataType
import fpga.host.models.HwConfig
import fpga.host.models.HwConfig.ConfigParams
import fpga.host.models.Model
import fpga.host.transform.HwConfigResolver
import vta.parsers.ConfigParser.parseConfigJsonAt
import vta.parsers.MetadataParser.loadLayerRegions
import vta.models.CompilerOutputModel.MemoryRegion

/** Reads a vta_config.json into the host [[ConfigParams]] model.
  *
  * The JSON read is reused from [[vta.parsers.VtaConfig]] (`loadRawEntriesAt`);
  * any key the file omits falls back to the Chisel [[vta.DefaultPynqConfig]]
  * (no hardcoded defaults). `null` selects the default config outright.
  */
object ConfigParser {
  def load(configJsonPath: String): ConfigParams = {
    val cfg = parseConfigJsonAt(configJsonPath).toOption
      .getOrElse(Map.empty[String, String])
    val default = HwConfigResolver.fromParameters(new DefaultPynqConfig)
    ConfigParams(
      blockSize = cfg
        .get("LOG_BLOCK")
        .map(v => 1 << v.toInt)
        .getOrElse(default.blockSize),
      logInpWidth =
        cfg.get("LOG_INP_WIDTH").map(_.toInt).getOrElse(default.logInpWidth),
      logOutWidth =
        cfg.get("LOG_OUT_WIDTH").map(_.toInt).getOrElse(default.logOutWidth),
      logWgtWidth =
        cfg.get("LOG_WGT_WIDTH").map(_.toInt).getOrElse(default.logWgtWidth),
      logAccWidth =
        cfg.get("LOG_ACC_WIDTH").map(_.toInt).getOrElse(default.logAccWidth),
      target = cfg.get("TARGET").orElse(default.target)
    )
  }
}

/** Builds the per-layer [[Model.LayerInfo]] list from a compiler-output dir.
  *
  * Reuses [[vta.parsers.]] for the memory_addresses regions and their gap-based
  * byte sizes. Missing buffer types (e.g. a MaxPool layer has no INP/WGT)
  * become zero-size regions so downstream emitters can treat every layer
  * uniformly. `vtaSuffixes` come from `dep.executionOrder` and each layer's
  * `reshapeInfo` from `dep.layers` (defaulting to "im2row" when absent).
  */
object LayerParser {
  def collectLayers(
    compDir: String,
    dep: DependencyInfo
  ): Seq[Model.LayerInfo] = {
    val vtaSuffixes = dep.executionOrder.collect { case (_, "vta", n) => n }
    if (vtaSuffixes.isEmpty)
      sys.error("ERROR: no VTA layers found in dependency.csv")
    val parsed = loadLayerRegions(
      compDir,
      vtaSuffixes,
      (layer, name) => Some(Model.layerBinfile(compDir, name, layer))
    )
    parsed.map { case (suffix, regions) =>
      val byName = regions.map(r => r.name -> r).toMap
      val mem = DataType.names.map { t =>
        t -> byName.getOrElse(t, MemoryRegion(t, 0L, None, 0L))
      }.toMap
      val missing = DataType.names.filterNot(byName.contains)
      if (missing.nonEmpty)
        println(
          s"WARNING: ${Model.memAddressesPath(compDir, suffix)} missing entries for " +
            missing.map(t => s"'$t'").mkString("[", ", ", "]") +
            " - treating as size=0 (maxpool/no-weight layer)"
        )
      val binFiles =
        DataType.names
          .map(t => t -> Model.layerBinfile(compDir, t, suffix))
          .toMap
      val reshapeInfo =
        dep.layers.get(suffix).map(_.reshapeInfo).getOrElse("im2row")
      Model.LayerInfo(
        suffix = suffix,
        mem = mem,
        binFiles = binFiles,
        reshapeInfo = reshapeInfo
      )
    }
  }
}
