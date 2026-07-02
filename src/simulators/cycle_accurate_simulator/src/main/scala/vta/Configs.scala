/*
 * Licensed to the Apache Software Foundation (ASF) under one
 * or more contributor license agreements.  See the NOTICE file
 * distributed with this work for additional information
 * regarding copyright ownership.  The ASF licenses this file
 * to you under the Apache License, Version 2.0 (the
 * "License"); you may not use this file except in compliance
 * with the License.  You may obtain a copy of the License at
 *
 *   http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing,
 * software distributed under the License is distributed on an
 * "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY
 * KIND, either express or implied.  See the License for the
 * specific language governing permissions and limitations
 * under the License.
 */

package vta

import circt.stage.ChiselStage
import vta.core._
import vta.shell._
import vta.test._
import vta.util.XilinxIpFlow.exportIpPackageTclScript
import vta.util.config._

/** VTA.
  *
  * This file contains all the configurations supported by VTA. These
  * configurations are built in a mix/match form based on core and shell
  * configurations.
  */
class DefaultPynqConfig extends Config(new CoreConfig ++ new PynqConfig)
class DefaultF1Config extends Config(new CoreConfig ++ new F1Config)
class DefaultDe10Config extends Config(new CoreConfig ++ new De10Config)

trait EmitterApp extends App {
  val defaultDir = os.RelPath("build/emitted/default")
  def outputDir = if (args.nonEmpty) os.Path(args(0)) else os.pwd / defaultDir
  def getConfig(implicit p: Parameters) = {
    p(CoreKey) match {
      case CoreParams(
            target,
            batch,
            blockOut,
            blockOutFactor,
            blockIn,
            inpBits,
            wgtBits,
            uopBits,
            accBits,
            outBits,
            uopMemDepth,
            inpMemDepth,
            wgtMemDepth,
            accMemDepth,
            outMemDepth,
            instQueueEntries
          ) =>
        s"""
          |Using following core config for target ${target}:
          | -batch=${batch}
          | -blockOut=${blockOut}
          | -blockOutFactor=${blockOutFactor}
          | -blockIn=${blockIn}
          | -inpBits=${inpBits}
          | -wgtBits=${wgtBits}
          | -uopBits=${uopBits}
          | -accBits=${accBits}
          | -outBits=${outBits}
          | -uopMemDepth=${uopMemDepth}
          | -inpMemDepth=${inpMemDepth}
          | -wgtMemDepth=${wgtMemDepth}
          | -accMemDepth=${accMemDepth}
          | -outMemDepth=${outMemDepth}
          | -instQueueEntries=${instQueueEntries}
          """.stripMargin
      case _ => ""
    }
  }
  def showConfig(implicit p: Parameters) = {
    println(getConfig)
  }
}

object DefaultXilinxConfig extends EmitterApp {
  override val defaultDir = os.RelPath("build") / "emitted" / "vta-xilinx-shell"
  implicit val p: Parameters = new DefaultPynqConfig
  ChiselStage.emitSystemVerilogFile(
    new XilinxShell,
    args = Array(
      "--target-dir",
      outputDir.toString(),
      "--split-verilog"
    ),
    firtoolOpts = Array(
      "--lowering-options=disallowLocalVariables,disallowPackedArrays,mitigateVivadoArrayIndexConstPropBug"
    )
  )

  showConfig
  exportIpPackageTclScript(
    target = outputDir,
    vendor = "onera",
    name = "VTA",
    version = "0.2.0",
    topModule = "VTAXilinxShell",
    displayName = "VTA_" + p(CoreKey).target,
    description =
      "Versatile Tensor Accelerator - Xilinx shell (AXI4-Lite ctrl + AXI4 DRAM)" + getConfig
  )

}
object DebugXilinxConfig extends EmitterApp {
  override val defaultDir =
    os.RelPath("build") / "emitted" / "vta-debug-xilinx-shell"
  implicit val p: Parameters = new DefaultPynqConfig
  ChiselStage.emitSystemVerilogFile(
    new XilinxDebugShell,
    args = Array(
      "--target-dir",
      outputDir.toString(),
      "--split-verilog"
    ),
    firtoolOpts = Array(
      "--lowering-options=disallowLocalVariables,disallowPackedArrays,mitigateVivadoArrayIndexConstPropBug"
    )
  )

