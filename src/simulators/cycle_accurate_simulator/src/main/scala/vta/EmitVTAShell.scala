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

import chisel3._
import circt.stage.ChiselStage
import vta.util.config._
import vta.shell._

/** Emit VTAShell as SystemVerilog for Verilator.
  *
  * Usage (from cycle_accurate_simulator/): ./mill emitVerilog
  *
  * Or directly: java -cp <classpath> vta.EmitVTAShell [output-dir]
  *
  * The default output directory is build/emitted/vta-shell (one level above the
  * mill build root, i.e., next to the cycle_accurate_simulator/ directory).
  */
object EmitVTAShell extends App {
  val outDir = if (args.nonEmpty) args(0) else "build/emitted/vta-shell"

  implicit val p: Parameters = new DefaultPynqConfig

  ChiselStage.emitSystemVerilogFile(
    new VTAShell(debug = true),
    args = Array(
      "--target-dir",
      outDir
    )
    // firtoolOpts = Array(
    //   "-disable-all-randomization",
    //   "-strip-debug-info"
    // )
  )

  println(s"[EmitVTAShell] VTAShell.sv written to $outDir/")
}
