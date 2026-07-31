package fpga.synthesis

import scopt.OParser

/** Package the emitted Xilinx shell as a Vivado IP-XACT core, into an IP
  * repository of its own. Simple wrapper that calls vivado on the package.tcl
  * script.
  *
  * Layout: the core is packaged into `<out>/vta` and `<out>` is what
  * create_project.tcl wants as `ip_repo_paths` (it expects the *parent* of the
  * core directory).
  */
object PackageIp {

  /** Directory name of the packaged core inside the repo. Shared with BuildFpga
    * so the two agree on where create_project.tcl will find it.
    */
  val coreDirName = "vta"

  def main(args: Array[String]): Unit = sys.exit(run(args))

  private case class Opts(
    board: String = "zcu104",
    emitDir: Option[String] = None,
    out: Option[String] = None,
    vivado: String = Vivado.tool(sys.env, "vivado"),
    dryRun: Boolean = false
  )

  private val argParser: OParser[_, Opts] = {
    val b = OParser.builder[Opts]
    import b._
    OParser.sequence(
      programName("packageIp"),
      head("packageIp", "VTA Vivado IP packager"),
      opt[String]("board")
        .action((x, c) => c.copy(board = x))
        .text("board name, for its part (default zcu104)"),
      opt[String]("emit-dir")
        .action((x, c) => c.copy(emitDir = Some(x)))
        .text(
          "emitted RTL directory holding package_ip.tcl and filelist.f (default <repo>/build/emitted/vta-xilinx-shell)"
        ),
      opt[String]("out")
        .required()
        .action((x, c) => c.copy(out = Some(x)))
        .text("IP repository directory to create; the core lands in <out>/vta"),
      opt[String]("vivado")
        .action((x, c) => c.copy(vivado = x))
        .text(
          "vivado executable (default $XILINX_VIVADO/bin/vivado, else vivado on PATH)"
        ),
      opt[Unit]("dry-run")
        .action((_, c) => c.copy(dryRun = true))
        .text("print commands without executing them")
    )
  }

  def run(argv: Array[String]): Int = {
    // VTA_ROOT is set by the Mill forkEnv for every forked JVM; fall back to
    // the process cwd for direct invocations from the repo root.
    val repoRoot = sys.env.get("VTA_ROOT").map(os.Path(_)).getOrElse(os.pwd)
    val boardsDir = repoRoot / "modules" / "fpga" / "boards"

    val o = OParser.parse(argParser, argv, Opts()) match {
      case Some(parsed) => parsed
      case _            => return 1
    }

    val board = Board.load((boardsDir / s"${o.board}.json").toString)
    val emitDir = os.Path(
      o.emitDir.getOrElse(
        (repoRoot / "build" / "emitted" / "vta-xilinx-shell").toString
      ),
      os.pwd
    )
    val outDir = os.Path(o.out.get, os.pwd)
    val ipRoot = outDir / coreDirName
    val tcl = emitDir / "package_ip.tcl"

    if (!o.dryRun && !os.exists(tcl)) {
      System.err.println(
        s"ERROR: emitted package_ip.tcl not found at $tcl\n" +
          s"       Emit the RTL first: ./mill modules.hardware.emitVtaFpgaConfig"
      )
      return 1
    }

    val vlnv =
      if (os.exists(tcl)) vlnvFromEmit(emitDir) else "unknown:unknown:VTA:0.0.0"
    println(
      s"[packageIp] board=${o.board} part=${board.part} emit_dir=$emitDir ip_repo=$outDir vlnv=$vlnv"
    )
    if (!o.dryRun) os.makeDir.all(outDir)

    // cwd is the output dir, and the log/journal are named explicitly, so
    // nothing is written next to the emitted RTL. --ip_root overrides the
    // default the emitter bakes into the script's header (which points back
    // into the emit dir); package_ip.tcl bases its scratch project on the
    // parent of ip_root, so that lands under --out too.
    Vivado.runCmd(
      Seq(
        o.vivado,
        "-mode",
        "batch",
        "-source",
        tcl.toString,
        "-log",
        (outDir / "vivado.log").toString,
        "-journal",
        (outDir / "vivado.jou").toString,
        "-tclargs",
        "--part",
        board.part,
        "--ip_root",
        ipRoot.toString
      ),
      cwd = outDir,
      dryRun = o.dryRun,
      stage = "package IP"
    )
    if (!o.dryRun) println(s"[packageIp] IP repo -> $outDir (core in $ipRoot)")
    0
  }

  /** The VLNV the emitted package_ip.tcl declares, as
    * vendor:library:name:version. Read from the script rather than recomputed,
    * so it can never disagree with what Vivado actually packages.
    */
  def vlnvFromEmit(emitDir: os.Path): String = {
    val pkg = emitDir / "package_ip.tcl"
    if (!os.exists(pkg))
      sys.error(
        s"ERROR: emitted package_ip.tcl not found at $pkg\n" +
          s"       Emit the RTL first: ./mill modules.hardware.emitVtaFpgaConfig"
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
}
