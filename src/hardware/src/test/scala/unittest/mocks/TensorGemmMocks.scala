package unittest.mocks

import chisel3._
import chisel3.simulator.PeekPokeAPI
import vta.core._

object TensorGemmMocks extends PeekPokeAPI {

  class TensorMasterMock(tm: TensorMaster) {
    tm.rd(0).data.valid.poke(0)
    var valid = tm.rd(0).idx.valid.peek()
    def logical_step(v: Option[BigInt]): Unit = {
      tm.rd(0).data.valid.poke(valid)
      valid = tm.rd(0).idx.valid.peek()
      for { x <- v } tm.rd(0).idx.valid.expect(x)
    }
  }

  class UopMasterMock(um: UopMaster) {
    um.data.valid.poke(0)
    var valid = um.idx.valid.peek()
    def logical_step(v: Option[BigInt]): Unit = {
      um.data.valid.poke(valid)
      valid = um.idx.valid.peek()
      for { x <- v } um.idx.valid.expect(x)
    }
  }

  class Mocks(c: TensorGemmIfc) {
    val uop_mock = new UopMasterMock(c.io.uop)
    val inp_mock = new TensorMasterMock(c.io.inp)
    val wgt_mock = new TensorMasterMock(c.io.wgt)
    val acc_mock = new TensorMasterMock(c.io.acc)

    val uop_indices = new scala.collection.mutable.Queue[BigInt]
    val acc_indices = new scala.collection.mutable.Queue[BigInt]
    val inp_indices = new scala.collection.mutable.Queue[BigInt]
    val wgt_indices = new scala.collection.mutable.Queue[BigInt]
    val accout_indices = new scala.collection.mutable.Queue[BigInt]
    val out_indices = new scala.collection.mutable.Queue[BigInt]

    def logical_step(
        sram_valid: Option[BigInt] = None,
        uop_valid: Option[BigInt] = None
    ): Unit = {
      c.clock.step(1)
      uop_mock.logical_step(uop_valid)
      inp_mock.logical_step(sram_valid)
      wgt_mock.logical_step(sram_valid)
      acc_mock.logical_step(sram_valid)
      if (uop_indices.nonEmpty && c.io.uop.idx.valid.peekBoolean()) {
        c.io.uop.idx.bits.expect(uop_indices.dequeue())
      }
      if (acc_indices.nonEmpty && c.io.acc.rd(0).idx.valid.peekBoolean()) {
        c.io.acc.rd(0).idx.bits.expect(acc_indices.dequeue())
      }
      if (inp_indices.nonEmpty && c.io.inp.rd(0).idx.valid.peekBoolean()) {
        c.io.inp.rd(0).idx.bits.expect(inp_indices.dequeue())
      }
      if (wgt_indices.nonEmpty && c.io.wgt.rd(0).idx.valid.peekBoolean()) {
        c.io.wgt.rd(0).idx.bits.expect(wgt_indices.dequeue())
      }
      if (accout_indices.nonEmpty && c.io.acc.wr(0).valid.peekBoolean()) {
        c.io.acc.wr(0).bits.idx.expect(accout_indices.dequeue())
      }
      if (out_indices.nonEmpty && c.io.out.wr(0).valid.peekBoolean()) {
        c.io.out.wr(0).bits.idx.expect(out_indices.dequeue())
      }
    }

    def test_if_done(withAssert: Boolean = false): Unit = {
      println(s"uop_indices remaining: ${uop_indices.size}")
      println(s"acc_indices remaining: ${acc_indices.size}")
      println(s"inp_indices remaining: ${inp_indices.size}")
      println(s"wgt_indices remaining: ${wgt_indices.size}")
      println(s"accout_indices remaining: ${accout_indices.size}")
      println(s"out_indices remaining: ${out_indices.size}")
      if (withAssert) {
        assert(uop_indices.isEmpty)
        assert(acc_indices.isEmpty)
        assert(inp_indices.isEmpty)
        assert(wgt_indices.isEmpty)
        assert(accout_indices.isEmpty)
        assert(out_indices.isEmpty)
      }
    }
  }
}
class TensorGemmGenericTester[T <: TensorGemmIfc](c: T) extends PeekPokeAPI {

