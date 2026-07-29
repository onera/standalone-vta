package fpga.host

import scopt.OParser
import fpga.host.models.Model

/** VTA test-gemm DRAM fixture generator.
  *
  * Generates the C++ header (init_dram.h) used by the VTA test-gemm C++
  * harness. In compiler-output mode the binary fixture files are loaded from
  * disk; the golden expected output is re-computed from the loaded matrices.
  *
  * The public helpers (formatCArray, formatInsnArray, formatUopArray) are
  * stable entry points tested directly by [[host.GenInitDramTestGemmTest]].
  */
object GenInitDramTestGemm {

  // ---------------------------------------------------------------------------
  // Constant string blocks (copied verbatim from the Python source)
  // ---------------------------------------------------------------------------

  private val _HEADER_INCLUDES =
    "#include <cstddef>\n" +
      "#include <cstdint>\n" +
      "#include <cstring>\n" +
      "\n" +
      "#include \"vta.h\"\n"

  private val _FINISH_INSN_BLOCK =
    "static const VTAInsn insn_finish[] = {\n" +
      "    {{0x00000003u, 0x00000000u, 0x00000000u, 0x00000000u}}\n" +
      "};\n"

  // Hardcoded VTA program for random-data mode (same uint32 words as Python).
  private val _HARDCODED_INSN_WORDS: Array[Long] = Array(0x00000000L,
    0x00000050L, 0x00010001L, 0x00000001L, 0x002000a2L, 0x00200008L,
    0x00000810L, 0x00000000L, 0x00000110L, 0x00000001L, 0x00100001L,
    0x00000010L, 0x200000c0L, 0x00000000L, 0x00010001L, 0x00000001L,
    0x00000188L, 0x00000003L, 0x00100001L, 0x00000010L, 0x04000000L,
    0x00000050L, 0x00010001L, 0x00000001L, 0x00200062L, 0x00200008L,
    0x00000800L, 0x00000002L, 0x00000229L, 0x00000004L, 0x00100001L,
    0x00000010L, 0x00000150L, 0x00000000L, 0x00000000L, 0x00000000L,
    0x00000018L, 0x00000000L, 0x00000000L, 0x00000000L, 0x00000003L,
    0x00000000L, 0x00000000L, 0x00000000L)
  private val _HARDCODED_UOP_WORDS: Array[Long] =
    Array(0x00000000L, 0x00000000L)

  // ---------------------------------------------------------------------------
  // Binary readers
  // ---------------------------------------------------------------------------

  /** Read a little-endian int32 binary file and return signed Int values. */
  def readInt32LE(path: os.Path): Array[Int] = {
    val bytes = os.read.bytes(path)
    val buf =
      java.nio.ByteBuffer.wrap(bytes).order(java.nio.ByteOrder.LITTLE_ENDIAN)
    Array.fill(bytes.length / 4)(buf.getInt())
  }

  /** Read a little-endian uint32 binary file and return values as unsigned
    * Long.
    */
  def readUInt32LE(path: os.Path): Array[Long] = {
    val bytes = os.read.bytes(path)
    val buf =
      java.nio.ByteBuffer.wrap(bytes).order(java.nio.ByteOrder.LITTLE_ENDIAN)
    Array.fill(bytes.length / 4)(buf.getInt().toLong & 0xffffffffL)
  }

  // ---------------------------------------------------------------------------
  // Formatters
  // ---------------------------------------------------------------------------

  /** Format a 1-D Int array as a C++ static const array (decimal,
    * right-aligned).
    *
    * Each value is right-justified to the width of the widest element
    * (including sign), matching Python's `f"{int(val):>{max_len}}"` rule
    * exactly.
    */
  def formatCArray(
    name: String,
    data: Array[Int],
    storageDtypeStr: String,
    chunkSize: Int
  ): String = {
    val cType = s"std::${storageDtypeStr}_t"
    val maxLen = data.map(_.toString.length).max
    val rows = data
      .grouped(chunkSize)
      .map { chunk =>
        "    " + chunk
          .map(v => " " * (maxLen - v.toString.length) + v.toString)
          .mkString(", ")
      }
      .toSeq
    s"static const $cType $name[] = {\n${rows.mkString(",\n")}\n};\n"
  }

