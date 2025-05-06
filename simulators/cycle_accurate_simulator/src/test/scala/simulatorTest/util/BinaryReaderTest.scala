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

  it should "decode correctly all the UOPs of a binary file" in {
    val result = computeAddresses("examples_compute/32x32_relu/uop.bin", DataType.UOP, "00000000", isDRAM = true)
    result match {
      case Success(data) =>
        println(data.size)
        printMap(data, DataType.UOP)
        data(0) should equal(Array(0, 0, 0))
        data(4) should equal(Array(0, 0, 0))
        data(8) should equal(Array(16, 0, 1))
        data(12) should equal(Array(32, 32, 0))
        data(16) should equal(Array(48, 32, 1))
        data(20) should equal(Array(0, 0, 0))
      case Failure(exception) =>
        fail(s"Error while computing addresses for UOPs : ${exception.getMessage}")

    }
  }

  it should "decode correctly the first 3 vectors of WGT (256 Bytes each) in a binary file" in {
    val result = computeAddresses("examples_compute/32x32_relu/weight.bin", DataType.WGT, "00000000", isDRAM = false)
    val vecWGT_0 = Array("FE",
      "02",
      "01",
      "00",
      "00",
      "FD",
      "01",
      "FD",
      "FF",
      "FC",
      "FD",
      "FE",
      "FE",
      "FF",
      "FF",
      "FD",
      "FF",
      "FF",
      "01",
      "FE",
      "FF",
      "FC",
      "FF",
      "00",
      "01",
      "01",
      "FF",
      "FF",
      "FD",
      "00",
      "01",
      "00",
      "01",
      "FD",
      "FD",
      "02",
      "FF",
      "FD",
      "FC",
      "00",
      "FC",
      "00",
      "FE",
      "FD",
      "00",
      "FC",
      "00",
      "00",
      "01",
      "FC",
      "00",
      "FF",
      "00",
      "01",
      "00",
      "02",
      "01",
      "FE",
      "FE",
      "02",
      "FF",
      "FC",
      "FD",
      "FE",
      "01",
      "01",
      "FE",
      "02",
      "00",
      "00",
      "FD",
      "00",
      "FF",
      "00",
      "FE",
      "00",
      "FD",
      "FF",
      "FE",
      "00",
      "00",
      "FC",
      "00",
      "FD",
      "02",
      "FF",
      "01",
      "02",
      "00",
      "FD",
      "FC",
      "FE",
      "01",
      "FE",
      "FE",
      "FE",
      "01",
      "FC",
      "FD",
      "00",
      "00",
      "FE",
      "FC",
      "FF",
      "02",
      "00",
      "01",
      "FD",
      "FD",
      "FE",
      "00",
      "FE",
      "FE",
      "FE",
      "02",
      "FD",
      "FD",
      "00",
      "01",
      "FE",
      "FD",
      "02",
      "01",
      "00",
      "FE",
      "FC",
      "FD",
      "FE",
      "02",
      "FE",
      "00",
      "01",
      "FC",
      "FF",
      "FF",
      "FF",
      "00",
      "FE",
      "FD",
      "00",
      "01",
      "01",
      "00",
      "FF",
      "FF",
      "FF",
      "FE",
      "FF",
      "00",
      "02",
      "00",
      "FD",
      "FE",
      "FF",
      "FC",
      "01",
      "FC",
      "FC",
      "02",
      "00",
      "00",
      "FD",
      "FF",
      "FF",
      "FE",
      "FE",
      "FC",
      "01",
      "00",
      "00",
      "02",
      "01",
      "02",
      "FF",
      "02",
      "02",
      "FD",
      "01",
      "01",
      "FF",
      "02",
      "FD",
      "FD",
      "02",
      "FD",
      "00",
      "01",
      "FF",
      "FE",
      "02",
      "01",
      "FD",
      "FF",
      "FE",
      "02",
      "FF",
      "FC",
      "02",
      "FE",
      "FF",
      "FE",
      "FC",
      "FE",
      "FC",
      "FF",
      "02",
      "FF",
      "02",
      "FC",
      "FE",
      "FC",
      "FD",
      "00",
      "FE",
      "FF",
      "FD",
      "FE",
      "00",
      "02",
      "FD",
      "02",
      "FF",
      "00",
      "FE",
      "00",
      "02",
      "FC",
      "FF",
      "00",
      "FD",
      "01",
      "FD",
      "FF",
      "FC",
      "FD",
      "FE",
      "00",
      "FF",
      "01",
      "FE",
      "02",
      "FE",
      "FF",
      "02",
      "FF",
      "01",
      "FC",
      "01",
      "02",
      "02",
      "00",
      "00",
      "FF",
      "FC",
      "FD",
      "FE")
    val vecWGT_1 = Array("FD",
      "01",
      "01",
      "FC",
      "FC",
      "FF",
      "FE",
      "00",
      "FF",
      "FF",
      "01",
      "01",
      "FE",
      "01",
      "FF",
      "FD",
      "02",
      "FE",
      "FF",
      "00",
      "02",
      "FF",
      "02",
      "00",
      "02",
      "FF",
      "00",
      "FE",
      "FF",
      "02",
      "FF",
      "02",
      "00",
      "FE",
      "02",
      "FC",
      "FF",
      "FC",
      "FE",
      "FF",
      "FF",
      "FF",
      "FC",
      "FE",
      "02",
      "02",
      "FD",
      "01",
      "FD",
      "FE",
      "FF",
      "FE",
      "01",
      "FF",
      "01",
      "02",
      "01",
      "FD",
      "02",
      "00",
      "FF",
      "02",
      "01",
      "FE",
      "01",
      "02",
      "01",
      "FD",
      "00",
      "00",
      "00",
      "02",
      "FC",
      "02",
      "FC",
      "FE",
      "FE",
      "02",
      "01",
      "00",
      "FC",
      "02",
      "00",
      "01",
      "FE",
      "02",
      "FE",
      "02",
      "FC",
      "00",
      "FC",
      "FC",
      "01",
      "FF",
      "FD",
      "FE",
      "00",
      "FD",
      "FD",
      "00",
      "FD",
      "FC",
      "FC",
      "FD",
      "00",
      "FF",
      "02",
      "02",
      "FD",
      "00",
      "01",
      "FD",
      "00",
      "02",
      "FD",
      "FD",
      "FF",
      "FF",
      "FC",
      "FC",
      "00",
      "FE",
      "FE",
      "FC",
      "02",
      "FF",
      "FE",
      "02",
      "FE",
      "FE",
      "01",
      "FE",
      "FC",
      "02",
      "FC",
      "01",
      "FF",
      "02",
      "FC",
      "FC",
      "FC",
      "FD",
      "FF",
      "FD",
      "FF",
      "00",
      "00",
      "02",
      "01",
      "FF",
      "FD",
      "00",
      "FE",
      "FF",
      "FC",
      "FC",
      "02",
      "02",
      "FD",
      "FC",
      "01",
      "FC",
      "FE",
      "FD",
      "01",
      "FE",
      "01",
      "01",
      "FF",
      "FC",
      "FD",
      "FD",
      "01",
      "FE",
      "00",
      "FF",
      "FE",
      "FC",
      "01",
      "01",
      "FD",
      "FF",
      "FC",
      "FE",
      "01",
      "00",
      "FE",
      "00",
      "FD",
      "FC",
      "00",
      "FE",
      "FF",
      "FD",
      "00",
      "FC",
      "02",
      "00",
      "FE",
      "FF",
      "02",
      "01",
      "FD",
      "FC",
      "FC",
      "02",
      "FF",
      "FF",
      "00",
      "00",
      "FC",
      "01",
      "FE",
      "01",
      "FF",
      "FF",
      "02",
      "02",
      "FE",
      "00",
      "01",
      "FD",
      "02",
      "FD",
      "02",
      "FE",
      "00",
      "FD",
      "02",
      "02",
      "FC",
      "01",
      "FC",
      "FE",
      "FC",
      "01",
      "FF",
      "FF",
      "01",
      "01",
      "FE",
      "01",
      "FF",
      "01",
      "FF",
      "02",
      "00",
      "02",
      "FD",
      "FD",
      "FD",
      "00",
      "02",
      "FE",
      "01",
      "00")
    val vecWGT_2 = Array("FD",
      "FF",
      "FC",
      "FD",
      "01",
      "FE",
      "FE",
      "02",
      "01",
      "FD",
      "FE",
      "01",
      "01",
      "FD",
      "01",
      "FD",
      "FF",
      "FE",
      "01",
      "FF",
      "00",
      "00",
      "FD",
      "FF",
      "02",
      "FE",
      "FC",
      "FD",
      "00",
      "FD",
      "FC",
      "02",
      "00",
      "01",
      "FD",
      "FD",
      "FE",
      "FF",
      "02",
      "FE",
      "FE",
      "01",
      "FE",
      "FE",
      "00",
      "01",
      "FE",
      "02",
      "FE",
      "01",
      "00",
      "FC",
      "FE",
      "FE",
      "00",
      "FC",
      "FD",
      "FC",
      "FC",
      "FF",
      "00",
      "FD",
      "02",
      "02",
      "FC",
      "02",
      "02",
      "00",
      "FF",
      "02",
      "01",
      "FF",
      "FC",
      "FE",
      "02",
      "02",
      "FF",
      "02",
      "FE",
      "02",
      "FE",
      "FE",
      "FC",
      "FC",
      "00",
      "FD",
      "FD",
      "FF",
      "00",
      "FF",
      "FE",
      "02",
      "01",
      "01",
      "FF",
      "01",
      "02",
      "00",
      "01",
      "FD",
      "00",
      "01",
      "FD",
      "FE",
      "01",
      "02",
      "01",
      "FF",
      "02",
      "00",
      "00",
      "00",
      "00",
      "02",
      "00",
      "00",
      "02",
      "00",
      "FD",
      "02",
      "01",
      "FC",
      "FF",
      "FF",
      "FC",
      "01",
      "02",
      "01",
      "FE",
      "01",
      "FF",
      "00",
      "FF",
      "00",
      "FE",
      "02",
      "FE",
      "FD",
      "00",
      "01",
      "FF",
      "00",
      "00",
      "FE",
      "02",
      "FC",
      "FC",
      "01",
      "00",
      "FE",
      "02",
      "FE",
      "FE",
      "02",
      "02",
      "FF",
      "FF",
      "FE",
      "02",
      "FF",
      "FD",
      "01",
      "FC",
      "FF",
      "FE",
      "02",
      "02",
      "FC",
      "02",
      "FD",
      "02",
      "00",
      "FF",
      "01",
      "FD",
      "FE",
      "02",
      "00",
      "FF",
      "01",
      "FE",
      "FE",
      "FD",
      "FD",
      "FE",
      "FC",
      "01",
      "FF",
      "FE",
      "FF",
      "FC",
      "FD",
      "FD",
      "FC",
      "02",
      "01",
      "FF",
      "FE",
      "FC",
      "00",
      "FF",
      "FF",
      "01",
      "FC",
      "FE",
      "FC",
      "FD",
      "01",
      "00",
      "FE",
      "FE",
      "02",
      "FC",
      "01",
      "00",
      "FF",
      "02",
      "FE",
      "FE",
      "02",
      "FD",
      "FC",
      "FC",
      "FC",
      "FF",
      "FF",
      "01",
      "01",
      "FC",
      "FD",
      "02",
      "FE",
      "01",
      "FE",
      "FF",
      "02",
      "FF",
      "FD",
      "02",
      "FF",
      "00",
      "FC",
      "FD",
      "FF",
      "00",
      "FD",
      "01",
      "00",
      "FC",
      "FF",
      "00",
      "FC",
      "02",
      "FF",
      "00",
      "02")
    // String to decimal conversion for the first WGT block
    val wgtVec_0: Array[BigInt] = vecWGT_0.map { hex =>
      val decimal = java.lang.Integer.parseInt(hex, 16)
      if (decimal >= 128) BigInt(decimal - 256) else BigInt(decimal)
    }
    val wgtVec_1: Array[BigInt] = vecWGT_1.map { hex =>
      val decimal = java.lang.Integer.parseInt(hex, 16)
      if (decimal >= 128) BigInt(decimal - 256) else BigInt(decimal)
    }
    val wgtVec_2: Array[BigInt] = vecWGT_2.map { hex =>
      val decimal = java.lang.Integer.parseInt(hex, 16)
      if (decimal >= 128) BigInt(decimal - 256) else BigInt(decimal)
    }
    result match {
      case Success(data) =>
        data(0) should equal(wgtVec_0)
        data(1) should equal(wgtVec_1)
        data(2) should equal(wgtVec_2)
      case Failure(exception) =>
        fail(s"Error while computing addresses for WGT : ${exception.getMessage}")
    }
  }

  it should "decode four wgt vectors of 32x32_relu" in {
    val result = computeAddresses("examples_compute/32x32_relu/input.bin", DataType.INP, "00000000", isDRAM = false)
    result match {
      case Success(data) =>
        printMap(data, DataType.INP)
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
        data(8) should equal(Array(2, 32, 0)) // faux
        data(12) should equal(Array(0, 0, 0))
      case Failure(exception) =>
        fail(s"Error while computing addresses for UOPs : ${exception.getMessage}")

    }
  }

  it should "decode correctly the UOPs (4 Bytes each) in a binary file (conv1)" in {
    val result = computeAddresses("examples_compute/lenet5_conv1/uop.bin", DataType.UOP, "00000000", isDRAM = true)
    result match {
      case Success(data) =>
        data(0) should equal(Array(0, 0, 0))
        data(4) should equal(Array(0, 0, 0))
        data(8) should equal(Array(0, 16, 1))
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
    val result = computeAddresses("examples_compute/32x32_relu/weight.bin", DataType.WGT, "00000000", isDRAM = false)
    result match {
      case Success(data) =>
        printMap(data, DataType.WGT)
      case Failure(exception) =>
        fail(s"Error while computing addresses for WGT : ${exception.getMessage}")
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