  def initialProcedure(
      uopBegin: Int,
      uopEnd: Int,
      lp0: Int,
      lp1: Int,
      acc0: Int,
      acc1: Int,
      inp0: Int,
      inp1: Int,
      wgt0: Int,
      wgt1: Int,
      u0: BigInt,
      u1: BigInt,
      u2: BigInt
  ) = {

    require(uopBegin < uopEnd, "uop begin cannot be greater than uop end")
    c.io.flush.poke(0)
    c.io.dec.reset.poke(0)
    c.io.dec.uopBegin.poke(uopBegin)
    c.io.dec.uopEnd.poke(uopEnd)
    c.io.dec.lp0.poke(lp0)
    c.io.dec.lp1.poke(lp1)
    c.io.dec.acc0.poke(acc0)
    c.io.dec.acc1.poke(acc1)
    c.io.dec.inp0.poke(inp0)
    c.io.dec.inp1.poke(inp1)
    c.io.dec.wgt0.poke(wgt0)
    c.io.dec.wgt1.poke(wgt1)

    c.io.uop.data.bits.u0.poke(u0)
    c.io.uop.data.bits.u1.poke(u1)
    c.io.uop.data.bits.u2.poke(u2)
  }

  def pokeInputs(
      inp: IndexedSeq[BigInt],
      wgt: IndexedSeq[BigInt],
      acc: IndexedSeq[BigInt]
  ) = {

    require(inp.size == c.io.inp.rd.head.data.bits.head.size)
    require(wgt.size == c.io.wgt.rd.head.data.bits.head.size)
    require(acc.size == c.io.acc.rd.head.data.bits.head.size)
    for { lhs <- c.io.inp.rd(0).data.bits } {
      lhs.zip(inp.reverse).foreach { case (p, s) => p.poke(s) }
    }

    for { lhs <- c.io.wgt.rd(0).data.bits } {
      lhs.zip(wgt.reverse).foreach { case (p, s) => p.poke(s) }
    }

    for { lhs <- c.io.acc.rd(0).data.bits } {
      lhs.zip(acc.reverse).foreach { case (p, s) => p.poke(s) }
    }
  }
  val mocks = new TensorGemmMocks.Mocks(c)
}
class TensorGemmTester(c: TensorGemmSimple) extends TensorGemmGenericTester(c) {
  initialProcedure(
    uopBegin = 0,
    uopEnd = 1,
    lp0 = 1,
    lp1 = 1,
    acc0 = 1,
    acc1 = 1,
    inp0 = 1,
    inp1 = 1,
    wgt0 = 1,
    wgt1 = 1,
    u0 = 0,
    u1 = 0,
    u2 = 0
  )
  val inp = IndexedSeq.fill(c.io.inp.rd(0).data.bits(0).size) { BigInt(1) }

  val wgt = IndexedSeq.fill(c.io.wgt.rd(0).data.bits(0).size) { BigInt(1) }

  val acc = IndexedSeq.fill(c.io.acc.rd(0).data.bits(0).size) { BigInt(1) }

  pokeInputs(inp, wgt, acc)

  c.clock.step()

  c.io.state.expect(c.sIdle)

  c.io.start.poke(true)
  mocks.logical_step(Some(0), Some(1))
  c.io.state.expect(c.sReadUop)

  c.io.out.wr(0).valid.expect(0)
  c.io.acc.wr(0).valid.expect(0)

  c.io.start.poke(0)

  mocks.logical_step(Some(0), Some(0))
  c.io.state.expect(c.sComputeIdx)
  c.io.out.wr(0).valid.expect(0)
  c.io.acc.wr(0).valid.expect(0)

  mocks.logical_step(Some(1), Some(0))
  c.io.state.expect(c.sReadTensor)
  c.io.out.wr(0).valid.expect(0)
  c.io.acc.wr(0).valid.expect(0)

  mocks.logical_step(Some(0), Some(0))
  c.io.state.expect(c.sExe)
  c.io.out.wr(0).valid.expect(0)
  c.io.acc.wr(0).valid.expect(0)
  c.io.done.expect(0)

  mocks.logical_step(Some(0), Some(0))
  c.io.state.expect(c.sWait)
  c.io.inflight.expect(1)

  c.io.out.wr(0).valid.expect(0)
  c.io.acc.wr(0).valid.expect(0)

  mocks.logical_step(Some(0), Some(0))
  c.io.state.expect(c.sWait)
  c.io.inflight.expect(1)

  c.io.out.wr(0).valid.expect(1)
  c.io.acc.wr(0).valid.expect(1)

  mocks.logical_step(Some(0), Some(0))
  c.io.state.expect(c.sWait)
  c.io.inflight.expect(0)

  c.io.out.wr(0).valid.expect(0)
  c.io.acc.wr(0).valid.expect(0)

