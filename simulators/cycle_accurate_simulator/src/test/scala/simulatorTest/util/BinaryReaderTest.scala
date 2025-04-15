package simulatorTest.util

import org.scalatest.flatspec.AnyFlatSpec
import org.scalatest.matchers.should
import BinaryReader._

import scala.util.{Success, Failure}

class BinaryReaderTest extends AnyFlatSpec with should.Matchers {

  //FIXME organize the resource files
  "BinaryReader" should "print the decoded instructions in console" in {
    val result = computeAddressesTry("examples_compute/lenet5_layer1/instructions.bin", DataType.INSN, "00000000")
    printMapLE(result, DataType.INSN)
  }

  it should "print the INP data extracted from the binary file" in {
    printMapLELE("examples_compute/lenet5_layer1/input.bin")
  }

  it should "print the INP data encoded in a format computable by CHISEL" in {
    printMapLE(computeAddressesTry("examples_compute/lenet5_layer1/input.bin", DataType.INP, "00001000"), DataType.INP)
  }

  it should "decode correctly the first vector of INP (16 Bytes) in a binary file" in {
    val result =  computeAddressesTry("examples_compute/lenet5_layer1/input.bin", DataType.INP, "00000000")
    val hexa = Array("FD",
      "FE",
      "FC",
      "FF",
      "02",
      "FF",
      "01",
      "FF",
      "02",
      "FE",
      "00",
      "FC",
      "00",
      "FC",
      "FE",
      "FF")
    val inpFirstVector: Array[BigInt] = hexa.map { hex =>
      val decimal = java.lang.Integer.parseInt(hex, 16)
      if (decimal >= 128) BigInt(decimal - 256) else BigInt(decimal)
    }
    result match {
      case Success(data) =>
        Success(data(0) should equal (inpFirstVector))
      case Failure(exception) =>
        println(s"Error while computing addresses for INP : ${exception.getMessage}")
        Failure(exception)
    }
  }

