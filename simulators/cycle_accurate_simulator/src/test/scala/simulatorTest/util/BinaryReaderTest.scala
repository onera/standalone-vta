package simulatorTest.util

import org.scalatest.flatspec.AnyFlatSpec
import org.scalatest.matchers.should

import BinaryReader._

class BinaryReaderTest extends AnyFlatSpec with should.Matchers {

  //FIXME organize the resource files
  "BinaryReader" should "decode instruction from binary file" in {
    val result = computeAddresses("examples_compute/instructions_lenet5_layer1.bin")
    printMapLE(result)
    //result(0) should equal (Array(0, 0, 0, 1, 0, 1, 0, 1, 0, 0, 0, -48, 0, 0, 0, 0))
  }

  it should "blabla" in {

  }

}
