package utils

import chisel3._
import vta.util.config._
import chiseltest._
import chiseltest.iotesters._
import org.scalatest.flatspec.AnyFlatSpec
import vta.DefaultPynqConfig

import org.scalatest.Tag
object UnitTests extends Tag("UnitTests")
object LongTests extends Tag("LongTests")

class GenericSim[T <: Module, P <: PeekPokeTester[T], C <: Parameters](tag : String, dutFactory : (Parameters) => T,
                                                                       testerFactory : (T) => P, isLongTest : Boolean = false)
  extends AnyFlatSpec with ChiselScalatestTester {

  implicit val p: Parameters = new DefaultPynqConfig
  val defaultOpts = Seq(TreadleBackendAnnotation)

  behavior of tag
  if (isLongTest) {
    it should "not have expect violations" taggedAs(LongTests) in {
      test(dutFactory(p)).withAnnotations(defaultOpts).runPeekPoke(testerFactory)
    }
  } else {
    it should "not have expect violations" taggedAs(UnitTests) in {
      test(dutFactory(p)).withAnnotations(defaultOpts).runPeekPoke(testerFactory)
    }
  }
}
