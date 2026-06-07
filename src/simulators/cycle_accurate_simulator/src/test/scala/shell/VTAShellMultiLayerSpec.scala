package vta.shell

import chisel3._
import org.scalatest.matchers.should.Matchers

import scala.io.Source

import vta.parsers.DramInitParser
import vta.test.VTAShellTest
import vta.test.VTAShellTestFull
import vta.util.AnyFlatSpecSim
import vta.util.EnableMemInit
import vta.util.BinaryReader.DataType
import vta.util.BinaryReader.DataType._
import vta.util.MemoryConfig
import vta.util.MemoryInitializer.exportHexToMemFiles
import vta.util.SimulationUtils.verilatorWithWaveDump

/** Multi-layer launch-per-layer reproduction harness for the FPGA hang where
  *
  * MaxPool2 -> QLinearConv3 -> MaxPool4
  *
  * stalls MaxPool4 (instruction reads on m_axi_gmem complete but no further AXI
  * traffic). The board's run_nn_debug isolation mode runs each VTA layer with
  * its own launchVTA() against pre-loaded golden inputs, so any state leaked
  * from one launch into the next is exercised. This spec mirrors that: a single
  * VTAShell instance is launched once per layer; no Module reset happens
  * between launches.
  *
  * Layout strategy: each layer's compiler_output regions are relocated to a
  * unique high-address slot (RELO_L = layerIndex * reloStride). The VTA's
  * address computation is `baddr | (dram_offset << elem_shift)`, which equals
  * `baddr + offset` when their bit-ranges are disjoint, so setting the VCR
  * baddrs to RELO_L makes the encoded absolute offsets land in the layer's own
  * region with no risk of overlap (the compiler's per-layer ranges heavily
  * overlap each other at their original offsets).
  *
  * Inspired by VTAShellSimBinary (single layer) and the existing
  * `runVtaTestWithInitializedMemTwice` (two launches of the same data).
  */