  /** Emit `static const VTAInsn name[] = { ... };` from a uint32 word stream.
    *
    * Each VTAInsn is 4 x uint32 (128-bit). Length must be a multiple of 4.
    */
  def formatInsnArray(name: String, insnWords: Array[Long]): String = {
    require(
      insnWords.length % 4 == 0,
      s"Instruction stream has ${insnWords.length} uint32 words; " +
        s"expected a multiple of 4 (each VTAInsn is 4 x uint32)."
    )
    val rows = insnWords.grouped(4).toSeq
    val lines = Seq(s"static const VTAInsn $name[] = {") ++
      rows.zipWithIndex.map { case (row, i) =>
        val hexVals =
          row.map(w => "0x%08X".format(w & 0xffffffffL) + "u").mkString(", ")
        val sep = if (i < rows.length - 1) "," else ""
        s"    {{$hexVals}}$sep"
      } ++
      Seq("};")
    lines.mkString("\n") + "\n"
  }

  /** Emit `static const std::uint32_t name[] = { ... };` from a uint32 stream.
    */
  def formatUopArray(
    name: String,
    uopWords: Array[Long],
    chunkSize: Int = 4
  ): String = {
    val n = uopWords.length
    val lines = Seq(s"static const std::uint32_t $name[] = {") ++
      (0 until n by chunkSize).map { i =>
        val chunk = uopWords.slice(i, i + chunkSize)
        val hexVals =
          chunk.map(w => "0x%08X".format(w & 0xffffffffL) + "u").mkString(", ")
        val sep = if (i + chunkSize < n) "," else ""
        s"    $hexVals$sep"
      } ++
      Seq("};")
    lines.mkString("\n") + "\n"
  }

  // ---------------------------------------------------------------------------
  // Golden computation
  // ---------------------------------------------------------------------------

  /** Compute SOUT-truncated golden: acc + inp @ wgt.T, result as Int32.
    *
    * Mirrors Python's `_compute_golden` with acc_dtype=int32, out_dtype=int32.
    * Accumulation uses Long to avoid intermediate overflow; the final cast to
    * Int truncates the low 32 bits, matching NumPy int32 wrap semantics.
    */
  private def computeGolden(
    inp: Array[Int],
    wgt: Array[Int],
    acc: Array[Int],
    n: Int
  ): Array[Int] = {
    Array.tabulate(n * n) { idx =>
      val i = idx / n
      val j = idx % n
      val sum = acc(idx).toLong +
        (0 until n).foldLeft(0L)((s, k) =>
          s + inp(i * n + k).toLong * wgt(j * n + k).toLong
        )
      sum.toInt
    }
  }

  // ---------------------------------------------------------------------------
  // Main entry point
  // ---------------------------------------------------------------------------

  /** Generate the init_dram.h header file.
    *
    * @param outFile
    *   path to the output file (absolute or relative to CWD)
    * @param n
    *   matrix dimension (n x n); default 16
    * @param inpStorage
    *   storage dtype string for input ("int32", etc.)
    * @param wgtStorage
    *   storage dtype string for weight
    * @param accStorage
    *   storage dtype string for accumulator
    * @param outStorage
    *   storage dtype string for expected_out; defaults to accStorage
    * @param compilerOutputDir
    *   if set, load input/weight/acc/uop/insn from this directory
    * @param suffix
    *   file-name suffix appended to each bin basename
    * @param minVal
    *   minimum random value (random-data mode only)
    * @param maxVal
    *   maximum random value (random-data mode only)
    */
  def generate(
    outFile: String,
    n: Int = 16,
    inpStorage: String = "int32",
    wgtStorage: String = "int32",
    accStorage: String = "int32",
    outStorage: Option[String] = None,
    compilerOutputDir: Option[String] = None,
    suffix: String = "",
    minVal: Int = -128,
    maxVal: Int = 127
  ): Unit = {
    val outStorageStr = outStorage.getOrElse(accStorage)

    val (inp, wgt, acc, outGolden, uopWords, insnWords) =
      compilerOutputDir match {
        case Some(dir) =>
          val d = os.Path(new java.io.File(dir).getAbsolutePath)
          def p(base: String) = d / s"$base$suffix.bin"
          val inpFlat = readInt32LE(p("input"))
          val wgtFlat = readInt32LE(p("weight"))
          val accFlat = readInt32LE(p("accumulator"))
          require(
            inpFlat.length == n * n,
            s"input: expected ${n * n} elements, got ${inpFlat.length}. " +
              s"Adjust -n or check storage dtypes."
          )
          require(
            wgtFlat.length == n * n,
            s"weight: expected ${n * n} elements, got ${wgtFlat.length}. " +
              s"Adjust -n or check storage dtypes."
          )
          require(
            accFlat.length == n * n,
            s"accumulator: expected ${n * n} elements, got ${accFlat.length}. " +
              s"Adjust -n or check storage dtypes."
          )
          val golden = computeGolden(inpFlat, wgtFlat, accFlat, n)
          val uop = readUInt32LE(p("uop"))
          val insn = readUInt32LE(p("instructions"))
          (inpFlat, wgtFlat, accFlat, golden, uop, insn)

        case None =>
          val rng = new java.util.Random(0L)
          val range = maxVal - minVal + 1
          val inpFlat = Array.fill(n * n)(minVal + rng.nextInt(range))
          val wgtFlat = Array.fill(n * n)(minVal + rng.nextInt(range))
          val accFlat = Array.fill(n * n)(0)
          val golden = computeGolden(inpFlat, wgtFlat, accFlat, n)
          (
            inpFlat,
            wgtFlat,
            accFlat,
            golden,
            _HARDCODED_UOP_WORDS,
            _HARDCODED_INSN_WORDS
          )
      }

    val content =
      _HEADER_INCLUDES + "\n" +
        formatInsnArray("insn", insnWords) + "\n" +
        _FINISH_INSN_BLOCK + "\n" +
        formatUopArray("uop", uopWords) + "\n" +
        formatCArray("input", inp, inpStorage, n) + "\n" +
        formatCArray("wgt", wgt, wgtStorage, n) + "\n" +
        formatCArray("acc", acc, accStorage, n) + "\n" +
        formatCArray("expected_out", outGolden, outStorageStr, n) + "\n"

    val outPath = os.Path(outFile, os.pwd)
    os.makeDir.all(outPath / os.up)
    os.write.over(outPath, content)
    println(s"Success: File '$outPath' generated.")
    println(s"File size: ${os.stat(outPath).size} bytes.")
  }

