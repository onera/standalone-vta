package fpga.synthesis

import com.fasterxml.jackson.databind.ObjectMapper
import java.security.MessageDigest
import scala.collection.immutable.ListMap
import scala.jdk.CollectionConverters._
import scopt.OParser
import java.io.File

object BuildFpga {

  def main(args: Array[String]): Unit = sys.exit(run(args))

  private case class Opts(
    board: String = "zcu104",
    config: Option[String] = None,
    out: Option[String] = None,
    exportDir: Option[String] = None,
    emitDir: Option[String] = None,
    ipRepo: Option[String] = None,
    jobs: Option[Int] = None,
    vivado: String = Vivado.tool(sys.env, "vivado"),
    skipProject: Boolean = false,
    skipSynth: Boolean = false,
    dryRun: Boolean = false
  )

  private val argParser: OParser[_, Opts] = {
    val b = OParser.builder[Opts]
    import b._
    OParser.sequence(
      programName("buildFpga"),
      head("buildFpga", "VTA FPGA bitstream builder (Vivado)"),
      opt[String]("board")
        .action((x, c) => c.copy(board = x))
        .text("board name (default zcu104)"),
      opt[String]("config")
        .action((x, c) => c.copy(config = Some(x)))
        .text(
          "path to a config JSON inside <repo>/config (default: -Dvta.config.file, else <repo>/config/vta_config.json)"
        ),
      opt[String]("out")
        .action((x, c) => c.copy(out = Some(x)))
        .text(
          "build directory: board_params.tcl + the Vivado project (default <repo>/build/synthesis)"
        ),
      opt[String]("export-dir")
        .action((x, c) => c.copy(exportDir = Some(x)))
        .text(
          "where the XSA, bitstream, reports and manifest land (default: the --out dir)"
        ),
      opt[String]("emit-dir")
        .action((x, c) => c.copy(emitDir = Some(x)))
        .text(
          "emitted RTL directory (default <repo>/build/emitted/vta-xilinx-shell)"
        ),
      opt[String]("ip-repo")
        .action((x, c) => c.copy(ipRepo = Some(x)))
        .text(
          "IP repository holding the packaged VTA core, from fpga.synthesis.PackageIp (default <emit-dir>/ip_repo)"
        ),
      opt[Int]("jobs")
        .action((x, c) => c.copy(jobs = Some(x)))
        .text("Vivado parallel jobs (default min(4, nCPUs))"),
      opt[String]("vivado")
        .action((x, c) => c.copy(vivado = x))
        .text(
          "vivado executable (default $XILINX_VIVADO/bin/vivado, else vivado on PATH)"
        ),
      opt[Unit]("skip-project")
        .action((_, c) => c.copy(skipProject = true))
        .text(
          "skip the create-project stage; assume <out>/project/<board>/<board>.xpr already exists"
        ),
      opt[Unit]("skip-synth")
        .action((_, c) => c.copy(skipSynth = true))
        .text(
          "stop after creating the project, before synthesis/implementation/XSA export"
        ),
      opt[Unit]("dry-run")
        .action((_, c) => c.copy(dryRun = true))
        .text("print commands without executing them")
    )
  }

