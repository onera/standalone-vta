package fpga.host.checkers
import fpga.host.models._
import fpga.host.transform.MemoryLayout
import fpga.host.parsers.{ConfigParser, LayerParser}
import scopt.OParser
import vta.parsers.Dependency.loadDependencyInfo

/** Static DRAM-layout guard for the VTA baremetal path.
  *
  * Builds the exact layout the generator emits and runs the layout guard
  * checks: buffer overlaps, static binaries fitting their slots, CPU-op outputs
  * fitting the VTA region they feed, and - with maxAddr - every allocation
  * fitting the board's mapped DRAM.
  *
  * Translated from host/audit_dram.py.
  */
object AuditDram {

  /** Run all layout guards. Returns 0 (PASS) or 1 (FAIL).
    *
    * @param compDir
    *   absolute path to the compiler output directory
    * @param ddrBase
    *   physical DDR base address
    * @param configJson
    *   path to vta_config.json (null = DefaultPynqConfig)
    * @param maxAddr
    *   if given, verify all allocations fit below this address
    */
  def audit(
      compDir: String,
      ddrBase: Long,
      configJson: String,
      maxAddr: Option[Long]
  ): Int = {
    val cfg = ConfigParser.load(configJson)
    val dep =
      loadDependencyInfo(s"$compDir/dependency.csv")

    val layers = LayerParser.collectLayers(compDir, dep)

    val suffixToIdx = Model.suffixToIdx(layers)

    val (cpuOut, _, cpuScratch) =
      MemoryLayout.buildCpuOutAddrs(dep, layers, ddrBase, suffixToIdx, compDir)

    println(
      f"=== VTA DRAM audit (base 0x${ddrBase}%08X, block ${cfg.blockSize}) ==="
    )

    // Mirror run_guard_checks from audit_dram.py: every check always runs
    // (Checks.runGuards builds a strict Seq), then folds to a verdict.
    val ok = Checks.runGuards(
      dep,
      layers,
      ddrBase,
      suffixToIdx,
      cpuOut,
      cfg.blockSize,
      HwConfig.elemBytes(cfg.logInpWidth),
      cpuScratch,
      compDir,
      maxAddr
    )

    Checks.printSummary(layers, ddrBase)

    if (maxAddr.isEmpty)
      println(
        "\nNote: pass --max-addr <hex> to verify allocations fit mapped DRAM."
      )

    println("\nRESULT: " + (if (ok) "PASS" else "FAIL"))
    if (ok) 0 else 1
  }

  private case class Opts(
      compDir: String = "",
      ddrBase: String = "0x0",
      configJson: Option[String] = None,
      maxAddr: Option[String] = None
  )

  private val argParser: OParser[_, Opts] = {
    val b = OParser.builder[Opts]
    import b._
    OParser.sequence(
      programName("auditDram"),
      head("auditDram", "VTA static DRAM layout audit"),
      arg[String]("<compiler_output_dir>")
        .action((x, c) => c.copy(compDir = x))
        .text("compiler output directory"),
      opt[String]("ddr-base")
        .action((x, c) => c.copy(ddrBase = x))
        .text("DDR base address (hex, default 0x0)"),
      opt[String]("config-json")
        .action((x, c) => c.copy(configJson = Some(x)))
        .text("path to vta_config.json (default: Chisel DefaultPynqConfig)"),
      opt[String]("max-addr")
        .action((x, c) => c.copy(maxAddr = Some(x)))
        .text("verify allocations fit below this DDR address (hex)")
    )
  }

  def main(args: Array[String]): Unit =
    OParser.parse(argParser, args, Opts()) match {
      case Some(o) =>
        val compDir = new java.io.File(o.compDir).getAbsolutePath
        val ddrBase = BigInt(o.ddrBase, 16).toLong
        val maxAddr = o.maxAddr.map(BigInt(_, 16).toLong)
        sys.exit(audit(compDir, ddrBase, o.configJson.orNull, maxAddr))
      case _ => sys.exit(1)
    }
}
