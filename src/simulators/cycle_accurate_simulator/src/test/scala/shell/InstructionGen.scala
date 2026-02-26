package vta.shell
import chisel3._
import chisel3.util.Cat
import vta.core.ISAConstants

/** Instruction literal utils
  */
object InstructionGen {

  class InstructionLit extends ISAConstants

  case class Load() extends InstructionLit
  case class Store() extends InstructionLit
  case class Gemm(
      opcode: Int,
      deptFlag: Int,
      reset: Boolean,
      uopBegin: Int,
      uopEnd: Int,
      lpOut: Int,
      lpIn: Int,
      accIdxOut: Int,
      inpIdxOut: Int,
      inpIdxInt: Int,
      wgtIdxOut: Int,
      wgtIdxIn: Int
  ) extends InstructionLit {
    def asUInt() = {
      Cat(
        opcode.U(OP_BITS.W),
        deptFlag.U(M_DEP_BITS.W),
        reset.B,
        uopBegin.U(C_UOP_BGN_BITS.W),
        uopEnd.U(C_UOP_END_BITS.W)
      )
    }
  }
  case class Alu() extends InstructionLit
  case class Finish() extends InstructionLit
  case class Uop(accIdx: Int, inpIdx: Int, wgtIdx: Int) extends InstructionLit
}
