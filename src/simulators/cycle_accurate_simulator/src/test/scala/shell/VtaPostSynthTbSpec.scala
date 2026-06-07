package vta.shell

import chisel3._
import org.scalatest.matchers.should.Matchers
import vta.test.{CompilerOutputLayout, VTAPostSynthTb}
import vta.util.AnyFlatSpecSim
import vta.util.EnableMemInit
import vta.util.SimulationUtils.verilatorWithWaveDump

class VtaPostSynthTbSpec
    extends AnyFlatSpecSim
    with Matchers
    with EnableMemInit {
  behavior of "VTAPostSynthTb"

  private val compilerOutDir =
    sys.props.getOrElse("vta.compiler.outputDir", "../../../compiler_output")
  private val simOutDir =
    sys.props.getOrElse("vta.simOutDir", "../../../simulators_output")
  private val memOutDir = os.pwd / "build" / "mem-postsynth-test"
  private val reloStride = BigInt(0x200000)

  it should "drive MaxPool4 to done with the synthesizable host driver" in {
    val layers = Seq("MaxPool4")
    val (cfgs, params) =
      CompilerOutputLayout.build(compilerOutDir, layers, reloStride, memOutDir)

    implicit val simulator = verilatorWithWaveDump
    simulate(
      new VTAPostSynthTb(cfgs, params, perLayerTimeout = 200000),
      firtoolOpts = Array("--disable-all-randomization")
    ) { dut =>
      implicit val clock = dut.clock
      var c = 0
      while (!dut.io.done.peekBoolean() && c < 200000) {
        if (dut.io.error.peekBoolean())
          fail(s"driver error at layer ${dut.io.layerIdx.peek().litValue}")
        clock.step(1); c += 1
      }
      dut.io.done.expect(true.B, s"never finished after $c cycles")
      dut.io.error.expect(false.B)
    }
  }

  /** Run a single layer in isolation under Verilator and verify the bytes the
    * VTA stores to its OUT region match the fsim `--dump-layers` golden. The
    * OUT data is captured from the AXI write-channel snoop (io.dbgW)
    * strobe-aware, exactly like the netlist sim_top.sv wrapper, so this
    * behavioral result is a faithful control for the gate-level (xsim) run.
    */
  private def runLayerAndCheckOut(layer: String): Unit = {
    val (cfgs, params) =
      CompilerOutputLayout.build(
        compilerOutDir,
        Seq(layer),
        reloStride,
        memOutDir,
        simOutDir
      )
    val outCfg = cfgs
      .find(_.name == s"OUT_$layer")
      .getOrElse(fail(s"no OUT region for $layer"))
    val outBase = BigInt(outCfg.baseAddress) & 0xffffffffL

    val golden =
      os.read.bytes(os.Path(s"$simOutDir/output$layer.bin", os.pwd))

    // The CSV-declared OUT region (outCfg.words64) is frequently SMALLER than the
    // actual store extent (the compiler under-reserves OUT), so bound the capture
    // window by the golden length, not the declared region, plus one beat of slack.
    val outBytes =
      math.max(outCfg.words64.toLong * 8, golden.length.toLong) + 8

    // addr -> byte, accumulated from every strobed OUT write beat.
    val outMap = scala.collection.mutable.Map.empty[Long, Int]
    val beats = scala.collection.mutable.ListBuffer.empty[(Long, BigInt, Int)]

    implicit val simulator = verilatorWithWaveDump
    simulate(
      new VTAPostSynthTb(cfgs, params, perLayerTimeout = 200000),
      firtoolOpts = Array("--disable-all-randomization")
    ) { dut =>
      implicit val clock = dut.clock
      var c = 0
      while (!dut.io.done.peekBoolean() && c < 200000) {
        if (dut.io.error.peekBoolean())
          fail(s"driver error at layer ${dut.io.layerIdx.peek().litValue}")
        if (dut.io.dbgW.valid.peekBoolean()) {
          val addr = (dut.io.dbgW.addr.peek().litValue.toLong) & 0xffffffffL
          val data = dut.io.dbgW.data.peek().litValue
          val strb = dut.io.dbgW.strb.peek().litValue.toInt
          beats += ((addr, data, strb))
          if (addr >= outBase.toLong && addr < outBase.toLong + outBytes) {
            for (b <- 0 until 8 if (strb & (1 << b)) != 0) {
              val byteVal = ((data >> (8 * b)) & BigInt(0xff)).toInt
              outMap(addr - outBase.toLong + b) = byteVal
            }
          }
        }
        clock.step(1); c += 1
      }
      dut.io.done.expect(true.B, s"never finished after $c cycles")
      dut.io.error.expect(false.B)
    }
    // Dump beats touching the last OUT row (bytes 56..63) for diagnosis.
    beats
      .filter { case (a, _, _) =>
        a >= outBase.toLong + 48 && a < outBase.toLong + outBytes
      }
      .foreach { case (a, d, s) =>
        info(f"beat off=${a - outBase.toLong}%3d data=0x$d%016x strb=0x$s%02x")
      }

    val got = (0 until golden.length).map { i =>
      outMap.getOrElse(i.toLong, 0).toByte
    }.toArray
    val mismatches = (0 until golden.length).filter(i => got(i) != golden(i))
    info(
      s"$layer OUT: ${golden.length - mismatches.length}/${golden.length} bytes match"
    )
    if (mismatches.nonEmpty) {
      val sample = mismatches.take(16).map { i =>
        s"[$i] got=${got(i)} exp=${golden(i)}"
      }
      info(s"first mismatches: ${sample.mkString(", ")}")
    }
    withClue(s"$layer OUT mismatch (${mismatches.length}/${golden.length})") {
      mismatches.length shouldBe 0
    }
  }

  it should "compute MaxPool2 OUT bytes matching the fsim golden (behavioral)" in {
    runLayerAndCheckOut("MaxPool2")
  }

  it should "compute QLinearConv1 OUT bytes matching the fsim golden (behavioral)" in {
    runLayerAndCheckOut("QLinearConv1")
  }
}
