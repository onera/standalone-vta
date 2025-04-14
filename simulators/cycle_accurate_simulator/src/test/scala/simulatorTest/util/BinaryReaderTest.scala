package simulatorTest.util

import org.scalatest.flatspec.AnyFlatSpec
import org.scalatest.matchers.should
import BinaryReader._

import scala.util.{Success, Failure}

class BinaryReaderTest extends AnyFlatSpec with should.Matchers {

  //FIXME organize the resource files
  "BinaryReader" should "print the decoded instructions in console" in {
    val result = computeAddressesTry("examples_compute/instructions_lenet5_layer1.bin", DataType.INSN, "00000000")
    printMapLE(result, DataType.INSN)
  }

  it should "print the INP data extracted from the binary file" in {
    printMapLELE("examples_compute/input_lenet5_layer1.bin")
  }

  it should "print the INP data encoded in a format computable by CHISEL" in {
    printMapLE(computeAddressesTry("examples_compute/input_lenet5_layer1.bin", DataType.INP, "00001000"), DataType.INP)
  }

  it should "decode correctly the first vector of INP (16 Bytes) in a binary file" in {
    val result =  computeAddressesTry("examples_compute/input_lenet5_layer1.bin", DataType.INP, "00000000")
    result match {
      case Success(data) =>
        Success(data(0) should equal (Array(2, -1, -4, 1, 2, 1, 1, 1, -4, -1, 1, 2, -3, -4, 1, 1)))
      case Failure(exception) =>
        println(s"Error while computing addresses for INP : ${exception.getMessage}")
        Failure(exception)
    }
  }

  it should "decode correctly the first vector of WGT (256 Bytes) in a binary file" in {
    val result =  computeAddressesTry("examples_compute/weight_lenet5_layer1.bin", DataType.WGT, "00000000")
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
    result match {
      case Success(data) =>
        Success(data(0) should equal (wgtFirstBlock))
      case Failure(exception) =>
        println(s"Error while computing addresses for WGT : ${exception.getMessage}")
        Failure(exception)
    }
  }

  it should "decode correctly the UOPs (4 Bytes each) in a binary file" in {
    val result =  computeAddressesTry("examples_compute/uop_lenet5_layer1.bin", DataType.UOP, "00000000")
    result match {
      case Success(data) =>
        Success(data(0) should equal (Array(0, 0, 0, 0)),
          data(1) should equal (Array(0, 0, 0, 0)),
          data(2) should equal (Array(0, 64, -128, 0)),
          data(3) should equal (Array(0, 0, 0, 0)))
      case Failure(exception) =>
        println(s"Error while computing addresses for UOPs : ${exception.getMessage}")
        Failure(exception)
    }
  }

  it should "decode correctly the first instruction (16 Bytes) in a binary file" in {
    val result = computeAddressesTry("examples_compute/instructions_lenet5_layer1.bin", DataType.INSN, "00000000")
    result match {
      case Success(data) =>
        Success(data(0) should equal (Array(0, 0, 0, 1, 0, 1, 0, 1, 0, 0, 0, -48, 0, 0, 0, 0)))
      case Failure(exception) =>
        println(s"Error while computing addresses for instructions : ${exception.getMessage}")
        Failure(exception)
    }
  }

  it should "decode correctly the last instruction in a binary file" in {
    val result = computeAddressesTry("examples_compute/instructions_lenet5_layer1.bin", DataType.INSN, "00000000")
    result match {
      case Success(data) =>
        Success(data(data.size - 1) should equal (Array(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 3)))
      case Failure(exception) =>
        println(s"Error while computing addresses for instructions : ${exception.getMessage}")
        Failure(exception)
    }
  }

  it should "return the same value if an offset is or isn't used for the first vector of INP" in {
    val resultOffset = computeAddressesTry("examples_compute/instructions_lenet5_layer1.bin", DataType.INSN, "00001000")
    val resultWithoutOffset = computeAddressesTry("examples_compute/instructions_lenet5_layer1.bin", DataType.INSN, "00000000")
    resultOffset match {
      case Success(dataOffset) =>
        resultWithoutOffset match {
          case Success(dataWithoutOffset) =>
            val idx = java.lang.Integer.parseInt("00001000", 16)
            Success(dataOffset(idx) should equal (dataWithoutOffset(0)))
          case Failure(exception) =>
            println(s"Error while computing addresses for INP without an offset : ${exception.getMessage}")
            Failure(exception)
        }
      case Failure(exception) =>
        println(s"Error while computing addresses for INP with an offset : ${exception.getMessage}")
        Failure(exception)
    }
  }

  it should "return the same value if an offset is or isn't used for the second vector of INP" in {
    val offset = "00001000"
    val resultOffset = computeAddressesTry("examples_compute/instructions_lenet5_layer1.bin", DataType.INSN, offset)
    val resultWithoutOffset = computeAddressesTry("examples_compute/instructions_lenet5_layer1.bin", DataType.INSN, "00000000")
    resultOffset match {
      case Success(dataOffset) =>
        resultWithoutOffset match {
          case Success(dataWithoutOffset) =>
            val idx = java.lang.Integer.parseInt(offset, 16)
            Success(dataOffset(idx + 1) should equal (dataWithoutOffset(1)))
          case Failure(exception) =>
            println(s"Error while computing addresses for INP without an offset : ${exception.getMessage}")
            Failure(exception)
        }
      case Failure(exception) =>
        println(s"Error while computing addresses for INP with an offset : ${exception.getMessage}")
        Failure(exception)
    }
  }



  it should "return an error if the file formatting is wrong" in {
    val result = computeAddressesTry("examples_compute/compute_smm.json", DataType.INSN, "00000000")


  }
}
