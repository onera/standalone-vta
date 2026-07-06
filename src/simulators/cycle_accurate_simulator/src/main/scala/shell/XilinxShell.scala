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

package vta.shell

import chisel3._
import chisel3.experimental.dataview.DataViewable
import chisel3.util.experimental.BoringUtils
import vta.interface.axi._
import vta.util.config._

/** XilinxShell.
  *
  * This is a wrapper shell mostly used to match Xilinx convention naming,
  * therefore we can pack VTA as an IP for IPI based flows.
  */
class XilinxShell(implicit p: Parameters) extends RawModule {

  override def desiredName: String = "VTAXilinxShell"
  val hp = p(ShellKey).hostParams
  val mp = p(ShellKey).memParams

  val ap_clk = IO(Input(Clock()))
  val ap_rst_n = IO(Input(Bool()))
  val m_axi_gmem = IO(new XilinxAXIMaster(mp))
  val s_axi_control = IO(new XilinxAXILiteClient(hp))

  val shell = withClockAndReset(clock = ap_clk, reset = ~ap_rst_n) {
    Module(new VTAShell)
  }

  shell.io.mem <> m_axi_gmem.viewAs[AXIMaster]
  shell.io.host <> s_axi_control.viewAs[AXILiteClient]
}

class XilinxDebugShell(implicit p: Parameters) extends RawModule {

  override def desiredName: String = "VTAXilinxShell"
  val hp = p(ShellKey).hostParams
  val mp = p(ShellKey).memParams

  val ap_clk = IO(Input(Clock()))
  val ap_rst_n = IO(Input(Bool()))
  val m_axi_gmem = IO(new XilinxAXIMaster(mp))
  val s_axi_control = IO(new XilinxAXILiteClient(hp))

  val (shell, debug) = withClockAndReset(clock = ap_clk, reset = ~ap_rst_n) {
    val s = Module(new VTAShell)
    // Minimal observation probes, shared by the post-synthesis functional test
    // and on-board ILA bring-up: the VCR control register (bit 1 is `finish`),
    // the Compute FSM state, and Compute's `done` pulse. Bored from the core so
    // no IO is added to VTAShell itself, and not synthesized unless a consumer
    // reads them.
    val vcrCtrlW = RegNext(BoringUtils.bore(s.vcr.regs.ctrl))
    val computeStateW = RegNext(BoringUtils.bore(s.core.compute.state))
    val computeDoneW = RegNext(BoringUtils.bore(s.core.compute.done))

    val debug = IO(new Bundle {
      val vcrCtrl = Output(UInt(32.W))
      val computeState = Output(UInt(2.W))
      val computeDone = Output(Bool())
    })
    debug.vcrCtrl := vcrCtrlW
    debug.computeState := computeStateW
    debug.computeDone := computeDoneW
    (s, debug)
  }

  shell.io.mem <> m_axi_gmem.viewAs[AXIMaster]
  shell.io.host <> s_axi_control.viewAs[AXILiteClient]
}
