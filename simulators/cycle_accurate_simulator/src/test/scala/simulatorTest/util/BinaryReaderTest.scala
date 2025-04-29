package simulatorTest.util

import org.scalatest.flatspec.AnyFlatSpec
import org.scalatest.matchers.should
import BinaryReader._

import java.math.BigInteger
import scala.util.{Failure, Success}

class BinaryReaderTest extends AnyFlatSpec with should.Matchers {

  "BinaryReader" should "decode correctly the first vector of INP (16 Bytes) in a binary file" in {
    val result = computeAddresses("examples_compute/16x16/input.bin", DataType.INP, "00000000", isDRAM = false)
    val hexa = Array("FF",
      "FF",
      "00",
      "FD",
      "FD",
      "01",
      "02",
      "01",
      "00",
      "FD",
      "00",
      "00",
      "01",
      "FD",
      "00",
      "01")
    val inpFirstVector: Array[BigInt] = hexa.map { hex =>
      val decimal = java.lang.Integer.parseInt(hex, 16)
      if (decimal >= 128) BigInt(decimal - 256) else BigInt(decimal)
    }
    result match {
      case Success(data) =>
        data(0) should equal(inpFirstVector)
      case Failure(exception) =>
        fail(s"Error while computing addresses for INP : ${exception.getMessage}")
    }
  }

  it should "decode correctly the first vector of WGT (256 Bytes) in a binary file" in {
    val result = computeAddresses("examples_compute/16x16/weight.bin", DataType.WGT, "00000000", isDRAM = false)
    val inputWGTHex = Array("FD",
      "FD",
      "FC",
      "FE",
      "FF",
      "FC",
      "FE",
      "01",
      "00",
      "00",
      "FD",
      "FE",
      "02",
      "FC",
      "FD",
      "FE",
      "FC",
      "01",
      "FD",
      "FF",
      "FF",
      "FC",
      "00",
      "00",
      "FE",
      "02",
      "FD",
      "FC",
      "FF",
      "00",
      "01",
      "FE",
      "FC",
      "02",
      "01",
      "FE",
      "FF",
      "FE",
      "FD",
      "00",
      "01",
      "FE",
      "FF",
      "FF",
      "FF",
      "FE",
      "00",
      "00",
      "02",
      "FE",
      "00",
      "00",
      "01",
      "FD",
      "FF",
      "FD",
      "FF",
      "FD",
      "01",
      "00",
      "FF",
      "FE",
      "FF",
      "FD",
      "02",
      "FC",
      "FC",
      "FC",
      "FE",
      "FE",
      "02",
      "FD",
      "FD",
      "00",
      "FE",
      "01",
      "00",
      "FF",
      "FC",
      "FE",
      "01",
      "FF",
      "FC",
      "01",
      "00",
      "FE",
      "FC",
      "FC",
      "FC",
      "FC",
      "00",
      "FD",
      "FC",
      "00",
      "FF",
      "FE",
      "02",
      "FC",
      "FC",
      "FF",
      "FD",
      "FF",
      "01",
      "00",
      "02",
      "FD",
      "FE",
      "FE",
      "FC",
      "02",
      "FD",
      "00",
      "FD",
      "01",
      "FD",
      "FD",
      "FD",
      "FF",
      "00",
      "FD",
      "FC",
      "01",
      "FF",
      "01",
      "FD",
      "FE",
      "02",
      "FF",
      "FE",
      "FC",
      "FC",
      "FC",
      "FE",
      "02",
      "00",
      "02",
      "FF",
      "FD",
      "02",
      "FF",
      "00",
      "FE",
      "FC",
      "FD",
      "02",
      "01",
      "FE",
      "FF",
      "00",
      "00",
      "FF",
      "00",
      "FE",
      "FC",
      "FF",
      "01",
      "01",
      "00",
      "FD",
      "FC",
      "FD",
      "FD",
      "01",
      "FC",
      "FC",
      "FD",
      "01",
      "FE",
      "FE",
      "FD",
      "00",
      "01",
      "FF",
      "FD",
      "FD",
      "01",
      "FF",
      "FD",
      "FC",
      "FE",
      "02",
      "FE",
      "01",
      "FC",
      "FC",
      "FE",
      "FD",
      "FD",
      "00",
      "FC",
      "FE",
      "FC",
      "FF",
      "02",
      "01",
      "FF",
      "FD",
      "01",
      "01",
      "FC",
      "00",
      "00",
      "FC",
      "FE",
      "FD",
      "01",
      "01",
      "FE",
      "00",
      "FF",
      "FE",
      "FD",
      "FE",
      "00",
      "FC",
      "FF",
      "02",
      "FF",
      "FE",
      "FF",
      "FD",
      "02",
      "02",
      "FD",
      "01",
      "00",
      "02",
      "FD",
      "02",
      "01",
      "02",
      "FE",
      "FC",
      "FC",
      "00",
      "FD",
      "01",
      "FC",
      "FE",
      "FF",
      "FF",
      "00",
      "FD",
      "02",
      "FF",
      "FD",
      "02",
      "01",
      "FF",
      "01",
      "FE",
      "FC",
      "FE",
      "00",
      "02",
      "02")
    // String to decimal conversion for the first WGT block
    val wgtFirstBlock: Array[BigInt] = inputWGTHex.map { hex =>
      val decimal = java.lang.Integer.parseInt(hex, 16)
      if (decimal >= 128) BigInt(decimal - 256) else BigInt(decimal)
    }
    result match {
      case Success(data) =>
        data(0) should equal(wgtFirstBlock)
      case Failure(exception) =>
        fail(s"Error while computing addresses for WGT : ${exception.getMessage}")
    }
  }

