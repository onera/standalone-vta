package fpga.synthesis

import scopt.OParser

/** Compile + run VTAPostSynthTb under Vivado xsim. Ported from
  * postsynth/run_xsim.sh (behavior-faithful, including the two caches).
  *
  * --behavioral the emitted behavioral shell (control; should reach DONE)
  * --netlist <funcsim.v> the post-synth gate-level netlist (the DUT)
  *
  * The netlist leg compiles ONLY the TB wrapper + funcsim netlist + glbl
  * (excluding the behavioral VTAShell.sv the netlist replaces); the behavioral
  * leg compiles all emitted SV. Two caches: --reuse-elab skips xvlog+xelab and
  * runs the cached snapshot; the big netlist parse is skipped when the netlist
  * path+mtime is unchanged (.nlxvlog.stamp).
  */
object RunXsim {

  def main(args: Array[String]): Unit = sys.exit(run(args))

  private case class Opts(
    mode: String = "", // behavioral | netlist
    netlist: String = "",
    tb: Option[String] = None,
    out: Option[String] = None,
    layers: Int = 3,
    timeoutNs: Long = 2000000000L,
    writes: String = "writes.log",
    wave: Boolean = false,
    waveNs: Long = 250000L,
    reuseElab: Boolean = false,
    dryRun: Boolean = false
  )

  private val argParser: OParser[_, Opts] = {
    val b = OParser.builder[Opts]
    import b._
    OParser.sequence(
      programName("runXsim"),
      opt[Unit]("behavioral").action((_, c) => c.copy(mode = "behavioral")),
      opt[String]("netlist").action((x, c) =>
        c.copy(mode = "netlist", netlist = x)
      ),
      opt[String]("tb").action((x, c) => c.copy(tb = Some(x))),
      opt[String]("out").required().action((x, c) => c.copy(out = Some(x))),
      opt[Int]("layers").action((x, c) => c.copy(layers = x)),
      opt[Long]("timeout-ns").action((x, c) => c.copy(timeoutNs = x)),
      opt[String]("writes").action((x, c) => c.copy(writes = x)),
      opt[Unit]("wave").action((_, c) => c.copy(wave = true)),
      opt[Long]("wave-ns").action((x, c) => c.copy(wave = true, waveNs = x)),
      opt[Unit]("reuse-elab").action((_, c) => c.copy(reuseElab = true)),
      opt[Unit]("dry-run").action((_, c) => c.copy(dryRun = true))
    )
  }

  /** The planned command strings + derived params, for --dry-run and tests. */
  final case class Plan(mode: String, idxWidth: Int, commands: Seq[String])

  private def idxWidth(layers: Int): Int =
    math.max(
      1,
      math.ceil(math.log(math.max(layers, 2).toDouble) / math.log(2.0)).toInt
    )

  /** Build the plan without running anything. */
  def planFor(argv: Array[String]): Plan = {
    val o =
      OParser.parse(argParser, argv, Opts()).getOrElse(sys.error("bad args"))
    require(o.mode.nonEmpty, "pass --behavioral or --netlist <funcsim.v>")
    val env = sys.env
    val xvlog = Vivado.tool(env, "xvlog")
    val xelab = Vivado.tool(env, "xelab")
    val bits = idxWidth(o.layers)
    val tb = os.Path(
      o.tb.getOrElse {
        val repoRoot = env.get("VTA_ROOT").map(os.Path(_)).getOrElse(os.pwd)
        (repoRoot / "build" / "emitted" / "vta-postsynth-tb").toString
      },
      os.pwd
    )
    val simTop = Vivado.extractResource("synthesis/sim_top.sv", "-sim_top.sv")
    val dbg = if (o.wave) "-debug all" else "-debug typical"
    val cmds = scala.collection.mutable.ArrayBuffer[String]()
    if (o.mode == "behavioral") {
      cmds += s"$xvlog -d ENABLE_INITIAL_MEM_ -d LAYERIDX_W=$bits -sv $simTop ${tb}/*.sv"
      cmds += s"$xelab sim_top $dbg -s snap --timescale 1ns/1ps"
    } else {
      val glbl = env
        .get("XILINX_VIVADO")
        .map(v => s"$v/data/verilog/src/glbl.v")
        .getOrElse("glbl.v")
      cmds += s"$xvlog -d ENABLE_INITIAL_MEM_ -d LAYERIDX_W=$bits -sv $simTop <tb-files>"
      cmds += s"$xvlog ${o.netlist} $glbl"
      cmds += s"$xelab sim_top glbl $dbg -L unisims_ver -L secureip -s snap --timescale 1ns/1ps"
    }
    Plan(o.mode, bits, cmds.toSeq)
  }

