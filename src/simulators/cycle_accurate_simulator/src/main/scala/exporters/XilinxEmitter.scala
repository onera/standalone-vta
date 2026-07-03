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
import vta.util.config.Parameters
import vta.exporters.XilinxIpPackager.writeTclScript
import vta.configs.DefaultPynqConfig

object XilinxEmit {
  val vendor = "onera"
  val lib = "user"
  val name = "VTA"
  val version = "0.2.0"

  /** The "Using following core config..." string, shared by
    * EmitterApp.getConfig and emitXilinx so both callers produce the identical
    * description.
    */
  def coreConfig(p: Parameters): String = {
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

  /** Emit the Xilinx shell SystemVerilog + package_ip.tcl into outDir. Returns
    * the VLNV string "vendor:lib:name:version".
    */
  def emitXilinx(
      outDir: os.Path
  )(implicit p: Parameters = new DefaultPynqConfig): String = {
    ChiselStage.emitSystemVerilogFile(
      new XilinxShell,
      args = Array("--target-dir", outDir.toString(), "--split-verilog"),
      firtoolOpts = Array(
        "--lowering-options=disallowLocalVariables,disallowPackedArrays,mitigateVivadoArrayIndexConstPropBug"
      )
    )
    writeTclScript(
      target = outDir,
      vendor = vendor,
      name = name,
      version = version,
      topModule = "VTAXilinxShell",
      displayName = "VTA_" + p(CoreKey).target,
      description =
        "Versatile Tensor Accelerator - Xilinx shell (AXI4-Lite ctrl + AXI4 DRAM)" + coreConfig(
          p
        )
    )
    s"$vendor:$lib:$name:$version"
  }
}
