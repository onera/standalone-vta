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
import vta.util.config._
import vta.util.XilinxIpFlow.exportIpPackageTclScript
import os.RelPath

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
  def showConfig(implicit p: Parameters) = {
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
        println(
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
        )
    }
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
    displayName = "VTA_" + p(CoreKey).target
  )

}

object StandaloneSimConfig extends EmitterApp {
  override val defaultDir = os.RelPath("build/emitted/vta-sim-shell")

  implicit val p: Parameters = new DefaultPynqConfig

  ChiselStage.emitSystemVerilogFile(
    new Test(true),
    args = Array("--target-dir", outputDir.toString())
  )

  showConfig
  println(s"[EmitVTAShell] Simulation files written to $outputDir/")
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
