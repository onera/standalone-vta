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

package vta.exporters

import circt.stage.ChiselStage
import vta.configs._
import vta.core._
import vta.shell._
import vta.test._
import vta.util.config._

import IpPackageScriptExporter.export

/** Base abstract emitter class for generating the SystemVerilog for a given
  * config
  *
  * @param p
  *   The config used by the emitter, defined in [[vta.configs]] package
  */
sealed abstract class EmitterApp(p: Parameters) extends App {
  implicit val params: Parameters = p
  val defaultDir = os.RelPath("build/emitted/default")
  def outputDir = if (args.nonEmpty) os.Path(args(0)) else os.pwd / defaultDir

  /** Return a text representation of the current config, used for emission
    *
    * @param p
    *   the config
    * @return
    *   an info string to be printed for debug
    */
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
  println(getConfig)
}

/** Emit the XilinxShell, as well as a package.tcl script for Vivado IPI flow
  */
object DefaultXilinxConfigEmitter extends EmitterApp(new DefaultPynqConfig) {
  override val defaultDir = os.RelPath("build") / "emitted" / "vta-xilinx-shell"
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

  export(
    target = outputDir,
    vendor = "onera",
    name = "VTA",
    version = "0.2.0",
    topModule = "VTAXilinxShell",
    displayName = "VTA_" + params(CoreKey).target,
    description =
      "Versatile Tensor Accelerator - Xilinx shell (AXI4-Lite ctrl + AXI4 DRAM)" + getConfig
  )

}

/** Emit the XilinxDebugShell with probes for on-board ILA debug flow
  */
object DebugXilinxConfigEmitter extends EmitterApp(new DefaultPynqConfig) {
  override val defaultDir =
    os.RelPath("build") / "emitted" / "vta-debug-xilinx-shell"
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

  export(
    target = outputDir,
    vendor = "onera",
    name = "VTA_debug",
    version = "0.2.0",
    topModule = "VTAXilinxShell",
    displayName = "VTA_debug_" + params(CoreKey).target,
    description =
      "Versatile Tensor Accelerator - Xilinx shell (AXI4-Lite ctrl + AXI4 DRAM)" + getConfig
  )

}

/** Emit the VTA Test for DPI simulation
  */
object TestDefaultPynqConfigEmitter extends EmitterApp(new DefaultPynqConfig) {
  override val defaultDir = os.RelPath("build/emitted/vta-sim-shell")

  ChiselStage.emitSystemVerilogFile(
    new Test,
    args = Array("--target-dir", outputDir.toString())
  )

  println(s"[EmitVTAShell] Simulation files written to $outputDir/")
}

/** Emit the self-driving multi-layer post-synthesis testbench (VTAPostSynthTb)
  * to SystemVerilog plus the per-layer .mem files.
  */
object DefaultPynqConfigTbEmitter extends EmitterApp(new DefaultPynqConfig) {
  override val defaultDir = os.RelPath("build") / "emitted" / "vta-postsynth-tb"

  private def argVal(key: String, default: String): String =
    args
      .find(_.startsWith(s"--$key="))
      .map(_.stripPrefix(s"--$key="))
      .orElse(sys.props.get(s"vta.$key"))
      .getOrElse(default)

  val compilerOutDir = argVal("compilerOutDir", "../../../compiler_output")
  val layers =
    argVal(
      "layers",
      "QLinearConv1"
    ).split(",").map(_.trim).filter(_.nonEmpty).toSeq
  val baseAddressOffset = BigInt(argVal("reloStride", "2097152")) // 0x200000
  val perLayerTimeout = argVal("perLayerTimeout", "2000000").toInt
  // INP buffers come from the fsim/vsim --dump-layers output
  val simOutDir = argVal("simOutDir", "../../../simulators_output")

  val memOutDir = outputDir / "mem"
  val (memoryConfigs, launchParams) =
    vta.parsers.CompilerOutputLayout.build(
      compilerOutDir,
      layers,
      baseAddressOffset,
      memOutDir,
      simOutDir
    )

  val loweringOptions = argVal(
    "loweringOptions",
    "disallowLocalVariables,disallowPackedArrays,mitigateVivadoArrayIndexConstPropBug"
  )
  ChiselStage.emitSystemVerilogFile(
    new vta.test.VTAPostSynthTb(memoryConfigs, launchParams, perLayerTimeout),
    args = Array("--target-dir", outputDir.toString(), "--split-verilog"),
    firtoolOpts = Array(s"--lowering-options=$loweringOptions")
  )

  println(
    s"[EmitPostSynthTb] SV written to $outputDir; .mem files in $memOutDir; " +
      s"layers=${layers.mkString(",")}"
  )
}

object DefaultF1ConfigEmitter extends EmitterApp(new DefaultF1Config) {
  ChiselStage.emitSystemVerilog(new XilinxShell, args)
}

object DefaultDe10ConfigEmitter extends EmitterApp(new DefaultDe10Config) {
  ChiselStage.emitSystemVerilog(new IntelShell, args)
}

object TestDefaultF1Config extends EmitterApp(new DefaultF1Config) {
  ChiselStage.emitSystemVerilog(new Test, args)
}

object TestDefaultDe10Config extends EmitterApp(new DefaultF1Config) {
  implicit val p: Parameters = new DefaultDe10Config
  ChiselStage.emitSystemVerilog(new Test, args)
}
