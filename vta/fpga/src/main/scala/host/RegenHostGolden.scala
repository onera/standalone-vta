package fpga.host

import fpga.host.models.HwConfig
import fpga.host.parsers.ConfigParser

/** Dev tool: snapshot the [[GenNnBaremetal]] port output into the committed
  * host-golden fixture directories.
  *
  * Usage: fpga.host.RegenHostGolden <binRoot> <goldenRoot> binRoot - directory
  * produced by the Mill `compilerOutputs` task; layout:
  * <binRoot>/<case>/compiler_output/ goldenRoot - committed fixture root:
  * vta/fpga/src/test/resources/host-golden/
  *
  * For each of the 4 cases the tool regenerates gen/, gen-debug/ and gen-sd/
  * using the production [[GenNnBaremetal.generate]] so the stored golden is a
  * faithful snapshot of the tool under test.
  *
  * Run via Mill: ./mill vta.fpga.regenHostGolden
  */
object RegenHostGolden {

  private case class CaseDef(
      name: String,
      configName: String,
      ddrBaseHex: String,
      modelDesc: String
  ) {
    def ddrBase: Long =
      java.lang.Long.parseLong(ddrBaseHex.stripPrefix("0x"), 16)
  }

  private val cases = Seq(
    CaseDef(
      "lenet5-default",
      "vta_config.json",
      "0x0",
      "lenet5.onnx (QLinearConv x5 + MaxPool x2, 28x28 input)"
    ),
    CaseDef(
      "lenet5-w8b",
      "vta_w8b.json",
      "0x10000000",
      "lenet5.onnx (QLinearConv x5 + MaxPool x2, 28x28 input)"
    ),
    CaseDef(
      "qyolo-default",
      "vta_config.json",
      "0x0",
      "qyolo_pattern.onnx (RepConv/ReLU conv + maxpool + concat)"
    ),
    CaseDef(
      "qyolo-w8b",
      "vta_w8b.json",
      "0x10000000",
      "qyolo_pattern.onnx (RepConv/ReLU conv + maxpool + concat)"
    )
  )

  private def canon(s: String, compDir: os.Path): String =
    s.replace(compDir.toString, "@COMP_DIR@")

  private def withTempDir[A](prefix: String)(f: os.Path => A): A = {
    val tmp = os.Path(
      java.nio.file.Files.createTempDirectory(prefix).toAbsolutePath
    )
    try f(tmp)
    finally os.remove.all(tmp)
  }

  /** Regenerate all golden sub-dirs for the given case definition. */
  private def regenCase(
      cd: CaseDef,
      binRoot: os.Path,
      goldenRoot: os.Path,
      configRoot: os.Path
  ): Unit = {
    val comp = binRoot / cd.name / "compiler_output"
    require(
      os.isDir(comp),
      s"compiler_output not found: $comp  (run ./mill vta.fpga.test.compilerOutputs first)"
    )

    val cfgPath = configRoot / cd.configName
    val cfg: HwConfig.ConfigParams = ConfigParser.load(cfgPath.toString)

    val caseDir = goldenRoot / cd.name
    os.makeDir.all(caseDir)

    // CASE.txt
    os.write.over(
      caseDir / "CASE.txt",
      s"case=${cd.name}\nconfig=${cd.configName}\nddr_base=${cd.ddrBaseHex}\nmodel=${cd.modelDesc}\n"
    )

    // config.json - copy from the workspace config/ dir
    os.copy(
      cfgPath,
      caseDir / "config.json",
      replaceExisting = true,
      createFolders = true
    )

    // gen/ - plain generate, no flags
    val genDir = caseDir / "gen"
    os.remove.all(genDir)
    os.makeDir.all(genDir)
    withTempDir("regen-gen-") { tmp =>
      GenNnBaremetal.generate(
        compDir = comp.toString,
        outdir = tmp.toString,
        ddrBase = cd.ddrBase,
        cfg = cfg
      )
      for (
        f <- Seq(
          "vta_hw_config.h",
          "nn_ddr_map.h",
          "nn_exec_plan.h",
          "load_nn_static.tcl",
          "load_nn.tcl",
          "load_input.tcl",
          "nn_bin_data.S",
          "nn_vta_sections.ld"
        )
      )
        os.write.over(genDir / f, canon(os.read(tmp / f), comp))
    }

    // gen-debug/ - emitCpuCheck + refDir = comp
    val genDebugDir = caseDir / "gen-debug"
    os.remove.all(genDebugDir)
    os.makeDir.all(genDebugDir)
    withTempDir("regen-debug-") { tmp =>
      GenNnBaremetal.generate(
        compDir = comp.toString,
        outdir = tmp.toString,
        ddrBase = cd.ddrBase,
        cfg = cfg,
        emitCpuCheck = true,
        refDir = Some(comp.toString)
      )
      // debug maps: NO canonicalization (tests compare raw)
      for (f <- Seq("nn_debug_map.h", "nn_cpu_debug_map.h"))
        os.copy(
          tmp / f,
          genDebugDir / f,
          replaceExisting = true,
          createFolders = true
        )
      // augmented loaders: canonicalize the absolute compDir path
      for (f <- Seq("nn_bin_data.S", "nn_vta_sections.ld"))
        os.write.over(genDebugDir / f, canon(os.read(tmp / f), comp))
    }

    // gen-sd/ - emitSdManifest = true
    val genSdDir = caseDir / "gen-sd"
    os.remove.all(genSdDir)
    os.makeDir.all(genSdDir)
    withTempDir("regen-sd-") { tmp =>
      GenNnBaremetal.generate(
        compDir = comp.toString,
        outdir = tmp.toString,
        ddrBase = cd.ddrBase,
        cfg = cfg,
        emitSdManifest = true
      )
      // SD manifest: NO canonicalization
      os.copy(
        tmp / "nn_sd_manifest.h",
        genSdDir / "nn_sd_manifest.h",
        replaceExisting = true,
        createFolders = true
      )
      // staged_files.txt: sorted relative paths under sd_card/
      val staged = os
        .walk(tmp / "sd_card")
        .filter(os.isFile)
        .map(_.relativeTo(tmp / "sd_card").toString)
        .sorted
      os.write.over(
        genSdDir / "staged_files.txt",
        staged.mkString("", "\n", "\n")
      )
    }

    println(s"[regen] done: ${cd.name}")
  }

  def main(args: Array[String]): Unit = {
    require(
      args.length >= 2,
      "Usage: RegenHostGolden <binRoot> <goldenRoot>"
    )
    val binRoot = os.Path(args(0))
    val goldenRoot = os.Path(args(1))
    // Config JSON files live under config/ relative to the workspace root.
    // Mill runs this with workingDir = workspace root.
    val configRoot = os.pwd / "config"

    for (cd <- cases) {
      println(s"[regen] processing: ${cd.name} ...")
      regenCase(cd, binRoot, goldenRoot, configRoot)
    }
    println("[regen] all cases regenerated.")
  }
}