  it should "decode correctly the first vector of EXPECT_OUT (16 Bytes) in a binary file" in {
    val result = computeAddresses("examples_compute/16x16/expected_out.bin", DataType.OUT, "00000000", isDRAM = false)
    val hexa = Array("14",
      "FC",
      "0E",
      "00",
      "14",
      "F5",
      "0E",
      "0F",
      "28",
      "07",
      "2D",
      "0E",
      "02",
      "FE",
      "1D",
      "FD")
    val outFirstVector: Array[BigInt] = hexa.map { hex =>
      val decimal = java.lang.Integer.parseInt(hex, 16)
      if (decimal >= 128) BigInt(decimal - 256) else BigInt(decimal)
    }
    result match {
      case Success(data) =>
        data(0) should equal(outFirstVector)
      case Failure(exception) =>
        fail(s"Error while computing addresses for EXPECT_OUT : ${exception.getMessage}")
    }
  }

  it should "decode correctly the first vector of ACC (64 Bytes) in a binary file" in {
    val result = computeAddresses("examples_compute/lenet5_layer1/accumulator.bin", DataType.ACC, "00000000", isDRAM = true)
    val hexa = Array("00000000",
      "00000000",
      "00000000",
      "00000000",
      "00000000",
      "00000000",
      "00000000",
      "00000000",
      "00000000",
      "00000000",
      "00000000",
      "00000000",
      "00000000",
      "00000000",
      "00000000",
      "00000000")
    val expectedOut = hexa.map { hex =>
      val decimal = java.lang.Integer.parseInt(hex, 16)
      if (decimal >= 128) BigInt(decimal - 256) else BigInt(decimal)
    }
    result match {
      case Success(data) =>
        data(0) should equal(expectedOut)
      case Failure(exception) =>
        fail(s"Error while computing addresses for ACC : ${exception.getMessage}")
    }
  }

  it should "decode correctly the UOPs (4 Bytes each) in a binary file" in {
    val result = computeAddresses("examples_compute/lenet5_layer1/uop.bin", DataType.UOP, "00000000", isDRAM = true)
    result match {
      case Success(data) =>
        data(0) should equal(Array(0, 0, 0))
        data(4) should equal(Array(0, 0, 0))
        data(8) should equal(Array(2, 32, 0))
        data(12) should equal(Array(0, 0, 0))
      case Failure(exception) =>
        fail(s"Error while computing addresses for UOPs : ${exception.getMessage}")

    }
  }