  mocks.logical_step(Some(0), Some(0))
  c.io.state.expect(c.sIdle)
  c.io.inflight.expect(0)

  c.io.out.wr(0).valid.expect(0)
  c.io.acc.wr(0).valid.expect(0)

}
class TensorGemmIndexGeneratorTester(
    c: TensorGemmIndexGenerator,
    debug: Boolean = false
) extends PeekPokeAPI {
  val uopBegin = 0
  val uopEnd = 2
  assert(uopBegin < uopEnd)
  val lp0 = 2
  val lp1 = 3
  val acc0 = 1 * lp1
  val inp0 = 2 * lp1
  val wgt0 = 4 * lp1
  val acc1 = 1
  val inp1 = 2
  val wgt1 = 4

  c.io.dec.reset.poke(0)
  c.io.dec.uopBegin.poke(uopBegin)
  c.io.dec.uopEnd.poke(uopEnd)
  c.io.dec.lp0.poke(lp0)
  c.io.dec.lp1.poke(lp1)
  c.io.dec.acc0.poke(acc0)
  c.io.dec.acc1.poke(acc1)
  c.io.dec.inp0.poke(inp0)
  c.io.dec.inp1.poke(inp1)
  c.io.dec.wgt0.poke(wgt0)
  c.io.dec.wgt1.poke(wgt1)
  c.io.flush.poke(0)
  // Don't need empty_0,{push,pop}_{next,prev},op

  class Mocks {
    val uop_indices = new scala.collection.mutable.Queue[BigInt]
    val acc_indices = new scala.collection.mutable.Queue[BigInt]
    val inp_indices = new scala.collection.mutable.Queue[BigInt]
    val wgt_indices = new scala.collection.mutable.Queue[BigInt]

    def logical_step(): Unit = {
      c.clock.step(1)
      if (c.io.valid.peekBoolean()) {
        c.io.uop_idx.expect(uop_indices.dequeue())
        c.io.acc_i.expect(acc_indices.dequeue())
        c.io.inp_i.expect(inp_indices.dequeue())
        c.io.wgt_i.expect(wgt_indices.dequeue())
      }
    }

    def test_if_done(): Unit = {
      if (debug) {
        println(s"uop_indices remaining: ${uop_indices.size}")
        println(s"acc_indices remaining: ${acc_indices.size}")
        println(s"inp_indices remaining: ${inp_indices.size}")
        println(s"wgt_indices remaining: ${wgt_indices.size}")
      }
      assert(uop_indices.isEmpty)
      assert(acc_indices.isEmpty)
      assert(inp_indices.isEmpty)
      assert(wgt_indices.isEmpty)
    }
  }

  val mocks = new Mocks
  for {
    cnt_o <- 0 until lp0
    cnt_i <- 0 until lp1
    uop_idx <- uopBegin until uopEnd
  } {
    mocks.uop_indices.enqueue(uop_idx)
    mocks.acc_indices.enqueue(acc0 * cnt_o + acc1 * cnt_i)
    mocks.inp_indices.enqueue(inp0 * cnt_o + inp1 * cnt_i)
    mocks.wgt_indices.enqueue(wgt0 * cnt_o + wgt1 * cnt_i)
  }

  c.io.start.poke(1)
  mocks.logical_step()
  c.io.start.poke(0)

  val end = (uopEnd - uopBegin) * lp0 * lp1
  var count = 0
  while (!c.io.last.peekBoolean() && count < 10 * end + 100) {
    mocks.logical_step()
    count += 1
  }
  mocks.test_if_done()
}
class TensorGemmPipelinedTester(
    c: TensorGemmPipelinedSplit,
    debug: Boolean = false
) extends PeekPokeAPI {
  c.io.start.poke(0)
  c.io.flush.poke(0)

  val uopBegin = 0
  val uopEnd = 2
  assert(uopBegin < uopEnd)
  val lp0 = 2
  val lp1 = 3
  val acc0 = 1 * lp1
  val inp0 = 2 * lp1
  val wgt0 = 4 * lp1
  val acc1 = 1
  val inp1 = 2
  val wgt1 = 4
  val u0 = BigInt("000", 16)
  val u1 = BigInt("100", 16)
  val u2 = BigInt("200", 16)

  c.io.dec.reset.poke(0)
  c.io.dec.uopBegin.poke(uopBegin)
  c.io.dec.uopEnd.poke(uopEnd)
  c.io.dec.lp0.poke(lp0)
  c.io.dec.lp1.poke(lp1)
  c.io.dec.acc0.poke(acc0)
  c.io.dec.acc1.poke(acc1)
  c.io.dec.inp0.poke(inp0)
  c.io.dec.inp1.poke(inp1)
  c.io.dec.wgt0.poke(wgt0)
  c.io.dec.wgt1.poke(wgt1)
  // Don't need empty_0,{push,pop}_{next,prev},op

  c.io.uop.data.bits.u0.poke(u0)
  c.io.uop.data.bits.u1.poke(u1)
  c.io.uop.data.bits.u2.poke(u2)

  val inp = IndexedSeq.fill(c.io.inp.rd(0).data.bits(0).size) { BigInt(1) }
  for { lhs <- c.io.inp.rd(0).data.bits } {
    lhs.zip(inp.reverse).foreach { case (p, s) => p.poke(s) }
  }

  val wgt = IndexedSeq.fill(c.io.wgt.rd(0).data.bits(0).size) { BigInt(1) }
  for { lhs <- c.io.wgt.rd(0).data.bits } {
    lhs.zip(wgt.reverse).foreach { case (p, s) => p.poke(s) }
  }

  val acc = IndexedSeq.fill(c.io.acc.rd(0).data.bits(0).size) { BigInt(1) }
  for { lhs <- c.io.acc.rd(0).data.bits } {
    lhs.zip(acc.reverse).foreach { case (p, s) => p.poke(s) }
  }

  val mocks = new TensorGemmMocks.Mocks(c)
  for {
    cnt_o <- 0 until lp0
    cnt_i <- 0 until lp1
    uop_idx <- uopBegin until uopEnd
  } {
    mocks.uop_indices.enqueue(uop_idx)
    mocks.acc_indices.enqueue(u0 + acc0 * cnt_o + acc1 * cnt_i)
    mocks.inp_indices.enqueue(u1 + inp0 * cnt_o + inp1 * cnt_i)
    mocks.wgt_indices.enqueue(u2 + wgt0 * cnt_o + wgt1 * cnt_i)
    mocks.accout_indices.enqueue(u0 + acc0 * cnt_o + acc1 * cnt_i)
    mocks.out_indices.enqueue(u0 + acc0 * cnt_o + acc1 * cnt_i)
  }

  c.io.start.poke(0)
  c.clock.step(1)
  c.io.state.expect(c.sIdle)
  c.io.start.poke(1)

  var count = 0
  val end = (uopEnd - uopBegin) * lp0 * lp1

  while (!c.io.done.peekBoolean() && count < 10 * end + 100) {
    mocks.logical_step()
    c.io.start.poke(0)
  }

  c.io.done.expect(1)
  if (debug) {
    mocks.test_if_done()
  }
}
class TensorGemmResetTester(c: TensorGemm) extends TensorGemmGenericTester(c) {
  c.io.start.poke(0)
  val uopBegin = 0
  val uopEnd = 2
  val lp0 = 2
  val lp1 = 3
  val acc0 = 1 * lp1
  val inp0 = 2 * lp1
  val wgt0 = 4 * lp1
  val acc1 = 1
  val inp1 = 2
  val wgt1 = 4
  val u0 = BigInt("000", 16)
  val u1 = BigInt("100", 16)
  val u2 = BigInt("200", 16)
  val dec_reset = 1

