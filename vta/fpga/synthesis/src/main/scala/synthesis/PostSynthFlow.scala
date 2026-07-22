package fpga.synthesis

import scopt.OParser

/** End-to-end post-synthesis gate-level flow: OOC-synthesize the emitted shell,
  * run the behavioral control and gate-level xsim legs, and strb-compare the
  * gate-level OUT against the fsim golden.
  *
  * Owns the stage sequencing and both verdicts so the Mill task stays pure
  * build wiring (resolve cached inputs, emit sources, hand over a dest dir,
  * launch this). Composes the same OocNetlist / RunXsim / CompareOut entry
  * points the raw Mill tasks expose, called in-process.
  *
  * Inputs must already exist: the emitted shell (--shell-dir) or an
  * already-synthesized netlist (--netlist, skips the OOC stage), the post-synth
  * TB (--tb), the compiled model (--comp-dir) and the fsim `--dump-layers`
  * goldens (--golden-dir).
  */
object PostSynthFlow {

  def main(args: Array[String]): Unit = sys.exit(run(args))

  private case class Opts(
    board: String = "zcu104",
    shellDir: String = "",
    netlist: String = "",
    tb: String = "",
    compDir: String = "",
    goldenDir: String = "",
    out: String = "",
    layers: String = "",
    top: String = "VTAXilinxShell",
    vivado: String = Vivado.tool(sys.env, "vivado")
  )

  private val argParser: OParser[_, Opts] = {
    val b = OParser.builder[Opts]
    import b._
    OParser.sequence(
      programName("postSynthFlow"),
      head("postSynthFlow", "VTA post-synthesis gate-level check"),
      opt[String]("board")
        .action((x, c) => c.copy(board = x))
        .text("board name under vta/fpga/boards (default zcu104)"),
      opt[String]("shell-dir")
        .action((x, c) => c.copy(shellDir = x))
        .text(
          "emitted debug-xilinx shell dir (the OOC synth input; unused with --netlist)"
        ),
      opt[String]("netlist")
        .action((x, c) => c.copy(netlist = x))
        .text(
          "an already-synthesized <top>_funcsim.v: skip the OOC synth stage and use it as the gate-level DUT"
        ),
      opt[String]("tb")
        .required()
        .action((x, c) => c.copy(tb = x))
        .text("emitted post-synth TB dir"),
      opt[String]("comp-dir")
        .required()
        .action((x, c) => c.copy(compDir = x))
        .text("compiler output dir"),
      opt[String]("golden-dir")
        .required()
        .action((x, c) => c.copy(goldenDir = x))
        .text("fsim --dump-layers output dir"),
      opt[String]("out")
        .required()
        .action((x, c) => c.copy(out = x))
        .text("run dir for the netlist + both xsim legs"),
      opt[String]("layers")
        .required()
        .action((x, c) => c.copy(layers = x))
        .text("layer subset, comma-separated, in emit order"),
      opt[String]("top")
        .action((x, c) => c.copy(top = x))
        .text("synthesized top module (default VTAXilinxShell)"),
      opt[String]("vivado")
        .action((x, c) => c.copy(vivado = x))
        .text(
          "vivado executable (default $XILINX_VIVADO/bin/vivado, else vivado on PATH)"
        ),
      checkConfig(c =>
        if (c.netlist.nonEmpty || c.shellDir.nonEmpty) success
        else failure("pass --shell-dir (OOC-synthesize) or --netlist (reuse)")
      )
    )
  }

  /** True when both legs wrote byte-identical AXI write streams, i.e. the
    * gate-level netlist computes exactly what the behavioral RTL does.
    */
  def gatesMatchRtl(behavWrites: os.Path, netWrites: os.Path): Boolean =
    os.exists(behavWrites) && os.exists(netWrites) &&
      java.util.Arrays
        .equals(os.read.bytes(behavWrites), os.read.bytes(netWrites))

  def run(argv: Array[String]): Int = {
    val o = OParser.parse(argParser, argv, Opts()) match {
      case Some(parsed) => parsed
      case _            => return 1
    }
    val out = os.Path(o.out, os.pwd)
    val oocDir = out / "ooc-netlist"
    val behavDir = out / "xsim-behav"
    val netDir = out / "xsim-net"
    val nLayers = o.layers.split(",").count(_.trim.nonEmpty)

    // 1. OOC-synthesize the gate-level netlist of the board-faithful top, or
    // reuse an already-synthesized one (--netlist, e.g. the cached
    // vta.fpga.targets[config,board].oocNetlist output).
    val funcsim =
      if (o.netlist.nonEmpty) {
        val nl = os.Path(o.netlist, os.pwd)
        println(s"[postSynth] reusing netlist $nl (OOC synth skipped)")
        nl
      } else {
        val rcOoc = OocNetlist.run(
          Array(
            "--board",
            o.board,
            "--sv-dir",
            o.shellDir,
            "--top",
            o.top,
            "--out",
            oocDir.toString,
            "--vivado",
            o.vivado
          )
        )
        if (rcOoc != 0) return rcOoc
        oocDir / s"${o.top}_funcsim.v"
      }

    // 2. Behavioral control leg, then 3. the gate-level DUT leg.
    val rcBehav = RunXsim.run(
      Array(
        "--behavioral",
        "--tb",
        o.tb,
        "--out",
        behavDir.toString,
        "--layers",
        nLayers.toString
      )
    )
    if (rcBehav != 0) return rcBehav
    val rcNet = RunXsim.run(
      Array(
        "--netlist",
        funcsim.toString,
        "--tb",
        o.tb,
        "--out",
        netDir.toString,
        "--layers",
        nLayers.toString
      )
    )
    if (rcNet != 0) return rcNet

    // 4. The flow's primary verdict: identical write streams mean synthesis is
    // faithful, so any OUT-vs-golden failure below cannot be a synthesis bug.
    val behavWrites = behavDir / "writes.log"
    val netWrites = netDir / "writes.log"
    val gatesOk = gatesMatchRtl(behavWrites, netWrites)
    if (gatesOk)
      println(
        "[postSynth] gates == RTL: behavioral and netlist writes.log are byte-identical"
      )
    else
      println(
        "[postSynth] WARNING: behavioral and netlist writes.log DIFFER - " +
          "suspect a synthesis-level divergence"
      )

    // 5. Strb-aware compare of the gate-level OUT against the fsim golden.
    val rcCmp = CompareOut.run(
      Array(
        "--writes",
        netWrites.toString,
        "--layers",
        o.layers,
        "--compiler-out",
        o.compDir,
        "--golden-dir",
        o.goldenDir
      )
    )
    if (rcCmp != 0) {
      val diagnosis =
        if (gatesOk)
          "the two xsim legs are byte-identical, so this is an RTL-vs-fsim-golden " +
            "divergence, NOT a synthesis problem"
        else
          "the two xsim legs also differ, so synthesis is implicated"
      println(
        s"""
           |[postSynth] FAILED: OUT compare found mismatches (per-layer verdicts above);
           |            $diagnosis.
           |  netlist writes : $netWrites
           |  behavioral     : $behavWrites
           |  fsim goldens   : ${o.goldenDir}
           |  artifacts      : $out""".stripMargin
      )
      return rcCmp
    }
    println(s"[postSynth] OK: netlist OUT matches the fsim golden -> $out")
    0
  }
}
