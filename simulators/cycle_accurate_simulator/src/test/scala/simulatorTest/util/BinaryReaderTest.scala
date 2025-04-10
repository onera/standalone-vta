package simulatorTest.util

import org.scalatest.flatspec.AnyFlatSpec
import org.scalatest.matchers.should

import BinaryReader._

class BinaryReaderTest extends AnyFlatSpec with should.Matchers {

  //FIXME organize the resource files
  "BinaryReader" should "print the decoded instructions in console" in {
    val result = computeAddresses("examples_compute/instructions_lenet5_layer1.bin")
    printMapLE(result)
  }

  it should "decode correctly the first instruction in a binary file" in {
    val result = computeAddresses("examples_compute/instructions_lenet5_layer1.bin")
    result(0) should equal (Array(0, 0, 0, 1, 0, 1, 0, 1, 0, 0, 0, -48, 0, 0, 0, 0))
  }

  it should "decode correctly the last instruction in a binary file" in {
    val result = computeAddresses("examples_compute/instructions_lenet5_layer1.bin")
    result(result.size - 1) should equal (Array(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 3))
  }

  it should "return an error if the file formatting is wrong" in {
    val result = computeAddresses("examples_compute/compute_smm.json")

  }
}
