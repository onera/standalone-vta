package fpga.host

import scopt.OParser
import vta.configs.DefaultPynqConfig
import vta.parsers.Dependency.loadDependencyInfo
import fpga.host.models._
import fpga.host.transform.{HwConfigResolver, MemoryLayout}
import fpga.host.checkers._
import fpga.host.parsers.LayerParser
import fpga.host.exporters.all._
import os.Path
import fpga.utils.HexUtils.parseAddr
import vta.models.CompilerOutputModel.alignPage

/** CLI entry point for the baremetal codegen. Mirrors nnbaremetal/cli.py.
  *
  * The hardware config is taken from the Chisel `DefaultPynqConfig` (driven by
  * `-Dvta.config.file`, the same single source the SV emitters use) rather than
  * a `--config-json` argument. The pipeline lives in [[generate]] so tests can
  * call it directly with a per-fixture [[HwConfig.ConfigParams]]; [[main]]
  * parses the CLI with scopt and derives the config from `DefaultPynqConfig`.
  */
object GenNnBaremetal {

  /** Generate all baremetal header / loader files for one compiler output.
    *
    * Throws (via [[sys.error]]) on any failure so a caller can catch it (tests)
    * or let it propagate to [[main]], which maps it to `sys.exit(1)`.
    */
  def generate(
    compDir: String,
    outdir: String,
    ddrBase: Long,
    cfg: HwConfig.ConfigParams,
    emitLayerCheck: Boolean = false,
    emitCpuCheck: Boolean = false,
    emitSdManifest: Boolean = false,
    stageSdFiles: Boolean = true,
    goldenDir: Option[String] = None,
    refDir: Option[String] = None,
    sdDir: String = "",
    maxAddr: Option[Long] = None,
    verbose: Boolean = false
  ): Unit = {
    val blockSize = cfg.blockSize
    val emitCheck = emitLayerCheck || emitCpuCheck
    println(
      s"[gen] VTA block size: $blockSize" +
        s" | inp=${1 << cfg.logInpWidth}-bit" +
        s" | out=${1 << cfg.logOutWidth}-bit" +
        s" | acc=${1 << cfg.logAccWidth}-bit"
    )
    println(s"[gen] Output directory: $outdir")

    val depPath = s"$compDir/dependency.csv"
    if (!os.exists(os.Path(depPath, os.pwd)))
      sys.error(s"ERROR: dependency.csv not found: $depPath")
    val dep = loadDependencyInfo(depPath)
    println(
      s"[gen] dependency.csv: ${dep.executionOrder.length} execution steps"
    )

    if (!Checks.checkConfigCompat(cfg, dep)) sys.error("incompatible config")

    val layers = LayerParser.collectLayers(compDir, dep)
    println(s"[gen] found ${layers.length} VTA layer(s)")

    val suffixToIdx = Model.suffixToIdx(layers)
    val (cpuOut, allocTop, cpuScratch) =
      MemoryLayout.buildCpuOutAddrs(
        dep,
        layers,
        ddrBase,
        suffixToIdx,
        compDir,
        refDir
      )
    val (ctParams, ctBlobs, allocTop2) =
      MemoryLayout.buildCpuParamAddrs(dep, compDir, allocTop)
    // CPU activation scratch + CPU-op parameter blobs, for the layout checks.
    val allScratch: Seq[(String, Long, Long)] =
      cpuScratch ++ ctBlobs.map(b => (b.label, b.addr, b.size))

    if (
      !Checks.runGuards(
        dep,
        layers,
        ddrBase,
        suffixToIdx,
        cpuOut,
        blockSize,
        HwConfig.elemBytes(cfg.logInpWidth),
        allScratch,
        compDir,
        refDir,
        maxAddr = None
      )
    )
      sys.error("layout checks failed")

    val resolvedGoldenDir =
      if (!emitCheck) ""
      else {
        val gd = goldenDir.getOrElse(
          sys.error("ERROR: --emit-layer-check requires --golden-dir")
        )
        if (!os.isDir(os.Path(gd, os.pwd)))
          sys.error(s"ERROR: --golden-dir not found: $gd")
        gd
      }

    // activeL is `layers` in non-check mode; in check mode it is the updated
    // sequence returned by assignLayerCheckRegions (check fields populated).
    val activeL: Seq[Model.LayerInfo] =
      if (emitCheck) {
        val (checkedLayers, checkTop) =
          MemoryLayout.assignLayerCheckRegions(
            layers,
            dep,
            ddrBase,
            resolvedGoldenDir,
            allocTop2
          )
        val alignedBase = alignPage(allocTop2)
        println(
          f"[gen] isolation-check golden regions: 0x${alignedBase}%08X-0x${checkTop}%08X"
        )
        if (!Checks.checkBufferOverlaps(checkedLayers, ddrBase, allScratch))
          sys.error("layout check failed: buffer overlaps")
        checkedLayers
      } else layers

    os.makeDir.all(os.Path(outdir, os.pwd))
    def out(fn: String): os.Path = os.Path(s"$outdir/$fn", os.pwd)

    println(s"[gen] VTA hardware config written at ${out("vta_hw_config.h")}")
    cfg.export(out("vta_hw_config.h"))
    DdrMap(activeL, ddrBase).export(out("nn_ddr_map.h"))
    ExecPlan(
      dep,
      activeL,
      ddrBase,
      compDir,
      blockSize = blockSize,
      suffixToIdx = Some(suffixToIdx),
      cpuOut = Some(cpuOut),
      logOutWidth = cfg.logOutWidth,
      ctParams = Some(ctParams)
    ).export(out("nn_exec_plan.h"))
    LoadTcl(
      activeL,
      ddrBase,
      compDir,
      scriptName = "load_nn_static.tcl",
      includeInput = false,
      extraBlobs = ctBlobs,
      refDir = refDir
    ).export(out("load_nn_static.tcl"))
    LoadTcl(
      activeL,
      ddrBase,
      compDir,
      scriptName = "load_nn.tcl",
      includeInput = true,
      extraBlobs = ctBlobs,
      refDir = refDir
    ).export(out("load_nn.tcl"))
    InputTcl(activeL, ddrBase, compDir, refDir = refDir)
      .export(out("load_input.tcl"))

    if (emitSdManifest)
      SdManifest(
        activeL,
        ddrBase,
        compDir,
        sdCardDir = out("sd_card").toString,
        sdDir = sdDir,
        emitRefs = emitCheck,
        extraBlobs = ctBlobs,
        stageFiles = stageSdFiles,
        refDir = refDir
      ).export(out("nn_sd_manifest.h"))

    AsmIncbin(activeL, emitCheck = emitCheck, extraBlobs = ctBlobs).export(
      out("nn_bin_data.S")
    )
    LinkerFragment(
      activeL,
      ddrBase,
      emitCheck = emitCheck,
      extraBlobs = ctBlobs
    ).export(out("nn_vta_sections.ld"))

    if (emitCheck)
      DebugMap(activeL).export(out("nn_debug_map.h"))
    if (emitCpuCheck)
      CpuDebugMap(dep, activeL, cfg, suffixToIdx, ddrBase, compDir, refDir)
        .export(out("nn_cpu_debug_map.h"))

    if (verbose) Checks.printSummary(activeL, ddrBase)

    maxAddr match {
      case Some(ma) =>
        if (!Checks.checkMemoryFit(activeL, ddrBase, ma, refDir, allScratch))
          sys.error("layout check failed: allocations exceed max DDR address")
      case None =>
        println(
          "WARNING: --max-addr not given - DDR fit check skipped; allocations" +
            " (incl. golden regions) are not verified to fit the board's mapped" +
            " DRAM. Pass --max-addr <hex> to enable the check."
        )
    }
  }