class VTAShellMultiLayerSpec
    extends AnyFlatSpecSim
    with Matchers
    with VTAShellTest
    with EnableMemInit {
  behavior of "VTA multi-layer launches"

  /** Compiler outputs directory (override via -Dvta.compiler.outputDir=...).
    * Default points to the project's top-level compiler_output relative to the
    * cycle_accurate_simulator mill workdir.
    */
  private val compilerOutDir = sys.props.getOrElse(
    "vta.compiler.outputDir",
    "../../../compiler_output"
  )
  private val memOutDir = os.pwd / "build" / "mem-multilayer"

  // Reloc stride must be a power-of-2 wider than any layer's max region span,
  // so RELO_L's bits are disjoint from the per-instruction encoded offsets.
  // 0x200000 (2 MiB) is well above the 7-layer test net's biggest region.
  private val reloStride: BigInt = BigInt(0x200000)

  /** Drive the VTA through `layers` in order: one launch per layer, all on the
    * SAME VTAShell instance (no reset between launches). Hangs surface as
    * RunUntilFinished timeouts on the offending launch.
    */
  private def runLayerSequence(
      layers: Seq[String],
      perLayerTimeout: Int = 50_000,
      waves: Boolean = false
  ): Unit = {
    val (cfgs, perLayerList) =
      vta.test.CompilerOutputLayout.build(
        compilerOutDir,
        layers,
        reloStride,
        memOutDir
      )
    val perLayer: Map[String, vta.test.CompilerOutputLayout.LaunchParams] =
      layers.zip(perLayerList).toMap

    implicit val simulator = verilatorWithWaveDump

    simulate(
      // enforceOutBounds = false because the compiler's per-layer CSVs declare
      // OUT region sizes that are tighter than the actual store extents the
      // compiler emits (and OUT also overlaps adjacent UOP/INSN regions inside
      // the same layer slot by design). The bounds assertion would fire on
      // legal writes; cross-layer isolation is already enforced by the
      // reloStride slot layout.
      new VTAShellTestFull(cfgs, enforceOutBounds = false),
      firtoolOpts = Array("--disable-all-randomization")
    ) { vta =>
      implicit val clock = vta.clock
      implicit val axiLiteClient = vta.io.host
      vta.io.host.b.ready.poke(true.B)

      if (waves) {
        enableWaves()
      }

      def snapshot(label: String): Unit = {
        val s0 = vta.io.dbg.sem0.peek().litValue
        val s1 = vta.io.dbg.sem1.peek().litValue
        val aluSt = vta.io.dbg.tensorAluState.peek().litValue
        val aluInf = vta.io.dbg.tensorAluInf.peek().litValue
        val gemmSt = vta.io.dbg.tensorGemmState.peek().litValue
        val gemmInf = vta.io.dbg.tensorGemmInf.peek().litValue
        val cState = vta.io.dbg.computeState.peek().litValue
        val vmeAvail = vta.io.dbg.vmeAvailEntries.peek().litValue
        val instQ = vta.io.dbg.instQDeqValid.peek().litValue
        val isGemm = vta.io.dbg.computeIsGemm.peek().litValue
        val isAlu = vta.io.dbg.computeIsAlu.peek().litValue
        val labelStr = f"$label%-30s"
        val launch = vta.io.dbg.vcrLaunch.peek().litValue
        val fetchVal = vta.io.dbg.fetchInstCoValid.peek().litValue
        val fetchRdy = vta.io.dbg.fetchInstCoReady.peek().litValue
        val fetchSt = vta.io.dbg.fetchState.peek().litValue
        val fetchQ = vta.io.dbg.fetchInstQCount.peek().litValue
        val insCnt = vta.io.dbg.vcrInsCount.peek().litValue
        val cFin = vta.io.dbg.computeFinish.peek().litValue
        val cHead = vta.io.dbg.computeInstHead.peek().litValue
        val cSync = vta.io.dbg.computeIsSync.peek().litValue
        val cFn = vta.io.dbg.computeIsFinish.peek().litValue
        val cStart = vta.io.dbg.computeStart.peek().litValue
        info(
          s"[dbg @ $labelStr]  computeState=$cState  sem0=$s0  sem1=$s1  " +
            s"aluSt=$aluSt aluInf=$aluInf  gemmSt=$gemmSt gemmInf=$gemmInf  " +
            s"vmeAvail=$vmeAvail  instQDeqV=$instQ  isGemm=$isGemm isAlu=$isAlu  " +
            s"launch=$launch  fetchSt=$fetchSt fetchQ=$fetchQ insCnt=$insCnt " +
            s"fetch.co(v=$fetchVal,r=$fetchRdy)  " +
            f"cHead=0x$cHead%02x cSync=$cSync cFn=$cFn cStart=$cStart cFin=$cFin"
        )
      }

      snapshot("start (before any launch)")

      for (layer <- layers) {
        val p = perLayer(layer)
        // For ddr_base=0 compiled binaries, the compiler emits absolute byte
        // offsets in every instruction. The VTA computes the DRAM address as
        // `baddr | (offset << elem_shift)`, so pointing baddr at the
        // per-layer relocation slot reproduces a clean "base + offset" map.
        writeUopBaseAddress(p.relo.toInt)
        writeInputBaseAddress(p.relo.toInt)
        writeWeightBaseAddress(p.relo.toInt)
        writeAccBaseAddress(p.relo.toInt)
        writeOutBaseAddress(p.relo.toInt)
        writeInstructionBaseAddress(p.insnBaddr.toInt)
        writeInstructionCount(p.insnCount)

        // Exactly one launch per layer. VCR ctrl bit 0 is the launch level
        // and auto-clears on FNSH (VCR.scala:128-133 sets ctrl := 2.U on
        // io.vcr.finish), so each launchVTA() gives Fetch a fresh rising
        // edge. RunUntilFinished steps until VTAShellTestFull's stop() fires
        // on the next finish pulse - do NOT precede it with clock.step, that
        // races past the pulse and leaves us waiting for a finish that
        // already happened.
        launchVTA()
        snapshot(s"$layer  +0 cycles (right after launchVTA write)")
        // step 1 cycle so we can sample after the ctrl write has actually
        // propagated to launch
        vta.clock.step(1)
        snapshot(s"$layer  +1 cycles")
        var c = 1
        // For the dense tail layer, sample every 5 cycles for the first 200;
        // everywhere else use the coarse 10/100/10000 progression.
        val dense = layer == "QLinearConv7"
        var nextProbe = if (dense) 5 else 10
        while (c < perLayerTimeout && !vta.io.finish.peekBoolean()) {
          vta.clock.step(1)
          c = c + 1
          if (c == nextProbe) {
            snapshot(s"$layer  +${c} cycles (mid)")
            nextProbe =
              if (dense && c < 200) c + 5
              else if (nextProbe < 100) nextProbe + 10
              else if (nextProbe < 1000) nextProbe + 100
              else nextProbe + 10000
          }
        }
        if (!vta.io.finish.peekBoolean()) {
          // Hang surfaced - log the stuck state before failing so the probe
          // values are in the test log.
          snapshot(s"TIMEOUT after ${c} cycles in $layer")
        }
        vta.io.finish.expect(true.B, s"Layer ${layer} timed out")
        snapshot(s"after $layer FNSH (${c} cycles)")
      }
    }
  }

  // ------ baseline scenarios that ALSO pass on the board ------

  it should "run MaxPool4 alone (board case 0)" in {
    runLayerSequence(Seq("MaxPool4"), waves = true)
  }

  it should "run MaxPool4 twice in a row (board case 1)" in {
    runLayerSequence(Seq("MaxPool4", "MaxPool4"))
  }

  it should "run QLinearConv3 -> MaxPool4 (board case 2)" in {
    runLayerSequence(Seq("QLinearConv3", "MaxPool4"))
  }

  it should "run MaxPool2 -> MaxPool4 (board case 4)" in {
    runLayerSequence(Seq("MaxPool2", "MaxPool4"))
  }

  // ------ THE failing scenario on the board ------
  // If state leaks across launches in the same way as on hardware, this test
  // will time out on the third launchVTA() (Compute parks in sIdle waiting on
  // a semaphore that never posts, so no AXI traffic past the instruction
  // reads). If it passes, the bug is FPGA-only (timing / interconnect / cache
  // coherency) and we'll need on-board instrumentation.
  it should "REPRO: MaxPool2 -> QLinearConv3 -> MaxPool4 (board case 3, HANGS)" in {
    runLayerSequence(Seq("MaxPool2", "QLinearConv3", "MaxPool4"))
  }

  // ------ board tests rerun 2026-05-29 after the d1-shadow bypass fix ------
  // Per-layer corruption is solved, the cascade hang persists. The user
  // narrowed it to "MaxPool2 leaves residue; the next GEMM-using layer
  // hangs (Conv/Gemm hang, another MaxPool tolerates the residue)". These
  // mirror the board scenarios so we know whether the sim reproduces:
  //   - test 2 below: ran 2x MaxPool2 ok, then hung at QLinearConv3.
  //   - test 4 below: QLinearConv5 ok, MaxPool2 ok, Gemm6 produced correct
  //     output, then Gemm7 hung.
  //   - test "minimal" below: simplest possible boundary that should hang
  //     according to the model (MaxPool2 -> any GEMM-using layer).
  // If any of these reproduce in sim, the bug is in our Chisel and we can
  // iterate cycle-accurately. If they all pass like board case 3 already
  // does, the bug is board-only (AXI timing / interconnect / coherency)
  // and the path forward is the debug-bitstream probe capture.

  it should "REPRO: MaxPool2 -> MaxPool2 -> QLinearConv3 (board test 2)" in {
    runLayerSequence(Seq("MaxPool2", "MaxPool2", "QLinearConv3"))
  }

  it should "REPRO: QLinearConv5 -> MaxPool2 -> QLinearConv6 -> QLinearConv7 (board test 4)" in {
    // The LeNet5_conv dense tail compiles to QLinearConv6/QLinearConv7 in this
    // branch's compiler_output (the board notes called them Gemm6/Gemm7).
    runLayerSequence(
      Seq("QLinearConv5", "MaxPool2", "QLinearConv6", "QLinearConv7")
    )
  }

  it should "REPRO: MaxPool2 -> QLinearConv1 -> QLinearConv3 (board test 5)" in {
    runLayerSequence(
      Seq("MaxPool2", "QLinearConv1", "QLinearConv3")
    )
  }

  it should "REPRO: minimal MaxPool2 -> QLinearConv3" in {
    runLayerSequence(Seq("MaxPool2", "QLinearConv3"))
  }
}
