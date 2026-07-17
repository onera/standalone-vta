package fpga.synthesis

/** Shared Vivado / xsim process glue, used by BuildFpga, OocNetlist and
  * RunXsim.
  *
  * Kept dependency-free (only os-lib) so every synthesis orchestrator shares
  * one copy of the command-runner and the classpath-resource extractor.
  */
object Vivado {

  /** Run an external tool, echoing the command and stage. On a non-zero exit,
    * print a vivado.log hint (if present in cwd) and exit with that code.
    *
    * Vivado needs libudev preloaded on some distros; mirror the shell scripts'
    * LD_PRELOAD shim when the invoked tool looks like a Xilinx binary.
    */
  def runCmd(
    cmd: Seq[String],
    cwd: os.Path,
    dryRun: Boolean,
    stage: String
  ): Unit = {
    println(s"\n[$stage] (cwd=$cwd)\n    ${cmd.mkString(" ")}")
    if (dryRun) return
    val libudev = os.Path("/lib/x86_64-linux-gnu/libudev.so.1")
    val xilinxTool =
      cmd.headOption.exists { c =>
        val n = c.toLowerCase
        n.contains("vivado") || n.endsWith("xvlog") || n.endsWith("xelab") ||
        n.endsWith("xsim")
      }
    val extraEnv: Map[String, String] =
      if (os.exists(libudev) && xilinxTool)
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

  /** Extract a classpath resource to a real temp file, returning its path.
    * URL.getPath is percent-encoded and unusable inside a jar, so tools that
    * need a real -source / file path get a copy on disk.
    */
  def extractResource(resourcePath: String, suffix: String): String = {
    val url = getClass.getClassLoader.getResource(resourcePath)
    require(url != null, s"classpath resource not found: $resourcePath")
    os.temp(url.openStream().readAllBytes(), suffix = suffix).toString
  }

  /** Resolve a Xilinx tool (vivado, xvlog, xelab, xsim): prefer
    * $XILINX_VIVADO/bin/<name>, else the bare name on PATH.
    */
  def tool(env: Map[String, String], name: String): String =
    env
      .get("XILINX_VIVADO")
      .map(p => (os.Path(p) / "bin" / name).toString)
      .getOrElse(name)
}