  /** scopt command-line options. The hardware config is NOT an option here - it
    * comes from the Chisel DefaultPynqConfig (`-Dvta.config.file`).
    */
  private case class Opts(
    compilerOutputDir: String = "",
    ddrBase: String = "0x0",
    outdir: String = "build/baremetal",
    maxAddr: Option[String] = None,
    verbose: Boolean = false,
    emitLayerCheck: Boolean = false,
    emitCpuCheck: Boolean = false,
    emitSdManifest: Boolean = false,
    stageSdFiles: Boolean = true,
    goldenDir: Option[String] = None,
    refDir: Option[String] = None,
    sdDir: String = ""
  )

  /** Get repo root absolute path from VTA_ROOT env variable, fallback to
    * current working dir
    *
    * @return
    *   absolute repo root path
    */
  private def repoRoot = sys.env.get("VTA_ROOT").getOrElse(os.pwd)

  private val argParser: OParser[_, Opts] = {
    val b = OParser.builder[Opts]
    import b._
    OParser.sequence(
      programName("genNnBaremetal"),
      head(
        "genNnBaremetal",
        "VTA baremetal codegen (hardware config from the Chisel DefaultPynqConfig / -Dvta.config.file)"
      ),
      arg[String]("<compiler_output_dir>")
        .action((x, c) => c.copy(compilerOutputDir = x))
        .text("compiler output directory")
        .required()
        .validate(x =>
          if (os.isDir(os.Path(x, os.pwd))) success
          else
            failure(
              s"compiler output directory not found: ${os.Path(x, os.pwd)}"
            )
        ),
      opt[String]("ddr-base")
        .action((x, c) => c.copy(ddrBase = x))
        .text("DDR base address (hex, default 0x0)"),
      opt[String]("outdir")
        .action((x, c) => c.copy(outdir = x))
        .text("output directory (default <repo>/build/baremetal)"),
      opt[String]("max-addr")
        .action((x, c) => c.copy(maxAddr = Some(x)))
        .text("verify allocations fit below this DDR address (hex)"),
      opt[Unit]("verbose")
        .action((_, c) => c.copy(verbose = true))
        .text("print the DRAM map summary"),
      opt[Unit]("emit-layer-check")
        .action((_, c) => c.copy(emitLayerCheck = true))
        .text(
          "emit per-layer isolation-check artifacts (requires --golden-dir)"
        ),
      opt[Unit]("emit-cpu-check")
        .action((_, c) => c.copy(emitCpuCheck = true))
        .text(
          "emit the per-CPU-op isolation-check map (implies --emit-layer-check)"
        ),
      opt[Unit]("emit-sd-manifest")
        .action((_, c) => c.copy(emitSdManifest = true))
        .text("emit the SD-card manifest and stage the .bin set"),
      opt[Unit]("no-stage-sd-files")
        .action((_, c) => c.copy(stageSdFiles = false))
        .text(
          "with --emit-sd-manifest: emit the header only, do not copy the" +
            " .bin set into <outdir>/sd_card"
        ),
      opt[String]("golden-dir")
        .action((x, c) => c.copy(goldenDir = Some(x)))
        .text(
          "fsim per-layer golden dump directory (required with the check flags)"
        )
        .validate(x =>
          if (os.isDir(os.Path(x, os.pwd))) success
          else failure(s"ERROR: golden dump directory not found: $x")
        ),
      opt[String]("ref-dir")
        .action((x, c) => c.copy(refDir = Some(x)))
        .text("reference dir holding input_nn.bin (reference_output)")
        .validate(x =>
          if (os.isDir(os.Path(x, os.pwd))) success
          else failure(s"ERROR: reference directory not found: $x")
        ),
      opt[String]("sd-dir")
        .action((x, c) => c.copy(sdDir = x))
        .text("SD-card subfolder for the staged files")
    )
  }

  def main(args: Array[String]): Unit =
    OParser.parse(argParser, args, Opts()) match {
      case Some(o) =>
        // Hardware config from the Chisel DefaultPynqConfig (-Dvta.config.file).
        val cfg = HwConfigResolver.fromParameters(new DefaultPynqConfig)
        Model.runOrExit {
          generate(
            compDir = new java.io.File(o.compilerOutputDir).getAbsolutePath,
            outdir = new java.io.File(o.outdir).getAbsolutePath,
            ddrBase = parseAddr(o.ddrBase),
            cfg = cfg,
            emitLayerCheck = o.emitLayerCheck || o.emitCpuCheck,
            emitCpuCheck = o.emitCpuCheck,
            emitSdManifest = o.emitSdManifest,
            stageSdFiles = o.stageSdFiles,
            goldenDir =
              o.goldenDir.map(gd => new java.io.File(gd).getAbsolutePath),
            refDir = o.refDir.map(rd => new java.io.File(rd).getAbsolutePath),
            sdDir = o.sdDir,
            maxAddr = o.maxAddr.map(parseAddr),
            verbose = o.verbose
          )
        }
      case _ => // scopt already printed usage / the error
    }
}
