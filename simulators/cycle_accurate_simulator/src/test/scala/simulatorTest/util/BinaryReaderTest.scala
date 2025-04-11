package simulatorTest.util

import org.scalatest.flatspec.AnyFlatSpec
import org.scalatest.matchers.should

import BinaryReader._

class BinaryReaderTest extends AnyFlatSpec with should.Matchers {

  //FIXME organize the resource files
  "BinaryReader" should "print the decoded instructions in console" in {
    val result = computeAddresses("examples_compute/instructions_lenet5_layer1.bin", DataType.INSN, "00000000")
    printMapLE(result, DataType.INSN)
  }

  it should "print the INP data extracted from the binary file" in {
    printMapLELE("examples_compute/input_lenet5_layer1.bin")
  }

  it should "print the INP data encoded in a format computable by CHISEL" in {
    printMapLE(computeAddresses("examples_compute/input_lenet5_layer1.bin", DataType.INP, "00000000"), DataType.INP)
  }

  it should "decode correctly the first vector of INP (16 Bytes) in a binary file" in {
    val result =  computeAddresses("examples_compute/input_lenet5_layer1.bin", DataType.INP, "00000000")
    result(0) should equal (Array(2, -1, -4, 1, 2, 1, 1, 1, -4, -1, 1, 2, -3, -4, 1, 1))
  }

  it should "decode correctly the first vector of WGT (256 Bytes) in a binary file" in {
    val result =  computeAddresses("examples_compute/weight_lenet5_layer1.bin", DataType.WGT, "00000000")
    val inputWGTHex = Array(
      "01", "02", "FF", "FE", "FC", "01", "01", "01", "FE", "00", "FE", "FE", "FC", "01", "00",
      "00", "FC", "01", "FE", "02", "FC", "02", "FC", "FE", "00", "FD", "00", "FE", "FF", "FF",
      "02", "FC", "FE", "FC", "FD", "FE", "02", "FE", "01", "00", "01", "FE", "FD", "01", "FC",
      "FD", "00", "FF", "FE", "FE", "00", "02", "FE", "FD", "FF", "00", "FD", "FF", "00", "FF",
      "00", "01", "FD", "FC", "01", "01", "01", "FE", "FE", "FE", "00", "FF", "FE", "FD", "02",
      "FC",
      "02",
      "FF",
      "FD",
      "FE",
      "FD",
      "FE",
      "FE",
      "01",
      "FD",
      "FD",
      "FD",
      "00",
      "00",
      "00",
      "FD",
      "01",
      "01",
      "FD",
      "02",
      "FC",
      "00",
      "00",
      "00",
      "00",
      "00",
      "00",
      "00",
      "00",
      "00",
      "00",
      "00",
      "00",
      "00",
      "00",
      "00",
      "00",
      "00",
      "00",
      "00",
      "00",
      "00",
      "00",
      "00",
      "00",
      "00",
      "00",
      "00",
      "00",
      "00",
      "00",
      "00",
      "00",
      "00",
      "00",
      "00",
      "00",
      "00",
      "00",
      "00",
      "00",
      "00",
      "00",
      "00",
      "00",
      "00",
      "00",
      "00",
      "00",
      "00",
      "00",
      "00",
      "00",
      "00",
      "00",
      "00",
      "00",
      "00",
      "00",
      "00",
      "00",
      "00",
      "00",
      "00",
      "00",
      "00",
      "00",
      "00",
      "00",
      "00",
      "00",
      "00",
      "00",
      "00",
      "00",
      "00",
      "00",
      "00",
      "00",
      "00",
      "00",
      "00",
      "00",
      "00",
      "00",
      "00",
      "00",
      "00",
      "00",
      "00",
      "00",
      "00",
      "00",
      "00",
      "00",
      "00",
      "00",
      "00",
      "00",
      "00",
      "00",
      "00",
      "00",
      "00",
      "00",
      "00",
      "00",
      "00",
      "00",
      "00",
      "00",
      "00",
      "00",
      "00",
      "00",
      "00",
      "00",
      "00",
      "00",
      "00",
      "00",
      "00",
      "00",
      "00",
      "00",
      "00",
      "00",
      "00",
      "00",
      "00",
      "00",
      "00",
      "00",
      "00",
      "00",
      "00",
      "00",
      "00",
      "00",
      "00",
      "00",
      "00",
      "00",
      "00",
      "00",
      "00",
      "00",
      "00",
      "00",
      "00",
      "00",
      "00",
      "00",
      "00",
      "00",
      "00",
      "00",
      "00",
      "00",
      "00",
      "00")
    val wgtFirstBlock: Array[BigInt] = inputWGTHex.map { hex =>
      val decimal = java.lang.Integer.parseInt(hex, 16)
      if (decimal >= 128) BigInt(decimal - 256) else BigInt(decimal)
    }
    result(0) should equal (wgtFirstBlock)
  }

  it should "decode correctly the first instruction (16 Bytes) in a binary file" in {
    val result = computeAddresses("examples_compute/instructions_lenet5_layer1.bin", DataType.INSN, "00000000")
    result(0) should equal (Array(0, 0, 0, 1, 0, 1, 0, 1, 0, 0, 0, -48, 0, 0, 0, 0))
  }

  it should "decode correctly the last instruction in a binary file" in {
    val result = computeAddresses("examples_compute/instructions_lenet5_layer1.bin", DataType.INSN, "00000000")
    result(result.size - 1) should equal (Array(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 3))
  }

  it should "return an error if the file formatting is wrong" in {
    val result = computeAddresses("examples_compute/compute_smm.json", DataType.INSN, "00000000")

  }
}