  initialProcedure(
    uopBegin,
    uopEnd,
    lp0,
    lp1,
    acc0,
    acc1,
    inp0,
    inp1,
    wgt0,
    wgt1,
    u0,
    u1,
    u2
  )

  val inp = IndexedSeq.fill(c.io.inp.rd(0).data.bits(0).size) { BigInt(1) }

  val wgt = IndexedSeq.fill(c.io.wgt.rd(0).data.bits(0).size) { BigInt(1) }

  val acc = IndexedSeq.fill(c.io.acc.rd(0).data.bits(0).size) { BigInt(1) }

  pokeInputs(inp, wgt, acc)

  for {
    cnt_o <- 0 until lp0
    cnt_i <- 0 until lp1
    uop_idx <- uopBegin until uopEnd
  } {
    mocks.uop_indices.enqueue(uop_idx)
    mocks.acc_indices.enqueue(u0 + acc0 * cnt_o + acc1 * cnt_i)
    mocks.inp_indices.enqueue(u1 + inp0 * cnt_o + inp1 * cnt_i)
    mocks.wgt_indices.enqueue(u2 + wgt0 * cnt_o + wgt1 * cnt_i)
    mocks.accout_indices.enqueue(u0 + acc0 * cnt_o + acc1 * cnt_i)

    if (dec_reset == 0) {
      mocks.out_indices.enqueue(u0 + acc0 * cnt_o + acc1 * cnt_i)
    }
  }

