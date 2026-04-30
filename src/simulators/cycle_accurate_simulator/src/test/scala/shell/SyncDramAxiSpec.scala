package vta.shell
import chisel3._
import chisel3.util.experimental.loadMemoryFromFileInline
import vta.interface.axi.AXIClient
import vta.interface.axi.AxiLike._
import vta.util.config.Parameters
import vta.tags.tagObjects.UnitTests
import vta.util.AnyFlatSpecSim
import vta.util.SimulationUtils.EnableMemInitVerilog

class SyncAxiDram(memoryFile: String = "", size: Int)(implicit
    p: Parameters
) extends Module {
  val io = IO(new Bundle {
    val axis = new AXIClient(p(ShellKey).memParams)
  })

  val mem = Mem(size, UInt(p(ShellKey).memParams.dataBits.W))
  // Initialize memory
  if (memoryFile.trim().nonEmpty) {
    loadMemoryFromFileInline(mem, memoryFile)
  }
  val readHandle = io.axis.readHandler(true.B)
  val writeHandle = io.axis.writeHandler(true.B)
  io.axis.r.bits.data := mem(readHandle)
  when(io.axis.w.fire) {
    mem.write(writeHandle, io.axis.w.bits.data)
    io.axis.b.valid := true.B
  }

  io.axis.b.bits.user := DontCare
  io.axis.r.bits.user := DontCare
}

class SyncAxiDramSpec extends AnyFlatSpecSim with vta.test.AxiFullSimUtils {

  class InitMemInline(memoryFile: String = "", size: Int, width: Int)
      extends Module {
    val io = IO(new Bundle {
      val enable = Input(Bool())
      val write = Input(Bool())
      val addr = Input(UInt(10.W))
      val dataIn = Input(UInt(width.W))
      val dataOut = Output(UInt(width.W))
    })

    val mem = SyncReadMem(size, UInt(width.W))
    // Initialize memory
    if (memoryFile.trim().nonEmpty) {
      loadMemoryFromFileInline(mem, memoryFile)
    }
    io.dataOut := DontCare
    when(io.enable) {
      val rdwrPort = mem(io.addr)
      when(io.write) { rdwrPort := io.dataIn }
        .otherwise { io.dataOut := rdwrPort }
    }
  }

  "InitMemInline" should "be simulable" taggedAs (UnitTests) in {
    val resource = "examples_shell/simple.mem"

    val file = getClass.getClassLoader.getResource(resource).getFile()
    implicit val memoryInit = EnableMemInitVerilog

    simulate(
      new InitMemInline(file, 16, 32),
      firtoolOpts = Array("--disable-all-randomization")
    ) { mem =>
      mem.io.enable.poke(true)
      for (i <- 1 until 10) {
        mem.io.dataIn.poke(i)
        mem.io.addr.poke(i)
        mem.io.write.poke(false)
        mem.clock.step()
        // println(mem.io.dataOut.peek())
        mem.io.dataOut.expect(i)
      }
    }
  }
}
