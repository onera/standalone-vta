package vta.test

import chisel3._
import vta.util.config.Parameters
import vta.interface.axi.AXIClient
import chisel3.util.experimental.loadMemoryFromFileInline
import org.scalatest.flatspec.AnyFlatSpec
import chisel3.simulator.scalatest.ChiselSim
import vta.DefaultPynqConfig
import vta.util.SimulationUtils.EnableMemInitVerilog
import vta.util.SimulationUtils.verilatorWithWaveDump
import chisel3.util.MuxCase
import vta.interface.axi.AXIParams
import vta.util.MemoryConfig
import vta.interface.axi.AxiLike._

/** A simulation utility module to connect several memories (sync write async
  * read)
  *
  * @param memoryConfigs
  *   the configuration of each memory
  * @param param
  *   the AXI parameters configuration
  */
class MultiMemAxiClient(memoryConfigs: Seq[MemoryConfig])(implicit
    val param: AXIParams
) extends Module {
  val io = IO(new AXIClient(param))

  val readEnable = RegInit(true.B)
  val writeEnable = RegInit(true.B)
  val readHandle = io.readHandler(readEnable)
  val writeHandle = io.writeHandler(writeEnable)

  def enCondition(bAddr: BigInt, hAddr: BigInt, addressW: UInt) =
    bAddr.U <= addressW && addressW < (hAddr).U
  val memories = memoryConfigs.map { p =>
    val m = Mem(p.words64, UInt(param.dataBits.W))
      .suggestName(s"memory_${p.name}")

    if (p.path.trim().nonEmpty) {
      loadMemoryFromFileInline(m, p.path)
    }

    (
      enCondition(p.baseAddress, p.baseAddress + p.words64, writeHandle),
      enCondition(p.baseAddress, p.baseAddress + p.words64, readHandle),
      m,
      p
    )
  }

  val log = SimLog.file("output.log")
  val rdata = for {
    (isSelForWrite, isSelForRead, mem, p) <- memories
  } yield {

    if (p.logging) {
      // Log any written data in a logfile for the current memory
      when(io.w.fire) {
        val splitted = io.w.bits.data.asTypeOf(Vec(2, SInt(32.W)))
        splitted.foreach { e => log.printf(cf"${e}%0d\n") }

      }
    }

    when(io.w.fire && isSelForWrite) {
      mem(writeHandle - p.baseAddress.U) := io.w.bits.data
    }
    (isSelForRead, Mux(isSelForRead, mem(readHandle - p.baseAddress.U), 0.U))

  }

  io.r.bits.data := MuxCase(0.U, rdata)

  io.b.bits.user := DontCare
  io.r.bits.user := DontCare
}

class MultiMemAxiClientSpec
    extends AnyFlatSpec
    with ChiselSim
    with AxiFullSimUtils {
  behavior of "MultiMemAxiClient"

  it should "read a burst to the first memory and second memory" in {
    val path = os.pwd / "generatedResources"
    implicit val param = AXIParams()
    implicit val withWaves = verilatorWithWaveDump
    implicit val enableMemoryInit = EnableMemInitVerilog
    simulate(
      new MultiMemAxiClient(
        Seq(
          MemoryConfig("INSN", path + "/INSN.mem", 0, 12, 24),
          MemoryConfig("UOP", path + "/UOP.mem", 100, 5, 3)
        )
      ),
      firtoolOpts = Array("--disable-all-randomization")
    ) { dut =>
      enableWaves()
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
