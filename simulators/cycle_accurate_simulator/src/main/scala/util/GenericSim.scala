package util

import chisel3._
import chiseltest._
import chiseltest.iotesters._
import org.scalatest.flatspec.AnyFlatSpec
import vta.DefaultPynqConfig
import vta.util.config._

//abstract class GenericSim[T <: Module, P <: PeekPokeTester[T], C <: Parameters] extends AnyFlatSpec with ChiselScalatestTester {
//  implicit val p: Parameters = new DefaultPynqConfig
//  val defaultOpts = Seq(TreadleBackendAnnotation)
//}
//
//class GenericMain[T <: Module, P <: PeekPokeTester[T], C <: Parameters](tag : String, dutFactory : (Parameters) => T,
//                                                                       testerFactory : (T) => P)
//  extends GenericSim[T, P, C] {
//
//  behavior of tag
//  it should "not have expect violations" in {
//    test(dutFactory(p)).withAnnotations(defaultOpts).runPeekPoke(testerFactory)
//  }
//}

class GenericSim[T <: Module, P <: PeekPokeTester[T], C <: Parameters](tag : String, dutFactory : (Parameters) => T,
                                                                       testerFactory : (T) => P, isLongTest : Boolean = false)
  extends AnyFlatSpec with ChiselScalatestTester {

  implicit val p: Parameters = new DefaultPynqConfig
  val defaultOpts = Seq(TreadleBackendAnnotation)

  behavior of tag
  it should "not have expect violations" in {
    test(dutFactory(p)).withAnnotations(defaultOpts).runPeekPoke(testerFactory)
  }
}
