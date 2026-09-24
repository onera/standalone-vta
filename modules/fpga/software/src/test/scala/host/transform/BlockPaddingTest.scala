package fpga.host.transform

import org.scalatest.flatspec.AnyFlatSpec
import org.scalatest.matchers.should.Matchers
import org.scalatest.OptionValues
import fpga.host.models._
import vta.models.CompilerOutputModel.{
  DependencyInfo,
  LayerDependency,
  MemoryRegion
}
import vta.models.DataType

/** Block-padding rules of the CPU steps, at block 32 with `H*W = 784`, where
  * padded and dense element counts differ.
  */
class BlockPaddingTest extends AnyFlatSpec with Matchers with OptionValues {

  private val Block = 32
  private val LogOutWidth = 5 // 32-bit OUT
  private val OutElemBytes = 4

  private val C = 128
  private val H = 28
  private val W = 28
  private val N = H * W // 784 - deliberately NOT a multiple of 32

  private def roundUp(x: Long): Long = ((x + Block - 1) / Block) * Block
  private val Dense = C.toLong * H * W // 100352
  private val Padded = roundUp(N.toLong) * roundUp(C.toLong) // 102400

  /** A layer row with the shape above; only the fields these paths read vary. */
  private def layerDep(
    processor: String,
    reshape: String,
    deps: Seq[String],
    nbInp: Int = 1
  ) = LayerDependency(
    processor = processor,
    reshapeInfo = reshape,
    offsetA = 0,
    scaleA = 1.0,
    offsetB = 0,
    scaleB = 1.0,
    offsetU = 0,
    scaleU = 1.0,
    offsetV = 0,
    scaleV = 1.0,
    tensorCh = C,
    tensorH = H,
    tensorW = W,
    kh = 1,
    kw = 1,
    sh = 1,
    sw = 1,
    pad = (0, 0, 0, 0),
    outCh = C,
    outH = H,
    outW = W,
    offsetC = 0,
    scaleC = 1.0,
    scale = 1.0,
    nbInp = nbInp,
    deps = deps
  )

  /** A VTA layer whose OUT holds `outElems` elements, everything else empty. */
  private def layerInfo(
    suffix: String,
    outElems: Long,
    offset: Long,
    reshape: String
  ) = {
    val mem = DataType.names.map { n =>
      n -> (if (n == "OUT")
              MemoryRegion("OUT", offset, None, outElems * OutElemBytes)
            else MemoryRegion(n, offset, None, 0L))
    }.toMap
    Model.LayerInfo(suffix, mem, Map.empty, reshape)
  }

  private def plan(
    order: Seq[(Int, String, String)],
    deps: Map[String, LayerDependency],
    layers: Seq[Model.LayerInfo],
    cpuOut: Map[String, Long]
  ) = ExecPlanResolver.resolve(
    ExecPlan(
      dep = DependencyInfo(order, deps, H, W, order.last._3),
      layers = layers,
      ddrBase = 0x01000000L,
      compDir = "",
      blockSize = Block,
      cpuOut = Some(cpuOut),
      logOutWidth = LogOutWidth
    )
  )

  // ---------------------------------------------------------------- qadd ---

  "a qadd over block-tiled buffers" should
    "count the padded elements, not C*H*W" in {
      val order = Seq(
        (0, "vta", "ConvA"),
        (1, "vta", "ConvB"),
        (2, "qadd", "Add")
      )
      val deps = Map(
        "ConvA" -> layerDep("vta", "im2row", Nil),
        "ConvB" -> layerDep("vta", "im2row", Nil),
        "Add" -> layerDep("qadd", "im2row", Seq("ConvA", "ConvB"), nbInp = 2)
      )
      val layers = Seq(
        layerInfo("ConvA", Padded, 0x1000L, "im2row"),
        layerInfo("ConvB", Padded, 0x100000L, "im2row")
      )
      val steps = plan(order, deps, layers, Map("Add" -> 0x200000L)).steps
      val qadd = steps.collectFirst { case s: QaddStep => s }.value

      qadd.n shouldBe Padded
      // The dense count stops 1024 elements short of the last real element:
      // block-tiled data does not occupy a dense prefix.
      qadd.n should not be Dense
    }

  // -------------------------------------------------------------- concat ---

  "a concat whose branches are all padded" should "use the padded row count" in {
    val order =
      Seq((0, "vta", "ConvA"), (1, "vta", "ConvB"), (2, "concat", "Cat"))
    val deps = Map(
      "ConvA" -> layerDep("vta", "im2row", Nil),
      "ConvB" -> layerDep("vta", "im2row", Nil),
      "Cat" -> layerDep("concat", "im2row", Seq("ConvA", "ConvB"), nbInp = 2)
    )
    val layers = Seq(
      layerInfo("ConvA", Padded, 0x1000L, "im2row"),
      layerInfo("ConvB", Padded, 0x100000L, "im2row")
    )
    val cat = plan(order, deps, layers, Map("Cat" -> 0x200000L)).steps
      .collectFirst { case s: ConcatStep => s }
      .value

    cat.nRows shouldBe roundUp(N.toLong) // 800
    cat.nRowsValid shouldBe N.toLong // 784
    cat.compactMask shouldBe 0 // nothing compact
  }

  it should "flag a branch that stores its final row-block compactly" in {
    // One compact (int32) branch and one padded (im2row) branch.
    val order =
      Seq((0, "vta", "ConvA"), (1, "vta", "PoolB"), (2, "concat", "Cat"))
    val deps = Map(
      "ConvA" -> layerDep("vta", "im2row", Nil),
      "PoolB" -> layerDep("vta", "int32", Nil),
      "Cat" -> layerDep("concat", "im2row", Seq("ConvA", "PoolB"), nbInp = 2)
    )
    val layers = Seq(
      layerInfo("ConvA", Padded, 0x1000L, "im2row"), // padded  -> bit clear
      layerInfo("PoolB", Dense, 0x100000L, "int32") // compact -> bit set
    )
    val cat = plan(order, deps, layers, Map("Cat" -> 0x200000L)).steps
      .collectFirst { case s: ConcatStep => s }
      .value

    cat.compactMask shouldBe 0x2 // branch 1 only
    cat.nRowsValid shouldBe N.toLong // the compact branch's real rows
  }

  // ---------------------------------------------------------- allocation ---

  "the CPU-op scratch allocator" should
    "size a qadd output for the padded element count" in {
      val order = Seq(
        (0, "vta", "ConvA"),
        (1, "vta", "ConvB"),
        (2, "qadd", "Add")
      )
      val deps = Map(
        "ConvA" -> layerDep("vta", "im2row", Nil),
        "ConvB" -> layerDep("vta", "im2row", Nil),
        "Add" -> layerDep("qadd", "im2row", Seq("ConvA", "ConvB"), nbInp = 2)
      )
      val layers = Seq(
        layerInfo("ConvA", Padded, 0x1000L, "im2row"),
        layerInfo("ConvB", Padded, 0x100000L, "im2row")
      )
      val (_, _, scratch) = MemoryLayout.buildCpuOutAddrs(
        DependencyInfo(order, deps, H, W, "Add"),
        layers,
        ddrBase = 0x01000000L,
        suffixToIdx = Map("ConvA" -> 0, "ConvB" -> 1),
        compDir = "",
        refDir = None,
        blockSize = Block
      )
      val add = scratch.find(_._1 == "Add").value
      // Dense would under-allocate by 2048 bytes, and the consuming relayout
      // addresses out to byte 101888.
      add._3 shouldBe Padded
    }
}
