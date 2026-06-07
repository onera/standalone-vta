package simulatorTest.alu

import chisel3._
import chisel3.simulator.PeekPokeAPI
import vta.core._
import vta.util.config._
import vta.util.AnyFlatSpecSim
import vta.tags

/** Reproduction of the FPGA cascade live-lock where a layer following MaxPool2
  * hangs. The board ILA showed the ALU parked in sRun with a nonzero inflight
  * and the VME idle: the TensorAlu index generator was iterating against a
  * decode that no longer matched the instruction that legitimately started the
  * run (the queue head had moved off the ALU op), so its three nested terminal
  * counters never aligned and `io.last` never fired - Compute then waits on a
  * `done` that never comes.
  *
  * This test recreates that desync directly: start a well-formed, terminating
  * ALU op, then swap `io.dec` mid-run to a decode whose loop bounds are zero
  * (lp-1 underflows to 2^C_ITER_BITS-1, an unreachable terminal). On the fixed
  * RTL the run keeps iterating against the decode latched at start (capture_dec
  * / decStable) and reaches `done`. On the unfixed RTL (index generator reading
  * the live `io.dec`) it live-locks and `done` never asserts.
  */
class TensorAluHangRepro(c: TensorAlu) extends PeekPokeAPI {

  private def pokeDec(
      uopBegin: Int,
      uopEnd: Int,
      lp0: Int,
      lp1: Int,
      aluOp: Int,
      useImm: Int
  ): Unit = {
    c.io.dec.reset.poke(0)
    c.io.dec.uop_begin.poke(uopBegin)
    c.io.dec.uop_end.poke(uopEnd)
    c.io.dec.lp_0.poke(lp0)
    c.io.dec.lp_1.poke(lp1)
    c.io.dec.dst_0.poke(0)
    c.io.dec.dst_1.poke(0)
    c.io.dec.src_0.poke(0)
    c.io.dec.src_1.poke(0)
    c.io.dec.alu_op.poke(aluOp)
    c.io.dec.alu_use_imm.poke(useImm)
    c.io.dec.alu_imm.poke(0)
  }

  // Zero-returning acc read mock: drive data.valid one cycle after idx.valid
  // (matching the acc scratchpad read latency the TensorAlu pipeline expects)
  // and return zero data. Values are irrelevant here - the test only observes
  // FSM termination, not computed results.
  private class AccMock(tm: TensorMaster) {
    tm.rd(0).data.valid.poke(0)
    private var valid = tm.rd(0).idx.valid.peekBoolean()
    def step(): Unit = {
      if (valid) {
        tm.rd(0).data.valid.poke(1)
        val cols = tm.rd(0).data.bits(0).size
        for {
          i <- 0 until tm.rd(0).data.bits.size
          j <- 0 until cols
        } tm.rd(0).data.bits(i)(j).poke(0)
      } else {
        tm.rd(0).data.valid.poke(0)
      }
      valid = tm.rd(0).idx.valid.peekBoolean()
    }
  }

  private class UopMock(um: UopMaster) {
    um.data.valid.poke(0)
    private var valid = um.idx.valid.peekBoolean()
    def step(): Unit = {
      if (valid) {
        um.data.valid.poke(1)
        um.data.bits.u0.poke(0)
        um.data.bits.u1.poke(0)
        um.data.bits.u2.poke(0)
      } else {
        um.data.valid.poke(0)
      }
      valid = um.idx.valid.peekBoolean()
    }
  }

  // D1: a well-formed terminating op (16 index steps + a few pipeline cycles).
  // D2: zero loop bounds -> lp_1-1 / uop_end-1 underflow to 2^14-1, so the
  // terminal is unreachable within any sane cycle budget.
  val budget = 600
  val swapAt = 5

  c.io.start.poke(0)
  pokeDec(uopBegin = 0, uopEnd = 4, lp0 = 2, lp1 = 2, aluOp = 1, useImm = 1)
  c.clock.step(1)
  c.io.start.poke(1)

  private val accMock = new AccMock(c.io.acc)
  private val uopMock = new UopMock(c.io.uop)

  var count = 0
  var swapped = false
  while (!c.io.done.peekBoolean() && count < budget) {
    c.clock.step(1)
    accMock.step()
    uopMock.step()
    c.io.start.poke(0)
    count += 1
    if (count == swapAt && !swapped) {
      // Queue head moves off the ALU op mid-run: feed a garbage AluDecode.
      pokeDec(uopBegin = 0, uopEnd = 0, lp0 = 0, lp1 = 0, aluOp = 1, useImm = 1)
      swapped = true
    }
  }

  val finished = c.io.done.peekBoolean()
  require(
    finished,
    s"TensorAlu live-locked: io.done never asserted within $budget cycles " +
      s"after the decode was swapped mid-run (reproduces the FPGA cascade hang)"
  )
}

@tags.UnitTests
class TensorAluHangReproTest extends AnyFlatSpecSim {
  behavior of "TensorAlu under a mid-run decode change"

  it should "still reach done (no live-lock) when the queue head moves off the ALU op" in {
    simulate(new TensorAlu) { c =>
      new TensorAluHangRepro(c)
      ()
    }
  }
}
