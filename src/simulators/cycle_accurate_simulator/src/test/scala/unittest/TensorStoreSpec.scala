package unittest

import chisel3._
import org.scalatest.flatspec.AnyFlatSpec
import chisel3.simulator.scalatest.ChiselSim
import vta.core.TensorStore
import vta.DefaultPynqConfig
import vta.util.SimulationUtils.verilatorWithWaveDump

class TensorStoreSpec extends AnyFlatSpec with ChiselSim {
  it should "properly run" in {
    implicit val parameter = new DefaultPynqConfig
    implicit val veril = verilatorWithWaveDump
    simulate(new TensorStore("out")) { dut =>
      enableWaves()
      dut.io.start.poke(false)
      dut.io.baddr.poke("x1000".asUInt)
      dut.io.start.poke(true)
      dut.io.tensor.wr(0).valid.poke(true)
      for (i <- 0 until 2) {
        dut.io.tensor.wr(0).bits.idx.poke(i)
        dut.io.tensor.wr(0).bits.data.zipWithIndex.foreach { r =>
          r._1.zipWithIndex.foreach { c => c._1.poke(2) }
        }
        dut.clock.step()
      }

      dut.clock.step(10)
    }
  }
}