  it should "decode correctly the first vector of WGT (256 Bytes) in a binary file" in {
    val result =  computeAddressesTry("examples_compute/lenet5_layer1/weight.bin", DataType.WGT, "00000000")
    val inputWGTHex = Array("00",
      "FE",
      "FF",
      "01",
      "01",
      "FD",
      "01",
      "00",
      "00",
      "FC",
      "FD",
      "02",
      "01",
      "02",
      "FD",
      "00",
      "FE",
      "FC",
      "FD",
      "FD",
      "FE",
      "FC",
      "01",
      "FC",
      "FD",
      "00",
      "00",
      "FF",
      "02",
      "FF",
      "FF",
      "02",
      "FC",
      "FE",
      "FE",
      "FF",
      "FE",
      "FC",
      "01",
      "FE",
      "02",
      "FD",
      "FE",
      "FD",
      "FD",
      "00",
      "FF",
      "01",
      "02",
      "02",
      "02",
      "01",
      "02",
      "FD",
      "00",
      "FF",
      "FE",
      "FC",
      "FD",
      "FF",
      "01",
      "FC",
      "FD",
      "02",
      "FF",
      "02",
      "02",
      "FF",
      "00",
      "FC",
      "FF",
      "FD",
      "FE",
      "FF",
      "FC",
      "01",
      "FE",
      "01",
      "FF",
      "FE",
      "FE",
      "01",
      "FC",
      "FF",
      "01",
      "FC",
      "FE",
      "FF",
      "FC",
      "FD",
      "FF",
      "00",
      "FD",
      "FF",
      "FF",
      "02",
      "00",
      "00",
      "00",
      "00",
      "00",
      "00",
      "00",
      "00",
      "00",
      "00",
      "00",
      "00",
      "00",
      "00",
      "00",
      "00",
      "00",
      "00",
      "00",
      "00",
      "00",
      "00",
      "00",
      "00",
      "00",
      "00",
      "00",
      "00",
      "00",
      "00",
      "00",
      "00",
      "00",
      "00",
      "00",
      "00",
      "00",
      "00",
      "00",
      "00",
      "00",
      "00",
      "00",
      "00",
      "00",
      "00",
      "00",
      "00",
      "00",
      "00",
      "00",
      "00",
      "00",
      "00",
      "00",
      "00",
      "00",
      "00",
      "00",
      "00",
      "00",
      "00",
      "00",
      "00",
      "00",
      "00",
      "00",
      "00",
      "00",
      "00",
      "00",
      "00",
      "00",
      "00",
      "00",
      "00",
      "00",
      "00",
      "00",
      "00",
      "00",
      "00",
      "00",
      "00",
      "00",
      "00",
      "00",
      "00",
      "00",
      "00",
      "00",
      "00",
      "00",
      "00",
      "00",
      "00",
      "00",
      "00",
      "00",
      "00",
      "00",
      "00",
      "00",
      "00",
      "00",
      "00",
      "00",
      "00",
      "00",
      "00",
      "00",
      "00",
      "00",
      "00",
      "00",
      "00",
      "00",
      "00",
      "00",
      "00",
      "00",
      "00",
      "00",
      "00",
      "00",
      "00",
      "00",
      "00",
      "00",
      "00",
      "00",
      "00",
      "00",
      "00",
      "00",
      "00",
      "00",
      "00",
      "00",
      "00",
      "00",
      "00",
      "00",
      "00",
      "00",
      "00",
      "00",
      "00",
      "00",
      "00",
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
    // String to decimal conversion for the first WGT block
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

  it should "decode correctly the first vector of EXPECT_OUT (16 Bytes) in a binary file" in {
    val result =  computeAddressesTry("examples_compute/16x16_relu/expected_out.bin", DataType.OUT, "00000000")
    result match {
      case Success(data) =>
        //val decimal = tableau.map(hex => Integer.parseInt(hex, 16))
        Success(data(0) should equal (Array(43,-5,25,10,35,25,5,64,43,-5,35,39,28,-2,1,34)))
      case Failure(exception) =>
        println(s"Error while computing addresses for EXPECT_OUT : ${exception.getMessage}")
        Failure(exception)
    }
  }

  it should "decode correctly the UOPs (4 Bytes each) in a binary file" in {
    val result =  computeAddressesTry("examples_compute/lenet5_layer1/uop.bin", DataType.UOP, "00000000")
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
    val result = computeAddressesTry("examples_compute/lenet5_layer1/instructions.bin", DataType.INSN, "00000000")
    result match {
      case Success(data) =>
        Success(data(0) should equal (Array(0, 0, 0, 1, 0, 1, 0, 1, 0, 0, 0, -48, 0, 0, 0, 0)))
      case Failure(exception) =>
        println(s"Error while computing addresses for instructions : ${exception.getMessage}")
        Failure(exception)
    }
  }

  it should "decode correctly the last instruction in a binary file" in {
    val result = computeAddressesTry("examples_compute/lenet5_layer1/instructions.bin", DataType.INSN, "00000000")
    result match {
      case Success(data) =>
        Success(data(data.size - 1) should equal (Array(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 3)))
      case Failure(exception) =>
        println(s"Error while computing addresses for instructions : ${exception.getMessage}")
        Failure(exception)
    }
  }

  it should "return the same value if an offset is or isn't used for the first vector of INP" in {
    val resultOffset = computeAddressesTry("examples_compute/lenet5_layer1/instructions.bin", DataType.INSN, "00001000")
    val resultWithoutOffset = computeAddressesTry("examples_compute/lenet5_layer1/instructions.bin", DataType.INSN, "00000000")
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
    val resultOffset = computeAddressesTry("examples_compute/lenet5_layer1/input.bin", DataType.INP, offset)
    val resultWithoutOffset = computeAddressesTry("examples_compute/lenet5_layer1/input.bin", DataType.INP, "00000000")
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
