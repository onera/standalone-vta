package vta.test

import chisel3._
import chisel3.simulator.scalatest.ChiselSim
import chisel3.util.experimental.loadMemoryFromFileInline
import chisel3.util.{MuxCase, log2Ceil}
import org.scalatest.flatspec.AnyFlatSpec
import vta.interface.axi.AxiLike._
import vta.interface.axi.{AXIClient, AXIParams}
import vta.models.MemoryConfig
import vta.util.EnableMemInit
import vta.util.SimulationUtils.verilatorWithWaveDump

/** A simulation utility module to connect several memories (sync write async
  * read)
  *
  * @param memoryConfigs
  *   the configuration of each memory
  * @param enforceOutBounds
  *   when true (default), emit a runtime assertion that every AXI write burst
  *   lies fully inside some OUT-named region.
  * @param param
  *   the AXI parameters configuration
  */
class MultiMemAxiClient(
  memoryConfigs: Seq[MemoryConfig],
  enforceOutBounds: Boolean = true
)(implicit val param: AXIParams)
    extends Module {
  val io = IO(new AXIClient(param))

  val readEnable = RegInit(true.B)
  val writeEnable = RegInit(true.B)
  val readHandle = io.readHandler(readEnable)
  val writeHandle = io.writeHandler(writeEnable)

  // AXI AxADDR is a *byte* address. The memories below are 64-bit-word
  // wide and word-indexed, so a byte address must be divided by the data-bus
  // byte width to obtain a word index. baseAddress/words64 are likewise the
  // byte base and the 64-bit-word count of each region.
  val bytesPerWord = param.dataBits / 8
  val wordShift = log2Ceil(bytesPerWord)

  def enCondition(bAddr: BigInt, hAddr: BigInt, addressW: UInt) =
    bAddr.U <= addressW && addressW < (hAddr).U
  val memories = memoryConfigs.map { p =>
    val m = Mem(p.words64, UInt(param.dataBits.W))
      .suggestName(s"memory_${p.name}")

    if (p.path.trim().nonEmpty) {
      loadMemoryFromFileInline(m, p.path)
    }

    val highByteAddr = p.baseAddress + p.words64 * bytesPerWord
    (
      enCondition(p.baseAddress, highByteAddr, writeHandle),
      enCondition(p.baseAddress, highByteAddr, readHandle),
      m,
      p
    )
  }

  // Allow any entry whose name starts with "OUT" to receive AXI writes.;
  // multi-layer harnesses can pass several OUT_<suffix> entries at non-overlapping addresses (per-layer
  // output buffers) and writes will be accepted if they fall in ANY of them.
  val outEntries = memoryConfigs.filter(_.name.startsWith("OUT"))
  require(
    outEntries.nonEmpty,
    "MultiMemAxiClient: at least one OUT-named region is required"
  )
  if (enforceOutBounds) {
    // io.aw.bits.len is a beat count (Length-1); the burst spans
    // len*bytesPerWord bytes above the start byte address.
    val awEndAddr = io.aw.bits.addr + (io.aw.bits.len << wordShift)
    val anyOutHit = outEntries
      .map { r =>
        val high = r.baseAddress + r.words64 * bytesPerWord
        (r.baseAddress.U <= io.aw.bits.addr) && (awEndAddr < high.U)
      }
      .reduce(_ || _)
    when(io.aw.fire) {
      assert(
        anyOutHit,
        cf"Trying to write at ${io.aw.bits.addr}:${awEndAddr}, outside of any OUT region"
      )
    }
  }
  val log = SimLog.file("output.log")
  val rdata = for {
    (isSelForWrite, isSelForRead, mem, p) <- memories
  } yield {

    if (p.logging) {
      // Log every accepted write beat for this region as
      //   <byteAddr> <data> <strb> <last>
      // (all hex except last). `writeHandle` is the per-beat byte address, so a
      // sparse/strobed store (block-4 OUT writes a 64-bit word in two partial
      // beats, strb 0x0f then 0xf0) is faithfully recoverable: a reader applies
      // `strb` per byte at `byteAddr` rather than assuming dense, sequential
      // writes. Logging only the two int32 halves with no address would silently
      // mis-attribute bytes whenever the store is not dense.
      when(io.w.fire && isSelForWrite) {
        log.printf(
          cf"${writeHandle}%x ${io.w.bits.data}%x ${io.w.bits.strb}%x ${io.w.bits.last}\n"
        )
      }
    }

    // Honor the AXI write-strobe (byte-enable) mask via read-modify-write.
    // Dense stores drive strb=all-ones (full beat); block-4 sparse/strided
    // stores drive partial strobes (e.g. 0x0f/0xf0) and must leave the masked
    // bytes untouched - matching dpi_mem.cc.
    when(io.w.fire && isSelForWrite) {
      val idx = (writeHandle - p.baseAddress.U) >> wordShift
      val curBytes = mem(idx).asTypeOf(Vec(bytesPerWord, UInt(8.W)))
      val newBytes = io.w.bits.data.asTypeOf(Vec(bytesPerWord, UInt(8.W)))
      val merged = VecInit((0 until bytesPerWord).map { b =>
        Mux(io.w.bits.strb(b), newBytes(b), curBytes(b))
      }).asUInt
      mem(idx) := merged
    }
    (
      isSelForRead,
      Mux(isSelForRead, mem((readHandle - p.baseAddress.U) >> wordShift), 0.U)
    )

  }

  io.r.bits.data := MuxCase(0.U, rdata)

  io.b.bits.user := DontCare
  io.r.bits.user := DontCare
}

class MultiMemAxiClientSpec
    extends AnyFlatSpec
    with ChiselSim
    with AxiFullSimUtils
    with EnableMemInit {
  behavior of "MultiMemAxiClient"

  it should "read a burst to the first memory and second memory" in {
    val path = os.pwd / "build" / "mem"
    implicit val param = AXIParams()
    implicit val withWaves = verilatorWithWaveDump
    simulate(
      new MultiMemAxiClient(
        Seq(
          MemoryConfig("INSN", (path / "INSN.mem").toString(), 0, 12, 24),
          MemoryConfig("UOP", (path / "UOP.mem").toString(), 100, 5, 3)
        )
      ),
      firtoolOpts = Array("--disable-mem-randomization")
    ) { dut =>
      implicit val axi = dut.io
      implicit val clock = dut.clock

      val rd0 = readAxiBurst(0, 3)
      println(rd0)
      val rd1 = readAxiBurst(100, 2)
      println(rd1)
      writeAxiBurst(0, Seq(1, 2, 3, 4, 5))
      writeAxiBurst(100, Seq(1, 2, 3))
      val rd2 = readAxiBurst(0, 5)
      val rd3 = readAxiBurst(100, 3)
      println(rd2)
      println(rd3)
    }
  }
}
