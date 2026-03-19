package vta.util

import chisel3._
import chisel3.simulator.scalatest.ChiselSim
import org.scalatest.flatspec.AnyFlatSpec
import vta.DefaultPynqConfig
import vta.util.config._

class GenericSim[T <: Module, C <: Parameters](
    tag: String,
    dutFactory: (Parameters) => T,
    testerFactory: (T) => Unit
) extends AnyFlatSpec
    with ChiselSim {

  implicit val p: Parameters = new DefaultPynqConfig

  behavior of tag
  it should "not have expect violations" in {
    simulate(dutFactory(p))(testerFactory)
  }
}
