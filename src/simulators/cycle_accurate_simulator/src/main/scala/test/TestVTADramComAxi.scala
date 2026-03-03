package vta.test

import chisel3._
import vta.util.MemoryConfig
import vta.util.config.Parameters
import vta.interface.axi.AXILiteClient
import vta.shell.VTAShell
import vta.shell.ShellKey
import chisel3.util.experimental.BoringUtils
import chisel3.simulator.ChiselSim
import vta.util.SimulationUtils.EnableMemInitVerilog
import vta.DefaultPynqConfig
import chisel3.simulator.stimulus.RunUntilFinished
import vta.util.SimulationUtils
import chisel3.testing.HasTestingDirectory
import java.nio.file.Path
import java.nio.file.Paths
import chisel3.simulator.HasSimulator

class VTAShellTestFull(
    content: Seq[MemoryConfig]
)(implicit
    param: Parameters
) extends Module {
  val io = IO(new Bundle {
    val host = new AXILiteClient(param(ShellKey).hostParams)
  })
  val vta = Module(new VTAShell(true))

  val dramMock = Module(
    new MultiMemAxiClient(content)(param(ShellKey).memParams)
  )
  val finish = dontTouch(
    WireInit(BoringUtils.tapAndRead(vta.vcr.io.vcr.finish))
  )
  when(finish) {
    stop()
  }
  vta.io.host <> io.host
  vta.io.mem <> dramMock.io
}

trait VTAShellTest extends ChiselSim with AxiFullSimUtils with AxiLiteSimUtils {

  def runVtaTestWithInitializedMem(
      content: Seq[MemoryConfig],
      timeout: Int = 100,
      waves: Boolean = false
  )(implicit testingDirectory: HasTestingDirectory, simulator: HasSimulator) = {
    implicit val parameters: Parameters = new DefaultPynqConfig

    implicit val enableMemoryInit = EnableMemInitVerilog
    simulate(
      new VTAShellTestFull(content),
      firtoolOpts = Array("--disable-all-randomization")
    ) { vta =>
      implicit val clock = vta.clock
      implicit val axiLiteClient = vta.io.host
      vta.io.host.b.ready.poke(true.B)

      if (waves) {
        enableWaves()
      }

      writeInstructionBaseAddress(
        content.find(_.name.matches("INSN")).get.baseAddress
      )
      writeUopBaseAddress(0)
      writeInputBaseAddress(0)
      writeWeightBaseAddress(0)
      writeAccBaseAddress(0)
      writeOutBaseAddress(0)
      // Configure instruction size

      writeInstructionCount(
        content.find(_.name.matches("INSN")).get.initialSize
      )

      // launch the processing of VTA
      launchVTA()

      // step clock until the computation is over
      clock.step(timeout)
      RunUntilFinished(timeout)
    }
  }
}
