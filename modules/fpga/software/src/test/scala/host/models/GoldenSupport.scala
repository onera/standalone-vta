package fpga.host.models

object GoldenSupport {
  val goldenRoot: os.Path = {
    val url = getClass.getClassLoader.getResource("host-golden")
    require(url != null, "host-golden resources not on classpath")
    os.Path(java.nio.file.Paths.get(url.toURI))
  }
  // generated compiler_output root, produced by the Mill `compilerOutputs` task
  // (modules/fpga/package.mill). Layout: host-golden-bin/<case>/compiler_output/...
  // The task exposes it through the test JVM's forkEnv (VTA_HOST_GOLDEN_BIN) so
  // it runs only when tests run; fall back to the classpath for legacy runners.
  val binRoot: os.Path = {
    sys.env
      .get("VTA_HOST_GOLDEN_BIN")
      .map(os.Path(_))
      .getOrElse {
        val url = getClass.getClassLoader.getResource("host-golden-bin")
        require(
          url != null,
          "host-golden-bin not available - set VTA_HOST_GOLDEN_BIN or run " +
            "`./mill modules.fpga.software.test` (its goldenOutputs task " +
            "compiles the ONNX models into compiler_output)"
        )
        os.Path(java.nio.file.Paths.get(url.toURI))
      }
  }
  final case class Case(
    name: String,
    dir: os.Path,
    comp: os.Path,
    gen: os.Path,
    cfg: os.Path,
    ddrBase: Long
  )
  def loadCase(name: String): Case = {
    val dir = goldenRoot / name
    val ddrHex = os.read
      .lines(dir / "CASE.txt")
      .find(_.startsWith("ddr_base="))
      .get
      .stripPrefix("ddr_base=")
      .stripPrefix("0x")
    Case(
      name,
      dir,
      binRoot / name / "compiler_output",
      dir / "gen",
      dir / "config.json",
      java.lang.Long.parseLong(ddrHex, 16)
    )
  }

  def sandbox(parts: String*): os.Path = {
    val d = parts.foldLeft(os.pwd / "build")(_ / _)
    os.remove.all(d)
    os.makeDir.all(d)
    d
  }

  /** The reference dir used by golden generation for this case (mirrors
    * RegenHostGolden.refDirFor). Nested under compDir on purpose - the golden
    * fixtures have no reference, so this deliberately does not exist on disk.
    */
  def refDirFor(c: Case): os.Path = c.comp / "reference"

  def assertGolden(c: Case, fileName: String, actual: String): Unit = {
    // @REF_DIR@ MUST be replaced first: refDirFor(c) nests under c.comp, so
    // replacing c.comp first would consume the prefix and leave nothing for
    // the @REF_DIR@ pattern to match (see RegenHostGolden.canon).
    val canon = actual
      .replace(refDirFor(c).toString, "@REF_DIR@")
      .replace(c.comp.toString, "@COMP_DIR@")
    val expected = os.read(c.gen / fileName)
    if (canon != expected) {
      val a = os.pwd / "golden-actual" / c.name / fileName
      os.write.over(a, canon, createFolders = true)
      throw new AssertionError(
        s"$fileName differs from golden for ${c.name}; actual at $a"
      )
    }
  }
  val cases: Seq[String] =
    Seq("lenet5-default", "lenet5-w8b", "qyolo-default", "qyolo-w8b")
}