  c.io.start.poke(0)
  c.clock.step(1)
  c.io.state.expect(c.sIdle)
  c.io.start.poke(1)

  while (!c.io.done.peekBoolean()) {
    mocks.logical_step(None, None)
    c.io.start.poke(0)
  }

  mocks.test_if_done()
}

class TensorGemmIdxTester(c: TensorGemmSimple)
    extends TensorGemmGenericTester(c) {

  c.io.start.poke(0)

  val uopBegin = 0
  val uopEnd = 2
  val lp0 = 2
  val lp1 = 3
  val acc0 = 1 * lp1
  val inp0 = 2 * lp1
  val wgt0 = 4 * lp1
  val acc1 = 1
  val inp1 = 2
  val wgt1 = 4
  val u0 = BigInt("000", 16)
  val u1 = BigInt("100", 16)
  val u2 = BigInt("200", 16)
  initialProcedure(
    uopBegin = uopBegin,
    uopEnd = uopEnd,
    lp0 = lp0,
    lp1 = lp1,
    acc0 = acc0,
    acc1 = acc1,
    inp0 = inp0,
    inp1 = inp1,
    wgt0 = wgt0,
    wgt1 = wgt1,
    u0 = u0,
    u1 = u1,
    u2 = u2
  )

  val inp = IndexedSeq.fill(c.io.inp.rd(0).data.bits(0).size) { BigInt(1) }
  val wgt = IndexedSeq.fill(c.io.wgt.rd(0).data.bits(0).size) { BigInt(1) }
  val acc = IndexedSeq.fill(c.io.acc.rd(0).data.bits(0).size) { BigInt(1) }
  pokeInputs(inp, wgt, acc)

  for {
    cnt_o <- 0 until lp0
    cnt_i <- 0 until lp1
    uop_idx <- uopBegin until uopEnd
  } {
    mocks.uop_indices.enqueue(uop_idx)
    mocks.acc_indices.enqueue(u0 + acc0 * cnt_o + acc1 * cnt_i)
    mocks.inp_indices.enqueue(u1 + inp0 * cnt_o + inp1 * cnt_i)
    mocks.wgt_indices.enqueue(u2 + wgt0 * cnt_o + wgt1 * cnt_i)
    mocks.accout_indices.enqueue(u0 + acc0 * cnt_o + acc1 * cnt_i)
    mocks.out_indices.enqueue(u0 + acc0 * cnt_o + acc1 * cnt_i)
  }

  c.io.start.poke(0)
  c.clock.step(1)
  c.io.state.expect(c.sIdle)

  c.io.start.poke(1)

  for { q <- 0 until (uopEnd - uopBegin) * lp0 * lp1 } {
    mocks.logical_step(Some(0), Some(1))
    c.io.out.wr(0).valid.expect(0)
    c.io.acc.wr(0).valid.expect(0)

    c.io.start.poke(0)

    mocks.logical_step(Some(0), Some(0))
    c.io.out.wr(0).valid.expect(if (q > 0) 1 else 0)
    c.io.acc.wr(0).valid.expect(if (q > 0) 1 else 0)

    mocks.logical_step(Some(1), Some(0))
    c.io.out.wr(0).valid.expect(0)
    c.io.acc.wr(0).valid.expect(0)

    mocks.logical_step(Some(0), Some(0))
    c.io.out.wr(0).valid.expect(0)
    c.io.acc.wr(0).valid.expect(0)
    c.io.done.expect(0)
  }

  mocks.logical_step(Some(0), Some(0))
  c.io.inflight.expect(1)

  c.io.out.wr(0).valid.expect(0)
  c.io.acc.wr(0).valid.expect(0)

  mocks.logical_step(Some(0), Some(0))
  c.io.inflight.expect(1)

  c.io.out.wr(0).valid.expect(1)
  c.io.acc.wr(0).valid.expect(1)

  mocks.logical_step(Some(0), Some(0))
  c.io.inflight.expect(0)

  c.io.out.wr(0).valid.expect(0)
  c.io.acc.wr(0).valid.expect(0)

  mocks.logical_step(Some(0), Some(0))
  c.io.inflight.expect(0)

  c.io.out.wr(0).valid.expect(0)
  c.io.acc.wr(0).valid.expect(0)

  mocks.test_if_done()
}