  private case class Opts(
    n: Int = 16,
    inpStorage: String = "int32",
    wgtStorage: String = "int32",
    accStorage: String = "int32",
    outStorage: Option[String] = None,
    compilerOutputDir: Option[String] = None,
    suffix: String = "",
    filename: String = "init_dram.h",
    outdir: String = "gen"
  )

  private val argParser: OParser[_, Opts] = {
    val b = OParser.builder[Opts]
    import b._
    OParser.sequence(
      programName("genInitDramTestGemm"),
      head(
        "genInitDramTestGemm",
        "generate init_dram.h for the VTA test-gemm harness"
      ),
      opt[Int]("n")
        .action((x, c) => c.copy(n = x))
        .text("matrix dimension n x n (default 16)"),
      opt[String]("inp-storage")
        .action((x, c) => c.copy(inpStorage = x))
        .text("input storage dtype (default int32)"),
      opt[String]("wgt-storage")
        .action((x, c) => c.copy(wgtStorage = x))
        .text("weight storage dtype (default int32)"),
      opt[String]("acc-storage")
        .action((x, c) => c.copy(accStorage = x))
        .text("accumulator storage dtype (default int32)"),
      opt[String]("out-storage")
        .action((x, c) => c.copy(outStorage = Some(x)))
        .text("expected_out storage dtype (default = acc-storage)"),
      opt[String]("compiler-output-dir")
        .action((x, c) => c.copy(compilerOutputDir = Some(x)))
        .text("load binary fixtures from this compiler output directory"),
      opt[String]("suffix")
        .action((x, c) => c.copy(suffix = x))
        .text("file-name suffix appended to each bin basename (default \"\")"),
      opt[String]("filename")
        .action((x, c) => c.copy(filename = x))
        .text("output file name (default init_dram.h)"),
      opt[String]("outdir")
        .action((x, c) => c.copy(outdir = x))
        .text("output directory (default gen)")
    )
  }

  def main(args: Array[String]): Unit =
    OParser.parse(argParser, args, Opts()) match {
      case Some(o) =>
        val outdir = new java.io.File(o.outdir).getAbsolutePath
        val outFile = s"$outdir/${o.filename}"
        Model.runOrExit {
          generate(
            outFile = outFile,
            n = o.n,
            inpStorage = o.inpStorage,
            wgtStorage = o.wgtStorage,
            accStorage = o.accStorage,
            outStorage = o.outStorage,
            compilerOutputDir =
              o.compilerOutputDir.map(p => new java.io.File(p).getAbsolutePath),
            suffix = o.suffix
          )
        }
      case _ =>
    }
}
