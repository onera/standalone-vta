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
import chisel3.util._
import vta.interface.axi.AxiLike._
import vta.interface.axi._
import vta.util.config._
import vta.util.genericbundle._

/** VCR parameters.
  *
  * These parameters are used on VCR interfaces and modules.
  */
case class VCRParams() {
  val nCtrl = 1
  val nECnt = 1
  val nVals = 1
  val nPtrs = 6
  val nUCnt = 1
  val regBits = 32
}

/** VCRBase. Parametrize base class. */
abstract class VCRBase(implicit p: Parameters)
    extends GenericParameterizedBundle(p)

/** VCRMaster.
  *
  * This is the master interface used by VCR in the VTAShell to control the Core
  * unit.
  */
class VCRMaster(implicit p: Parameters) extends VCRBase {
  val vp = p(ShellKey).vcrParams
  val mp = p(ShellKey).memParams
  val launch = Output(Bool())
  val finish = Input(Bool())
  val ecnt = Vec(vp.nECnt, Flipped(ValidIO(UInt(vp.regBits.W))))
  val vals = Output(Vec(vp.nVals, UInt(vp.regBits.W)))
  val ptrs = Output(Vec(vp.nPtrs, UInt(mp.addrBits.W)))
  val ucnt = Vec(vp.nUCnt, Flipped(ValidIO(UInt(vp.regBits.W))))
}

/** VCRClient.
  *
  * This is the client interface used by the Core module to communicate to the
  * VCR in the VTAShell.
  */
class VCRClient(implicit p: Parameters) extends VCRBase {
  val vp = p(ShellKey).vcrParams
  val mp = p(ShellKey).memParams
  val launch = Input(Bool())
  val finish = Output(Bool())
  val ecnt = Vec(vp.nECnt, ValidIO(UInt(vp.regBits.W)))
  val vals = Input(Vec(vp.nVals, UInt(vp.regBits.W)))
  val ptrs = Input(Vec(vp.nPtrs, UInt(mp.addrBits.W)))
  val ucnt = Vec(vp.nUCnt, ValidIO(UInt(vp.regBits.W)))
}

/** VTA Control Registers (VCR).
  *
  * This unit provides control registers (32 and 64 bits) to be used by a
  * control' unit, typically a host processor. These registers are read-only by
  * the core at the moment but this will likely change once we add support to
  * general purpose registers that could be used as event counters by the Core
  * unit.
  */
class VCR(implicit p: Parameters) extends Module {
  val io = IO(new Bundle {
    val host = new AXILiteClient(p(ShellKey).hostParams)
    val vcr = new VCRMaster
  })

  val vp = p(ShellKey).vcrParams
  val mp = p(ShellKey).memParams
  val hp = p(ShellKey).hostParams

  // Write and Read channels control
  val waddr = io.host.writeHandler(true.B)
  val raddr = io.host.readHandler(true.B)

  val wdata = io.host.w.bits.data
  val rdata = RegInit(0.U(vp.regBits.W))

  // registers
  val nPtrs = if (mp.addrBits == 32) vp.nPtrs else 2 * vp.nPtrs
  val nTotal = vp.nCtrl + vp.nECnt + vp.nVals + nPtrs + vp.nUCnt

  class VcrBundleReg extends Bundle {
    val ucnt = Vec(vp.nUCnt, UInt(32.W))
    val ptrs = Vec(nPtrs, UInt(vp.regBits.W))
    val vals = Vec(vp.nVals, UInt(32.W))
    val ecnt = Vec(vp.nECnt, UInt(32.W))
    val ctrl = UInt(32.W)
  }
  val regs = RegInit(0.U.asTypeOf(new VcrBundleReg))

  // View registers as a Vec
  val regVec = Wire(Vec(nTotal, UInt(32.W)))
  regVec := regs.asTypeOf(regVec)
  val addr = Seq.tabulate(nTotal)(_ * 4)
  val reg_map = (addr zip regVec) map { case (a, r) => a.U -> r }
  val eo = vp.nCtrl
  val vo = eo + vp.nECnt
  val po = vo + vp.nVals
  val uo = po + nPtrs

  io.host.r.bits.data := rdata

  // When VTA finishes, write a flag in ctrl register
  when(io.vcr.finish) {
    regs.ctrl := 2.U
  }.elsewhen(io.host.w.fire && addr(0).U === waddr) {
    regs.ctrl := wdata
  }

  for (i <- 0 until vp.nECnt) {
    when(io.vcr.ecnt(i).valid) {
      regs.ecnt(i) := io.vcr.ecnt(i).bits
    }.elsewhen(io.host.w.fire && addr(eo + i).U === waddr) {
      regs.ecnt(i) := wdata
    }
  }

  for (i <- 0 until (vp.nVals)) {
    when(io.host.w.fire && addr(vo + i).U === waddr) {
      regs.vals(i) := wdata
    }
  }

  for (i <- 0 until (vp.nPtrs)) {
    when(io.host.w.fire && addr(po + i).U === waddr) {
      regs.ptrs(i) := wdata
    }
  }
  io.host.r.bits.data := MuxLookup(raddr, 0.U)(reg_map)

  io.vcr.launch := regs.ctrl(0)

  for (i <- 0 until vp.nVals) {
    io.vcr.vals(i) := regs.vals(i)
  }

  if (mp.addrBits == 32) { // 32-bit pointers
    for (i <- 0 until nPtrs) {
      io.vcr.ptrs(i) := regs.ptrs(i)
    }
  } else { // 64-bits pointers
    for (i <- 0 until (nPtrs / 2)) {
      io.vcr.ptrs(i) := Cat(regs.ptrs(2 * i + 1), regs.ptrs(2 * i))
    }
  }

  for (i <- 0 until vp.nUCnt) {
    when(io.vcr.ucnt(i).valid) {
      regs.ucnt(i) := io.vcr.ucnt(i).bits
    }.elsewhen(io.host.w.fire && addr(uo + i).U === waddr) {
      regs.ucnt(i) := wdata
    }
  }
}
