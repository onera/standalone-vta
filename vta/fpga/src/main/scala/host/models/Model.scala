package fpga.host.models

import vta.models.CompilerOutputModel.MemoryRegion

/** Isolation-check data for one VTA layer: golden-file paths and the
  * pre-allocated DRAM addresses for the per-layer in/out reference blobs. All
  * fields default to "absent" (empty string / 0) when no golden file was found;
  * [[Option]][[[LayerCheck]]] being `None` means the layer has no check region
  * at all (non-check-mode run).
  */
case class LayerCheck(
    inRefFile: String,
    inRefAddr: Long,
    inRefSize: Long,
    inDstAddr: Long,
    outRefFile: String,
    outRefAddr: Long,
    outRefSize: Long
)

/** Host-generator data model and path/name helpers.
  *
  * Compiler-output parsing and byte-sizing are reused from [[vta.parsers.]]
  * (memory_addresses regions and dependency.csv); this object only adds the
  * baremetal-specific layer wrapper, static-load policy, and C/asm formatting
  * helpers. Translated from nnbaremetal/model.py.
  */
object Model {

  /** Order static model buffers are pre-loaded into the ELF / Tcl. */
  val staticLoadOrder: Seq[String] = Seq("INSN", "UOP", "WGT", "ACC")
  val insnBytes: Int = 16
  val incbinAlignLog2: Int = 6

  val binBaseName: Map[String, String] = Map(
    "INP" -> "input",
    "WGT" -> "weight",
    "ACC" -> "accumulator",
    "OUT" -> "out_init",
    "UOP" -> "uop",
    "INSN" -> "instructions"
  )

  /** A VTA layer: its compiler suffix, per-buffer regions (keyed by buffer
    * type; missing buffers are `MemoryRegion(name, 0, None, 0)`), backing
    * binary paths, and the reshape policy. `reshapeInfo` defaults to "im2row"
    * so an unannotated layer keeps the conv behaviour (ACC = static bias).
    */
  case class LayerInfo(
      suffix: String,
      mem: Map[String, MemoryRegion],
      binFiles: Map[String, String],
      reshapeInfo: String = "im2row",
      // Isolation-check golden region, populated only with --emit-layer-check
      // (written by DebugEmit.assignLayerCheckMemoryRegions). None in non-check mode.
      check: Option[LayerCheck] = None
  )

  /** 8-digit hex address literal, e.g. `0x10000000` (no type suffix). */
  def hexAddr(v: Long): String = f"0x${v}%08X"

  /** Same address as a C `unsigned` literal, e.g. `0x10000000u`. */
  def hex32(v: Long): String = hexAddr(v) + "u"

  /** os.path.isfile equivalent: exists and is a regular file. */
  def isFile(path: String): Boolean = {
    val p = os.Path(path, os.pwd)
    os.exists(p) && os.isFile(p)
  }

  /** ELF section name for a statically pre-loaded VTA buffer. */
  def sectionName(i: Int, bufType: String): String =
    s".vta_l${i}_${bufType.toLowerCase}"

  /** ELF section name for the per-layer golden input reference. */
  def inRefSection(i: Int): String = s".vta_l${i}_inref"

  /** ELF section name for the per-layer golden output reference. */
  def outRefSection(i: Int): String = s".vta_l${i}_outref"

  /** One in-ref or out-ref entry for a layer, carrying all fields needed by the
    * asm, linker, SD, and overlap-check emitters.
    */
  case class RefEntry(
      section: String,
      file: String,
      addr: Long,
      size: Long,
      isInput: Boolean
  )

  /** In-ref then out-ref entries for layer `l` at index `idx`.
    *
    * Returns an empty sequence when `l.check` is None (non-check-mode layer).
    * Entries whose `file` is empty or `size` is zero indicate a missing golden;
    * callers filter with `.filter(e => e.file.nonEmpty && e.size > 0)` as
    * needed.
    */
  def refEntries(l: LayerInfo, idx: Int): Seq[RefEntry] =
    l.check.toSeq.flatMap { c =>
      Seq(
        RefEntry(
          inRefSection(idx),
          c.inRefFile,
          c.inRefAddr,
          c.inRefSize,
          isInput = true
        ),
        RefEntry(
          outRefSection(idx),
          c.outRefFile,
          c.outRefAddr,
          c.outRefSize,
          isInput = false
        )
      )
    }

  /** Page-unaware byte size of a file, or 0 if absent. */
  def fileSizeOr0(path: String): Long = {
    val p = os.Path(path, os.pwd)
    if (os.exists(p)) os.size(p) else 0L
  }

  /** Build a suffix-to-layer-index map from an ordered layer list. */
  def suffixToIdx(layers: Seq[LayerInfo]): Map[String, Int] =
    layers.zipWithIndex.map { case (l, i) => l.suffix -> i }.toMap

  /** Run body; on RuntimeException print the message and exit with code 1. */
  def runOrExit(body: => Unit): Unit =
    try body
    catch {
      case e: RuntimeException =>
        System.err.println(Option(e.getMessage).getOrElse(e.toString))
        sys.exit(1)
    }

  def safeCName(suffix: String, index: Int): String = {
    if (suffix.isEmpty) s"l$index"
    else {
      val name = suffix.map(ch => if (ch.isLetterOrDigit) ch else '_').mkString
      if (name.head.isDigit) "_" + name else name
    }
  }

  def layerBinfile(compDir: String, bufType: String, suffix: String): String = {
    val base = binBaseName(bufType)
    if (bufType == "ACC")
      s"$compDir/${base}${suffix}_block.bin"
    else
      s"$compDir/${base}$suffix.bin"
  }

  def memAddressesPath(compDir: String, suffix: String): String =
    s"$compDir/memory_addresses$suffix.csv"

  /** fsim golden input dump for a layer (VTA_DUMP_LAYERS=1). */
  def refInputPath(refDir: String, suffix: String): String =
    s"$refDir/input$suffix.bin"

  /** fsim golden secondary-operand input dump (dual-operand int32 layers). */
  def refInputYPath(refDir: String, suffix: String): String =
    s"$refDir/input${suffix}_Y.bin"

  /** fsim golden output dump for a layer (raw OUT, pre-rescale). */
  def refOutputPath(refDir: String, suffix: String): String =
    s"$refDir/output$suffix.bin"

  /** Return a POSIX-style relative path from baseDir to absPath. */
  def relpathPosix(absPath: String, baseDir: String): String =
    os.Path(absPath).relativeTo(os.Path(baseDir)).toString

  /** True when a buffer must NOT be statically pre-loaded into the ELF.
    *
    * For an int32 (ALU/maxpool) layer the ACC holds the layer's input
    * activations (dynamic, produced by the previous layer at runtime), not a
    * static parameter. Conv ACC (a bias) stays static.
    */
  def isRuntimeAcc(layer: LayerInfo, bufType: String): Boolean =
    bufType == "ACC" && layer.reshapeInfo == "int32"

  /** Yield (i, layer, bufType, region) for each statically pre-loaded buffer.
    *
    * Single source of truth for what gets embedded in the ELF: iterates
    * STATIC_LOAD_ORDER and skips empty buffers and the runtime ACC of
    * int32/maxpool layers.
    */
  def iterStaticBuffers(
      layers: Seq[LayerInfo]
  ): Seq[(Int, LayerInfo, String, MemoryRegion)] =
    for {
      (layer, i) <- layers.zipWithIndex
      bufType <- staticLoadOrder
      m = layer.mem(bufType)
      if m.byteSize != 0 && !isRuntimeAcc(layer, bufType)
    } yield (i, layer, bufType, m)
}
