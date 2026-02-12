package vta.shell

import org.scalatest.flatspec.AnyFlatSpec
import chisel3.simulator.scalatest.ChiselSim
import org.scalatest.matchers.should.Matchers
import com.fasterxml.jackson.databind.json.JsonMapper
import com.fasterxml.jackson.module.scala.DefaultScalaModule
import scala.io.Source
import com.fasterxml.jackson.databind.ObjectMapper

class DramInitTests extends AnyFlatSpec with ChiselSim with Matchers {

  "Json DRAM" should "be parsable" in {
    val bufferedSource =
      Source.fromURL(
        getClass.getClassLoader().getResource("examples_core/dram_state.json")
      )
    val mapper = new ObjectMapper()
    mapper.registerModule(DefaultScalaModule)
    val archState =
      mapper.readValue(bufferedSource.reader(), classOf[Map[String, Object]])
    bufferedSource.close
    println(archState)
    val memoryInit = archState.head._2
    memoryInit

  }
}
