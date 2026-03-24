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
  val defaultDir: String = "build/emitted/default"
  def outputDir: String = if (args.nonEmpty) args(0) else defaultDir.toString()
}

object DefaultPynqConfig extends EmitterApp {
  override val defaultDir = "build/emitted/vta-xilinx-shell"
  implicit val p: Parameters = new DefaultPynqConfig
  ChiselStage.emitSystemVerilogFile(
    new XilinxShell,
    args = Array(
      "--target-dir",
      outputDir,
      "--split-verilog"
    ),
    firtoolOpts = Array(
      "--lowering-options=disallowLocalVariables,disallowPackedArrays"
    )
  )
}

object ZynqUs3Config extends EmitterApp {
  override val defaultDir = "build/emitted/vta-zusys-shell"
  implicit val p: Parameters = new ZusysConfig
  ChiselStage.emitSystemVerilogFile(
    new XilinxShell,
    args = Array(
      "--target-dir",
      outputDir,
      "--split-verilog"
    ),
    firtoolOpts = Array(
      "--lowering-options=disallowLocalVariables,disallowPackedArrays"
    )
  )
}

object StandaloneSimConfig extends EmitterApp {
  override val defaultDir = "build/emitted/vta-sim-shell"

  implicit val p: Parameters = new DefaultPynqConfig

  ChiselStage.emitSystemVerilogFile(
    new Test(true),
    args = Array("--target-dir", outputDir)
  )

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