  def run(argv: Array[String]): Int = {
    // VTA_ROOT is set by the Mill forkEnv for every forked JVM (including
    // sandboxed test runs, where os.pwd is NOT the repo root). Fall back to
    // the process cwd for direct invocations from the repo root.
    val repoRoot = sys.env.get("VTA_ROOT").map(os.Path(_)).getOrElse(os.pwd)
    val fpgaDir = repoRoot / "modules" / "fpga"
    val boardsDir = fpgaDir / "boards"
    require(
      os.exists(boardsDir),
      s"$boardsDir not found; run from the repo root (./mill vta.fpga.BuildFpga)"
    )
    // Extracted here (not deferred to point of use) so a missing classpath
    // resource fails fast, before any Vivado stage runs.
    val createProjectTcl =
      Vivado.extractResource(
        "synthesis/create_project.tcl",
        "-create_project.tcl"
      )
    val synthesisTcl =
      Vivado.extractResource("synthesis/synthesis.tcl", "-synthesis.tcl")

    val o = OParser.parse(argParser, argv, Opts()) match {
      case Some(parsed) => parsed
      case _            => return 1
    }

    val boardName = o.board
    // The config is only provenance here (recorded in the manifest with its
    // sha256): the RTL itself comes pre-emitted in --emit-dir. Default from
    // -Dvta.config.file (forwarded by the Mill commands) under <repo>/config.
    val configDir = repoRoot / "config"
    val configPath = o.config match {
      case Some(c) => os.Path(c, os.pwd)
      case None =>
        os.Path(
          sys.props.getOrElse("vta.config.file", "vta_config.json"),
          configDir
        )
    }
    if (!os.exists(configPath)) {
      System.err.println(s"ERROR: config file not found: $configPath")
      return 1
    }
    val outStr = o.out.getOrElse((repoRoot / "build" / "synthesis").toString)
    val emitDirStr = o.emitDir.getOrElse(
      (repoRoot / "build" / "emitted" / "vta-xilinx-shell").toString
    )
    val jobs =
      o.jobs.getOrElse(math.min(4, Runtime.getRuntime.availableProcessors))
    val vivado = o.vivado
    val skipProject = o.skipProject
    val skipSynth = o.skipSynth
    val dryRun = o.dryRun

    val board = Board.load((boardsDir / s"$boardName.json").toString)
    val outDir = os.Path(outStr, os.pwd)
    val emitDir = os.Path(emitDirStr, os.pwd)
    // The IP repository is produced by fpga.synthesis.PackageIp, which owns its
    // own directory (the Mill task modules.fpga.targets[...].ipRepo). The
    // legacy <emit-dir>/ip_repo default is only for a hand-driven flow that
    // ran the old in-tree packaging; it makes this tool read the emit dir,
    // never write it.
    val ipRepo = o.ipRepo.map(os.Path(_, os.pwd)).getOrElse(emitDir / "ip_repo")
    val projDir = outDir / "project"
    // Where the deliverables (XSA, bitstream, reports, manifest) land. The
    // Vivado project stays in --out; Mill's fpgaSynth passes its own task
    // dest here so artifacts are written straight into it, no copy step.
    val exportDir = o.exportDir.map(os.Path(_, os.pwd)).getOrElse(outDir)
    val vtaCell = "VTA_0"

    println("=== VTA FPGA build ===")
    println(s"  board      : ${board.name}  (part ${board.part})")
    println(s"  config     : $configPath")
    println(s"  emit dir   : $emitDir")
    println(s"  ip repo    : $ipRepo")
    println(s"  output dir : $outDir")
    println(s"  export dir : $exportDir")
    println(s"  jobs       : $jobs")

    // The RTL emit is owned by Mill (modules.hardware.configs[c].vtaFpgaConfig)
    // and the IP packaging by fpga.synthesis.PackageIp; this tool consumes an
    // already-emitted dir and an already-packaged repo, and reads the IP
    // identity out of the emitted package_ip.tcl.
    val vlnv: String =
      if (dryRun && !os.exists(emitDir / "package_ip.tcl"))
        "unknown:unknown:VTA:0.0.0"
      else PackageIp.vlnvFromEmit(emitDir)

    println(s"  VTA IP     : $vlnv")

    if (!dryRun && !skipProject && !os.exists(ipRepo / PackageIp.coreDirName)) {
      System.err.println(
        s"ERROR: no packaged VTA IP under $ipRepo\n" +
          s"       Package it first: ./mill \"modules.fpga.targets[<config>,${board.name}].ipRepo\"\n" +
          s"       (or fpga.synthesis.PackageIp --board ${board.name} --emit-dir $emitDir --out <dir>)"
      )
      return 1
    }

    // board_params.tcl: always (re)written so a later --skip-project run
    // (possibly with different --jobs) sources fresh values.
    val params = BoardParams.render(
      board,
      vtaCell,
      vlnv.split(" ").head,
      ipRepo.toString,
      outDir.toString,
      projDir.toString,
      exportDir.toString,
      jobs
    )
    val paramsFile = outDir / "board_params.tcl"
    if (dryRun) {
      println("\n--- generated board_params.tcl ---")
      println(params)
      println("--- end board_params.tcl ---")
    } else {
      os.makeDir.all(outDir)
      os.write.over(paramsFile, params + "\n")
      println(s"\n[1/2 create project] wrote $paramsFile")
    }

    // Stage 1: create project + block design
    if (!skipProject) {
      Vivado.runCmd(
        Seq(
          vivado,
          "-mode",
          "batch",
          "-source",
          createProjectTcl,
          "-tclargs",
          paramsFile.toString
        ),
        cwd = outDir,
        dryRun = dryRun,
        stage = "1/2 create project"
      )
    } else {
      println("\n[1/2 create project] skipped (--skip-project)")
    }

    if (skipSynth) {
      val xpr = projDir / board.name / s"${board.name}.xpr"
      println("\n[2/2 synth] skipped (--skip-synth)")
      if (os.exists(xpr)) {
        println(s"Project ready: $xpr")
      } else {
        println(
          s"WARNING: project not found at $xpr (--skip-project was also set, so it was never created this run)"
        )
      }
      println("Open it in the Vivado GUI to edit, then resume with:")
      println(
        s"  buildFpga --board ${board.name} --out $outDir --config $configPath --emit-dir $emitDirStr --ip-repo $ipRepo --jobs $jobs --vivado $vivado --skip-project"
      )
      return 0
    }

    // Stage 2: synthesis + implementation + XSA export
    Vivado.runCmd(
      Seq(
        vivado,
        "-mode",
        "batch",
        "-source",
        synthesisTcl,
        "-tclargs",
        paramsFile.toString
      ),
      cwd = outDir,
      dryRun = dryRun,
      stage = "2/2 synth"
    )

    // Timing verdict
    val timing: Option[Boolean] =
      if (!dryRun) timingMet(exportDir / "timing_summary.rpt") else None

    // Provenance manifest
    val xsa = exportDir / s"vta_${board.name}.xsa"
    val manifest: ListMap[String, AnyRef] = ListMap(
      "board" -> board.name,
      "cpu" -> board.cpu,
      "part" -> board.part,
      "config" -> configPath.toString,
      "config_sha256" -> (if (os.exists(configPath)) sha256(configPath)
                          else null),
      "vta_vlnv" -> vlnv.split(" ").head,
      "git_sha" -> gitSha(repoRoot),
      "xsa" -> xsa.toString,
      "timing_met" -> timing.map(java.lang.Boolean.valueOf).orNull,
      "built_at" -> java.time.LocalDateTime.now().withNano(0).toString
    )

    val mapper = new ObjectMapper()
    val json =
      mapper
        .writerWithDefaultPrettyPrinter()
        .writeValueAsString(manifest.asJava)

    if (dryRun) {
      println("\n--- manifest.json (preview) ---")
      println(json)
      println("\n=== DRY RUN complete (nothing executed) ===")
      return 0
    }

    os.write.over(exportDir / "manifest.json", json + "\n")

    val softwareDir = fpgaDir / "software"
    val ext = if (board.isVersal) "pdi" else "bit"
    val bit = exportDir / s"vta_${board.name}.$ext"
    val timingStr = timing match {
      case Some(true)  => "MET"
      case Some(false) => "NOT MET"
      case None        => "unknown"
    }
    println("\n=== Done ===")
    println(s"  XSA      : $xsa")
    println(s"  Image    : $bit")
    println(
      s"  Reports  : ${exportDir / "timing_summary.rpt"}, ${exportDir / "utilization.rpt"}"
    )
    println(s"  Manifest : ${exportDir / "manifest.json"}")
    println(s"  Timing   : $timingStr")
    if (timing.contains(false)) {
      println(
        "\n  !! WARNING: timing constraints are NOT met. The bitstream was still\n" +
          "     written (Vivado does this regardless of slack) but is NOT reliable on\n" +
          s"     hardware at this clock. Lower pl_clock_mhz in boards/${board.name}.json\n" +
          "     or target a larger/faster part, then rebuild. See timing_summary.rpt."
      )
    }
    println("\nNext: create the Vitis platform from the XSA:")
    println(s"  make -C $softwareDir workspace XSA=$xsa CPU=${board.cpu}")

    0
  }

  private def timingMet(report: os.Path): Option[Boolean] = {
    if (!os.exists(report)) None
    else {
      val text = os.read(report)
      if (text.contains("Timing constraints are not met")) Some(false)
      else if (text.contains("All user specified timing constraints are met"))
        Some(true)
      else None
    }
  }

  private def gitSha(repoRoot: os.Path): String = {
    try {
      val result =
        os.proc("git", "-C", repoRoot.toString, "rev-parse", "HEAD")
          .call(check = false)
      if (result.exitCode == 0) result.out.trim() else "(unknown)"
    } catch { case _: Exception => "(unknown)" }
  }

  private def sha256(path: os.Path): String = {
    val digest = MessageDigest.getInstance("SHA-256")
    digest.update(os.read.bytes(path))
    digest.digest().map("%02x".format(_)).mkString
  }
}