  def run(argv: Array[String]): Int = {
    val o = OParser.parse(argParser, argv, Opts()) match {
      case Some(parsed) => parsed
      case _            => return 1
    }
    if (o.mode.isEmpty) {
      System.err.println("ERROR: pass --behavioral or --netlist <funcsim.v>");
      return 1
    }
    val env = sys.env
    if (!o.dryRun && env.get("XILINX_VIVADO").forall(_.isEmpty)) {
      System.err.println(
        "ERROR: XILINX_VIVADO unset - source Vivado settings64.sh first"
      )
      return 1
    }
    val repoRoot = env.get("VTA_ROOT").map(os.Path(_)).getOrElse(os.pwd)
    val xvlog = Vivado.tool(env, "xvlog")
    val xelab = Vivado.tool(env, "xelab")
    val xsim = Vivado.tool(env, "xsim")

    val tb = os.Path(
      o.tb.getOrElse(
        (repoRoot / "build" / "emitted" / "vta-postsynth-tb").toString
      ),
      os.pwd
    )
    if (!o.dryRun) {
      if (!os.exists(tb)) {
        System.err.println(s"ERROR: TB emit dir not found: $tb"); return 1
      }
      if (!os.exists(tb / "VTAPostSynthTb.sv")) {
        System.err.println(s"ERROR: $tb/VTAPostSynthTb.sv missing"); return 1
      }
    }
    val out = os.Path(o.out.get, os.pwd)
    val bits = idxWidth(o.layers)
    val simTop = Vivado.extractResource("synthesis/sim_top.sv", "-sim_top.sv")
    val dbg = if (o.wave) "-debug all" else "-debug typical"

    if (o.dryRun) {
      planFor(argv).commands.foreach(c => println(s"[dry-run] $c")); return 0
    }

    os.makeDir.all(out)
    println(
      s"[runXsim] mode=${o.mode} tb=$tb out=$out layers=${o.layers} (idxW=$bits)"
    )

    if (o.mode == "netlist" && !os.exists(os.Path(o.netlist, os.pwd))) {
      System.err.println(
        s"ERROR: netlist not found: ${os.Path(o.netlist, os.pwd)}"
      )
      return 1
    }

    val tbFiles: Seq[String] = {
      val fixed =
        Seq("VTAPostSynthTb.sv", "VtaHostDriver.sv", "MultiMemAxiClient.sv")
          .map(f => (tb / f).toString)
      val mems = os
        .list(tb)
        .filter(p => p.last.startsWith("memory_") && p.ext == "sv")
        .map(_.toString)
      fixed ++ mems.sorted
    }

    val snapReady = os.exists(out / "xsim.dir" / "snap")
    if (o.reuseElab && snapReady) {
      println(
        "[runXsim] --reuse-elab: skipping xvlog+xelab, running the cached snapshot"
      )
    } else if (o.mode == "behavioral") {
      Vivado.runCmd(
        Seq(
          xvlog,
          "-d",
          "ENABLE_INITIAL_MEM_",
          "-d",
          s"LAYERIDX_W=$bits",
          "-sv",
          simTop
        )
          ++ os.list(tb).filter(_.ext == "sv").map(_.toString).sorted,
        cwd = out,
        dryRun = false,
        stage = "xvlog (behavioral)"
      )
      Vivado.runCmd(
        Seq(xelab, "sim_top") ++ dbg
          .split(" ") ++ Seq("-s", "snap", "--timescale", "1ns/1ps"),
        cwd = out,
        dryRun = false,
        stage = "xelab"
      )
    } else {
      val netlist = os.Path(o.netlist, os.pwd)
      val glbl = env
        .get("XILINX_VIVADO")
        .map(v => s"$v/data/verilog/src/glbl.v")
        .getOrElse("glbl.v")
      Vivado.runCmd(
        Seq(
          xvlog,
          "-d",
          "ENABLE_INITIAL_MEM_",
          "-d",
          s"LAYERIDX_W=$bits",
          "-sv",
          simTop
        ) ++ tbFiles,
        cwd = out,
        dryRun = false,
        stage = "xvlog (tb)"
      )
      val stamp = s"$netlist ${os.mtime(netlist)}"
      val stampFile = out / ".nlxvlog.stamp"
      val cached =
        os.exists(stampFile) && os.read(stampFile).trim == stamp && os.exists(
          out / "xsim.dir" / "work"
        )
      if (cached)
        println(
          "[runXsim] netlist unchanged -> reusing cached parse (xvlog skipped)"
        )
      else {
        Vivado.runCmd(
          Seq(xvlog, netlist.toString, glbl),
          cwd = out,
          dryRun = false,
          stage = "xvlog (netlist)"
        )
        os.write.over(stampFile, stamp)
      }
      Vivado.runCmd(
        Seq(xelab, "sim_top", "glbl") ++ dbg.split(" ")
          ++ Seq(
            "-L",
            "unisims_ver",
            "-L",
            "secureip",
            "-s",
            "snap",
            "--timescale",
            "1ns/1ps"
          ),
        cwd = out,
        dryRun = false,
        stage = "xelab (netlist)"
      )
    }

    val runCmdTcl = if (o.wave) s"run ${o.waveNs} ns" else "run -all"
    val waveTcl =
      s"""open_vcd wave.vcd
         |log_vcd [get_objects -recursive /sim_top/dut/driver/*]
         |log_vcd [get_objects /sim_top/*]
         |log_vcd [get_objects /sim_top/dut/*]
         |log_vcd [get_objects /sim_top/dut/vta/*]
         |$runCmdTcl
         |flush_vcd
         |close_vcd
         |quit
         |""".stripMargin
    os.write.over(out / "wave.tcl", waveTcl)

    val simLog = new StringBuffer
    val res = os
      .proc(
        xsim,
        "snap",
        "-testplusarg",
        s"WRITES=${o.writes}",
        "-testplusarg",
        s"TIMEOUT_NS=${o.timeoutNs}",
        "-wdb",
        "wave.wdb",
        "-tclbatch",
        "wave.tcl"
      )
      .call(
        cwd = out,
        check = false,
        stdout = os.ProcessOutput.Readlines { l =>
          println(l); simLog.append(l).append('\n')
        },
        stderr = os.ProcessOutput.Readlines { l =>
          System.err.println(l); simLog.append(l).append('\n')
        }
      )
    os.write.over(out / "sim.log", simLog.toString)
    println(s"[runXsim] done -> $out/{${o.writes},sim.log,wave.vcd,wave.wdb}")
    simLog.toString.linesIterator
      .filter(_.matches(".*SIM_TOP: (DONE|WEDGE|TIMEOUT).*"))
      .foreach(println)
    res.exitCode
  }
}