  showConfig
  exportIpPackageTclScript(
    target = outputDir,
    vendor = "onera",
    name = "VTA_debug",
    version = "0.2.0",
    topModule = "VTAXilinxShell",
    displayName = "VTA_debug_" + p(CoreKey).target,
    description =
      "Versatile Tensor Accelerator - Xilinx shell (AXI4-Lite ctrl + AXI4 DRAM)" + getConfig
  )

}
object StandaloneSimConfig extends EmitterApp {
  override val defaultDir = os.RelPath("build/emitted/vta-sim-shell")

  implicit val p: Parameters = new DefaultPynqConfig

  ChiselStage.emitSystemVerilogFile(
    new Test,
    args = Array("--target-dir", outputDir.toString())
  )

  showConfig
  println(s"[EmitVTAShell] Simulation files written to $outputDir/")
}

/** Emit the self-driving multi-layer post-synthesis testbench (VTAPostSynthTb)
  * to SystemVerilog plus the per-layer .mem files.
  *
  * Config is taken from program args (forwarded by the Mill task) with
  * sys.props and defaults as fallback: args(0) = output dir (handled by
  * EmitterApp.outputDir) --compilerOutDir=... = compiler_output dir (default
  * "../../../compiler_output") --layers=a,b,c = comma-separated layer suffixes
  * --reloStride=N = per-layer relocation stride (default 0x200000)
  * --perLayerTimeout=N = host-driver watchdog cycles (default 2000000)
  */
object EmitPostSynthTb extends EmitterApp {
  override val defaultDir = os.RelPath("build") / "emitted" / "vta-postsynth-tb"
  implicit val p: Parameters = new DefaultPynqConfig

  private def argVal(key: String, dflt: String): String =
    args
      .find(_.startsWith(s"--$key="))
      .map(_.stripPrefix(s"--$key="))
      .orElse(sys.props.get(s"vta.$key"))
      .getOrElse(dflt)

  // Default matches the multilayer spec / repo layout: compiler_output lives at
  // the repo root, three levels above the Mill build root (this dir).
  val compilerOutDir = argVal("compilerOutDir", "../../../compiler_output")
  val layers =
    argVal(
      "layers",
      "QLinearConv1"
    ).split(",").map(_.trim).filter(_.nonEmpty).toSeq
  val reloStride = BigInt(argVal("reloStride", "2097152")) // 0x200000
  val perLayerTimeout = argVal("perLayerTimeout", "2000000").toInt
  // INP buffers come from the fsim/vsim --dump-layers output (the compiler's
  // input$layer.bin is a zero placeholder). See CompilerOutputLayout.fileFor.
  val simOutDir = argVal("simOutDir", "../../../simulators_output")

  val memOutDir = outputDir / "mem"
  val (cfgs, params) =
    vta.test.CompilerOutputLayout.build(
      compilerOutDir,
      layers,
      reloStride,
      memOutDir,
      simOutDir
    )

  // Lowering options; the Vivado array-index const-prop mitigation can be
  // toggled off for A/B synthesis experiments via -Dvta.loweringOptions=...
  val loweringOptions = argVal(
    "loweringOptions",
    "disallowLocalVariables,disallowPackedArrays,mitigateVivadoArrayIndexConstPropBug"
  )
  ChiselStage.emitSystemVerilogFile(
    new vta.test.VTAPostSynthTb(cfgs, params, perLayerTimeout),
    args = Array("--target-dir", outputDir.toString(), "--split-verilog"),
    firtoolOpts = Array(s"--lowering-options=$loweringOptions")
  )

  showConfig
  println(
    s"[EmitPostSynthTb] SV written to $outputDir; .mem files in $memOutDir; " +
      s"layers=${layers.mkString(",")}"
  )
}

object DefaultF1Config extends App {
  implicit val p: Parameters = new DefaultF1Config
  ChiselStage.emitSystemVerilog(new XilinxShell, args)
}

object DefaultDe10Config extends App {
  implicit val p: Parameters = new DefaultDe10Config
  ChiselStage.emitSystemVerilog(new IntelShell, args)
}

object TestDefaultPynqConfig extends App {
  implicit val p: Parameters = new DefaultPynqConfig
  // ChiselStage.emitSystemVerilog(new Test, args)
  ChiselStage.emitSystemVerilogFile(
    new Test,
    args = Array("--target-dir", s"build/emitted/test-vta-pynq")
  )
}

object TestDefaultF1Config extends App {
  implicit val p: Parameters = new DefaultF1Config
  ChiselStage.emitSystemVerilog(new Test, args)
}

object TestDefaultDe10Config extends App {
  implicit val p: Parameters = new DefaultDe10Config
  ChiselStage.emitSystemVerilog(new Test, args)
}
