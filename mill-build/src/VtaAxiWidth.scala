package vtabuild

/** Reads the DRAM-side AXI master width out of a VTA config JSON.
  *
  * The width used to be the global `-Dvta.axi.bits` property. Because that was
  * not part of a config's identity, a 64-bit and a 128-bit build of the *same*
  * config shared `out/targets/<config>/<board>/synth.dest` and silently
  * overwrote each other. It is now declared by the config file, so the two are
  * separate cross keys with separate caches.
  *
  * Kept out of build.mill so it is ordinary, testable Scala, and deliberately
  * depends on nothing from `build`: it takes a path. (Reusing
  * vta.parsers.ConfigParser is not possible here - that lives in a task result
  * of this build, not on the meta-build classpath.)
  */
object VtaAxiWidth {

  /** Widths the VTA shell has a Chisel config for: DefaultPynqConfig (64) and
    * FpgaExtWidthConfig (128), in modules/hardware/src/main/scala/shell.
    */
  val Supported: Set[Int] = Set(64, 128)

  /** Log2 of the width used when a config file does not declare one. */
  val DefaultLogAxiBits: Int = 6

  /** Suffix marking a config as the 128-bit variant of its sibling. */
  val WideSuffix: String = "_a128"

  private val LogAxiBitsLine = """"LOG_AXI_BITS"\s*:\s*(\d+)""".r.unanchored

  /** Log2 of the AXI width declared by the config at `configPath`, or
    * [[DefaultLogAxiBits]] when the key is absent.
    *
    * Absent meaning 64 is deliberate: it lets the config files that predate
    * this scheme stay byte-identical, so their content hash - and the synthesis
    * cached against it - survives.
    */
  def logAxiBitsOf(configPath: os.Path): Int = {
    require(os.exists(configPath), s"no VTA config file at $configPath")
    os.read
      .lines(configPath)
      .collectFirst { case LogAxiBitsLine(bits) => bits.toInt }
      .getOrElse(DefaultLogAxiBits)
  }

  /** AXI width in bits declared by the config at `configPath`. */
  def axiBitsOf(configPath: os.Path): Int = {
    val bits = 1 << logAxiBitsOf(configPath)
    require(
      Supported(bits),
      s"$configPath declares LOG_AXI_BITS giving a $bits-bit AXI master; " +
        s"only ${Supported.toSeq.sorted.mkString(" and ")} have a shell config"
    )
    bits
  }

  /** Fail on a leftover `-Dvta.axi.bits`, naming the config to use instead.
    *
    * The option is gone rather than ignored on purpose: a flag that is read by
    * nothing produces a build you believe is something else, which is how the
    * 128-bit SD-card staging leak happened during the October campaign.
    */
  def rejectLegacyProperty(configKey: String): Unit =
    sys.props.get("vta.axi.bits").filter(_.nonEmpty).foreach { value =>
      val advice =
        if (configKey.endsWith(WideSuffix))
          s"$configKey is already the 128-bit config"
        else
          s"use the $configKey$WideSuffix config for a 128-bit build"
      sys.error(
        s"-Dvta.axi.bits=$value is no longer read: the AXI width comes from " +
          s"the config file now, so that the two widths cache separately. " +
          s"Here, $advice. Drop the flag with `./mill configure vta.axi.bits=`."
      )
    }
}
