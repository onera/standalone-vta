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

package simulatorTest.isa

import chisel3._
import chisel3.util.BitPat
import org.scalatest.matchers.should.Matchers

import vta.core._
import vta.tags.UnitTests
import vta.util.AnyFlatSpecSim

/** IsaConsistencySpec - pin the two ISA encodings together.
  *
  * The instruction set is described twice: the `ISA` object builds matching
  * `BitPat`s positionally (taskId/memId/aluId at fixed offsets), while the
  * `*Decode` Bundles extract fields by declaration order. Nothing keeps the two
  * in sync, so a width/offset drift would silently misalign decode (a live
  * suspect for the post-MaxPool2 hang). This spec decodes each `ISA.*`
  * instruction through the real decoders and asserts the op field, the
  * Fetch/Compute classification, and the ALU sub-opcode position all agree.
  */
class IsaProbe extends Module {
  val io = IO(new Bundle {
    val inst = Input(UInt(INST_BITS.W))
    val memOp = Output(UInt(OP_BITS.W))
    val aluOp = Output(UInt(C_ALU_OP_BITS.W))
    val isLoad = Output(Bool())
    val isCompute = Output(Bool())
    val isStore = Output(Bool())
    val isLoadUop = Output(Bool())
    val isLoadAcc = Output(Bool())
    val isAlu = Output(Bool())
    val isGemm = Output(Bool())
    val isFinish = Output(Bool())
  })
  val fetch = Module(new FetchDecode)
  val comp = Module(new ComputeDecode)
  fetch.io.inst := io.inst
  comp.io.inst := io.inst
  // op is the low 3 bits in every decode Bundle; alu_op position is what the
  // ALU datapath relies on lining up with the aluId baked into the BitPat.
  io.memOp := io.inst.asTypeOf(new MemDecode).op
  io.aluOp := io.inst.asTypeOf(new AluDecode).alu_op
  io.isLoad := fetch.io.isLoad
  io.isCompute := fetch.io.isCompute
  io.isStore := fetch.io.isStore
  io.isLoadUop := comp.io.isLoadUop
  io.isLoadAcc := comp.io.isLoadAcc
  io.isAlu := comp.io.isAlu
  io.isGemm := comp.io.isGemm
  io.isFinish := comp.io.isFinish
}

@UnitTests
class IsaConsistencySpec extends AnyFlatSpecSim with Matchers {
  behavior of "ISA encoding consistency"

  // Concrete instruction word from a BitPat, don't-care bits resolved to 0.
  private def word(bp: BitPat): BigInt = bp.value

  // xsize occupies the bits above op, deps, id, sram/dram offsets, the 6-bit
  // reserved field, and ysize in MemDecode. ComputeDecode/LoadDecode treat a
  // zero xsize as a sync, so loads must carry a nonzero xsize to be classified.
  private val xsizeLsb =
    OP_BITS + 4 /* deps */ + M_ID_BITS + M_SRAM_OFFSET_BITS +
      M_DRAM_OFFSET_BITS + 6 /* reserved */ + M_SIZE_BITS /* ysize */
  private def withXsize(v: BigInt): BigInt = v | (BigInt(1) << xsizeLsb)

  private sealed trait Route
  private case object RLoad extends Route
  private case object RCompute extends Route
  private case object RStore extends Route

  private sealed trait Cls
  private case object CLoadUop extends Cls
  private case object CLoadAcc extends Cls
  private case object CAlu extends Cls
  private case object CGemm extends Cls
  private case object CFinish extends Cls
  private case object CNone extends Cls

  private case class Case(
      name: String,
      inst: BigInt,
      op: BigInt,
      route: Route,
      cls: Cls,
      aluId: Option[BigInt]
  )

  private val cases = Seq(
    Case(
      "LUOP",
      withXsize(word(ISA.LUOP)),
      OP_L.litValue,
      RCompute,
      CLoadUop,
      None
    ),
    Case("LWGT", word(ISA.LWGT), OP_L.litValue, RLoad, CNone, None),
    Case("LINP", word(ISA.LINP), OP_L.litValue, RLoad, CNone, None),
    Case(
      "LACC",
      withXsize(word(ISA.LACC)),
      OP_L.litValue,
      RCompute,
      CLoadAcc,
      None
    ),
    Case("SOUT", word(ISA.SOUT), OP_S.litValue, RStore, CNone, None),
    Case("GEMM", word(ISA.GEMM), OP_G.litValue, RCompute, CGemm, None),
    Case("FNSH", word(ISA.FNSH), OP_F.litValue, RCompute, CFinish, None),
    Case(
      "VMIN",
      word(ISA.VMIN),
      OP_A.litValue,
      RCompute,
      CAlu,
      Some(BigInt(0))
    ),
    Case(
      "VMAX",
      word(ISA.VMAX),
      OP_A.litValue,
      RCompute,
      CAlu,
      Some(BigInt(1))
    ),
    Case(
      "VADD",
      word(ISA.VADD),
      OP_A.litValue,
      RCompute,
      CAlu,
      Some(BigInt(2))
    ),
    Case("VSHX", word(ISA.VSHX), OP_A.litValue, RCompute, CAlu, Some(BigInt(3)))
  )

  it should "decode every ISA instruction consistently with the decode Bundles" in {
    simulate(new IsaProbe) { dut =>
      for (c <- cases) {
        withClue(s"[${c.name}] ") {
          dut.io.inst.poke(c.inst.U(INST_BITS.W))
          dut.clock.step()

          dut.io.memOp.peek().litValue shouldBe c.op

          // Fetch routing is exactly one-hot per instruction.
          dut.io.isLoad.peekBoolean() shouldBe (c.route == RLoad)
          dut.io.isCompute.peekBoolean() shouldBe (c.route == RCompute)
          dut.io.isStore.peekBoolean() shouldBe (c.route == RStore)

          dut.io.isLoadUop.peekBoolean() shouldBe (c.cls == CLoadUop)
          dut.io.isLoadAcc.peekBoolean() shouldBe (c.cls == CLoadAcc)
          dut.io.isAlu.peekBoolean() shouldBe (c.cls == CAlu)
          dut.io.isGemm.peekBoolean() shouldBe (c.cls == CGemm)
          dut.io.isFinish.peekBoolean() shouldBe (c.cls == CFinish)

          c.aluId.foreach { id =>
            dut.io.aluOp.peek().litValue shouldBe id
          }
        }
      }
    }
  }
}