  it should "decode correctly the first instruction (16 Bytes) in a binary file" in {
    val result = computeAddresses("examples_compute/lenet5_layer1/instructions.bin", DataType.INSN, "00000000", isDRAM = false)

    val I0 = BigInt(
      Array(
        ("00000001", 96),
        ("00010001", 64),
        ("000000D0", 32),
        ("00000000", 0)
      ).map { case (hex, shift) =>
        new BigInteger(hex, 16).shiftLeft(shift)
      }.reduce(_ add _))

    result match {
      case Success(data) =>
        data(0) should equal(Array(I0))
      case Failure(exception) =>
        fail(s"Error while computing addresses for instructions : ${exception.getMessage}")
    }
  }

  it should "decode correctly the last instruction in a binary file" in {
    val result = computeAddresses("examples_compute/lenet5_layer1/instructions.bin", DataType.INSN, "00000000", isDRAM = false)
    val I_last = BigInt(
      Array(
        ("00000000", 96),
        ("00000000", 64),
        ("00000000", 32),
        ("00000003", 0)
      ).map { case (hex, shift) =>
        new BigInteger(hex, 16).shiftLeft(shift)
      }.reduce(_ add _))

    result match {
      case Success(data) =>
        data(data.size - 1) should equal(Array(I_last))
      case Failure(exception) =>
        fail(s"Error while computing addresses for instructions : ${exception.getMessage}")
    }
  }

  it should "decode correctly the first vector of ACC" in {
    val result = computeAddresses("examples_compute/16x16_relu/accumulator.bin", DataType.ACC, "00000000", isDRAM = true)
    result match {
      case Success(data) =>
        data(0) should equal(Array(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0))
      case Failure(exception) =>
        fail(s"Error while computing addresses for instructions : ${exception.getMessage}")
    }
  }

  it should "print the decoded data" in {
    val result = computeAddresses("examples_compute/average_pooling/uop.bin", DataType.UOP, "00004000", isDRAM = true)
    result match {
      case Success(data) =>
        printMap(data, DataType.UOP)
      case Failure(exception) =>
        fail(s"Error while computing addresses for UOPs : ${exception.getMessage}")
    }
  }

  it should "return the same value if an offset is or isn't used for the first vector of INP" in {
    val resultOffset = computeAddresses("examples_compute/lenet5_layer1/instructions.bin", DataType.INSN, "00001000", isDRAM = false)
    val resultWithoutOffset = computeAddresses("examples_compute/lenet5_layer1/instructions.bin", DataType.INSN, "00000000", isDRAM = false)

    resultOffset match {
      case Success(dataOffset) =>
        for {
          withoutOffset <- resultWithoutOffset
        } {
          val idx = java.lang.Integer.parseInt("00001000", 16)
          dataOffset(idx) should equal(withoutOffset(0))
        }
      case Failure(exception) =>
        fail(s"Error while computing addresses for INP with an offset : ${exception.getMessage}")
    }
  }

  it should "return the same value if an offset is or isn't used for the second vector of INP" in {
    val offset = "00001000"
    val resultOffset = computeAddresses("examples_compute/lenet5_layer1/input.bin", DataType.INP, offset, isDRAM = false)
    val resultWithoutOffset = computeAddresses("examples_compute/lenet5_layer1/input.bin", DataType.INP, "00000000", isDRAM = false)
    resultOffset match {
      case Success(dataOffset) =>
        resultWithoutOffset match {
          case Success(dataWithoutOffset) =>
            val idx = java.lang.Integer.parseInt(offset, 16)
            dataOffset(idx + 1) should equal(dataWithoutOffset(1))
          case Failure(exception) =>
            fail(s"Error while computing addresses for INP without an offset : ${exception.getMessage}")
        }
      case Failure(exception) =>
        fail(s"Error while computing addresses for INP with an offset : ${exception.getMessage}")
    }
  }
}