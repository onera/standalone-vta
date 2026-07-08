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
      emitDir: Option[String] = None,
      jobs: Option[Int] = None,
      vivado: String = "vivado",
      skipEmit: Boolean = false,
      skipPackage: Boolean = false,
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
        .text("output directory (default <repo>/build/synthesis)"),
      opt[String]("emit-dir")
        .action((x, c) => c.copy(emitDir = Some(x)))
        .text(
          "emitted RTL directory (default <repo>/build/emitted/vta-xilinx-shell)"
        ),
      opt[Int]("jobs")
        .action((x, c) => c.copy(jobs = Some(x)))
        .text("Vivado parallel jobs (default min(4, nCPUs))"),
      opt[String]("vivado")
        .action((x, c) => c.copy(vivado = x))
        .text("vivado executable (default vivado)"),
      opt[Unit]("skip-emit")
        .action((_, c) => c.copy(skipEmit = true))
        .text("skip the RTL emit stage"),
      opt[Unit]("skip-package")
        .action((_, c) => c.copy(skipPackage = true))
        .text("skip the IP-package stage"),
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
    val fpgaDir = repoRoot / "vta" / "fpga"
    val boardsDir = fpgaDir / "boards"
    require(
      os.exists(boardsDir),
      s"$boardsDir not found; run from the repo root (./mill vta.fpga.BuildFpga)"
    )
    // Extract the TCL recipe from the classpath to a real file for Vivado's
    // -source: URL.getPath is percent-encoded (breaks on paths with spaces)
    // and unusable when the resource sits inside a jar.
    val buildTcl = {
      val url =
        getClass.getClassLoader.getResource("synthesis/build_fpga.tcl")
      os.temp(url.openStream().readAllBytes(), suffix = "-build_fpga.tcl")
        .toString
    }

    val o = OParser.parse(argParser, argv, Opts()) match {
      case Some(parsed) => parsed
      case _            => return 1
    }

    val boardName = o.board
    // The stage-1 emit reads the config through the vta.config.file JVM
    // property, resolved as a bare filename under $VTA_ROOT/config (see
    // CoreConfig / BinaryReader.resolveConfigPath). --config therefore must
    // point inside <repo>/config; without it, honor an already-set property
    // so the manifest records the config the emit actually used.
    val configDir = repoRoot / "config"
    val configPath = o.config match {
      case Some(c) => os.Path(c, os.pwd)
      case None    =>
        os.Path(
          sys.props.getOrElse("vta.config.file", "vta_config.json"),
          configDir
        )
    }
    if (!os.exists(configPath)) {
      System.err.println(s"ERROR: config file not found: $configPath")
      return 1
    }
    if (configPath / os.up != configDir) {
      System.err.println(
        s"ERROR: config file must live in $configDir (got $configPath):\n" +
          "       the RTL emit resolves vta.config.file relative to that directory."
      )
      return 1
    }
    sys.props("vta.config.file") = configPath.last
    val outStr = o.out.getOrElse((repoRoot / "build" / "synthesis").toString)
    val emitDirStr = o.emitDir.getOrElse(
      (repoRoot / "build" / "emitted" / "vta-xilinx-shell").toString
    )
    val jobs =
      o.jobs.getOrElse(math.min(4, Runtime.getRuntime.availableProcessors))
    val vivado = o.vivado
    val skipEmit = o.skipEmit
    val skipPkg = o.skipPackage
    val dryRun = o.dryRun

    val board = Board.load((boardsDir / s"$boardName.json").toString)
    val outDir = os.Path(outStr, os.pwd)
    val emitDir = os.Path(emitDirStr, os.pwd)
    val ipRepo = emitDir / "ip_repo"
    val projDir = outDir / "project"
    val vtaCell = "VTA_0"

    println("=== VTA FPGA build ===")
    println(s"  board      : ${board.name}  (part ${board.part})")
    println(s"  config     : $configPath")
    println(s"  emit dir   : $emitDir")
    println(s"  output dir : $outDir")
    println(s"  jobs       : $jobs")

    // Stage 1: emit RTL
    val vlnv: String = if (!skipEmit) {
      if (dryRun) {
        println(
          s"\n[1/3 emit RTL] Emitting VTAXilinxShell to $emitDir"
        )
        s"${vta.XilinxEmit.vendor}:${vta.XilinxEmit.lib}:${vta.XilinxEmit.name}:${vta.XilinxEmit.version}"
      } else {
        vta.XilinxEmit.emitXilinx(emitDir)
      }
    } else {
      println("\n[1/3 emit RTL] skipped (--skip-emit)")
      if (dryRun && !os.exists(emitDir / "package_ip.tcl")) {
        s"${vta.XilinxEmit.vendor}:${vta.XilinxEmit.lib}:${vta.XilinxEmit.name}:${vta.XilinxEmit.version}"
      } else {
        vlnvFromEmit(emitDir)
      }
    }

    // Stage 2: package IP
    if (!skipPkg) {
      runCmd(
        Seq(
          vivado,
          "-mode",
          "batch",
          "-source",
          (emitDir / "package_ip.tcl").toString,
          "-tclargs",
          "--part",
          board.part
        ),
        cwd = emitDir,
        dryRun = dryRun,
        stage = "2/3 package IP"
      )
    } else {
      println("\n[2/3 package IP] skipped (--skip-package)")
    }

    println(s"  VTA IP     : $vlnv")

    // Stage 3: build project -> bitstream -> XSA
    val params = BoardParams.render(
      board,
      vtaCell,
      vlnv.split(" ").head,
      ipRepo.toString,
      outDir.toString,
      projDir.toString,
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
      println(s"\n[3/3 build] wrote $paramsFile")
    }

    runCmd(
      Seq(
        vivado,
        "-mode",
        "batch",
        "-source",
        buildTcl,
        "-tclargs",
        paramsFile.toString
      ),
      cwd = outDir,
      dryRun = dryRun,
      stage = "3/3 build"
    )

    // Timing verdict
    val timing: Option[Boolean] =
      if (!dryRun) timingMet(outDir / "timing_summary.rpt") else None

    // Provenance manifest
    val xsa = outDir / s"vta_${board.name}.xsa"
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

    os.write.over(outDir / "manifest.json", json + "\n")

    val softwareDir = fpgaDir / "software"
    val ext = if (board.isVersal) "pdi" else "bit"
    val bit = outDir / s"vta_${board.name}.$ext"
    val timingStr = timing match {
      case Some(true)  => "MET"
      case Some(false) => "NOT MET"
      case None        => "unknown"
    }
    println("\n=== Done ===")
    println(s"  XSA      : $xsa")
    println(s"  Image    : $bit")
    println(
      s"  Reports  : ${outDir / "timing_summary.rpt"}, ${outDir / "utilization.rpt"}"
    )
    println(s"  Manifest : ${outDir / "manifest.json"}")
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

  private def vlnvFromEmit(emitDir: os.Path): String = {
    val pkg = emitDir / "package_ip.tcl"
    if (!os.exists(pkg))
      sys.error(
        s"ERROR: emitted package_ip.tcl not found at $pkg\n" +
          s"       Run without --skip-emit, or run the Mill emit first."
      )
    val text = os.read(pkg)
    val fields = Seq("ip_vendor", "ip_lib", "ip_name", "ip_version").map {
      key =>
        val pat = s"""set\\s+${key}\\s+"([^"]+)"""".r
        pat.findFirstMatchIn(text) match {
          case Some(m) => m.group(1)
          case None    => sys.error(s"ERROR: could not parse '$key' from $pkg")
        }
    }
    fields.mkString(":")
  }

  private def runCmd(
      cmd: Seq[String],
      cwd: os.Path,
      dryRun: Boolean,
      stage: String
  ): Unit = {
    println(s"\n[$stage] (cwd=$cwd)\n    ${cmd.mkString(" ")}")
    if (dryRun) return
    val libudev = os.Path("/lib/x86_64-linux-gnu/libudev.so.1")
    val extraEnv: Map[String, String] =
      if (
        os.exists(libudev) && cmd.headOption.exists(
          _.toLowerCase.contains("vivado")
        )
      )
        Map("LD_PRELOAD" -> libudev.toString)
      else Map.empty
    val result = os.proc(cmd).call(cwd = cwd, env = extraEnv, check = false)
    if (result.exitCode != 0) {
      val logHint = cwd / "vivado.log"
      val extra = if (os.exists(logHint)) s"\n       see $logHint" else ""
      println(
        s"ERROR: [$stage] command failed (exit ${result.exitCode}).$extra"
      )
      sys.exit(result.exitCode)
    }
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
