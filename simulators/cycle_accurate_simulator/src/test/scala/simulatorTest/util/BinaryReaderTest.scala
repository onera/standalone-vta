package simulatorTest.util

import org.scalatest.flatspec.AnyFlatSpec
import org.scalatest.matchers.should
import BinaryReader._

import java.math.BigInteger
import scala.util.{Failure, Success}

class BinaryReaderTest extends AnyFlatSpec with should.Matchers {

  "BinaryReader" should "decode correctly the first vector of INP (16 Bytes) in a binary file" in {
    val result = computeAddresses("examples_compute/lenet5_layer1/input.bin", DataType.INP, "00000000", isDRAM = false)
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
        data(0) should equal(inpFirstVector)
      case Failure(exception) =>
        fail(s"Error while computing addresses for INP : ${exception.getMessage}")
    }
  }

  it should "decode correctly the first vector of WGT (256 Bytes) in a binary file" in {
    val result = computeAddresses("examples_compute/lenet5_layer1/weight.bin", DataType.WGT, "00000000", isDRAM = false)
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
        data(0) should equal(wgtFirstBlock)
      case Failure(exception) =>
        fail(s"Error while computing addresses for WGT : ${exception.getMessage}")
    }
  }

  //FIXME remove success and failure in results and replace failure by fail (see example above)
  it should "decode correctly the first vector of EXPECT_OUT (16 Bytes) in a binary file" in {
    val result = computeAddresses("examples_compute/16x16_relu/expected_out.bin", DataType.OUT, "00000000", isDRAM = false)
    result match {
      case Success(data) =>
        Success(data(0) should equal(Array(43, -5, 25, 10, 35, 25, 5, 64, 43, -5, 35, 39, 28, -2, 1, 34)))
      case Failure(exception) =>
        println(s"Error while computing addresses for EXPECT_OUT : ${exception.getMessage}")
        Failure(exception)
    }
  }

  it should "decode correctly the UOPs (4 Bytes each) in a binary file" in {
    val result = computeAddresses("examples_compute/lenet5_layer1/uop.bin", DataType.UOP, "00000000", isDRAM = true)
    result match {
      case Success(data) =>
        Success(data(0) should equal(Array(0, 0, 0)),
          data(4) should equal(Array(0, 0, 0)),
          data(8) should equal(Array(2, 32, 0)),
          data(12) should equal(Array(0, 0, 0)))
      case Failure(exception) =>
        println(s"Error while computing addresses for UOPs : ${exception.getMessage}")
        Failure(exception)
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
        Success(data(0) should equal(Array(I0)))
      case Failure(exception) =>
        println(s"Error while computing addresses for instructions : ${exception.getMessage}")
        Failure(exception)
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
        Success(data(data.size - 1) should equal(Array(I_last)))
      case Failure(exception) =>
        println(s"Error while computing addresses for instructions : ${exception.getMessage}")
        Failure(exception)
    }
  }

  it should "decode correctly the first vector of ACC" in {
    val result = computeAddresses("examples_compute/16x16_relu/accumulator.bin", DataType.ACC, "00000000", isDRAM = true)
    result match {
      case Success(data) =>
        Success(data(0) should equal(Array(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0)))
      case Failure(exception) =>
        println(s"Error while computing addresses for instructions : ${exception.getMessage}")
        Failure(exception)
    }
  }

  it should "print the decoded data" in {
    val result = computeAddresses("examples_compute/lenet5_layer1/uop.bin", DataType.UOP, "00001000", isDRAM = true)
    result match {
      case Success(data) =>
        printMap(data, DataType.UOP)
      case Failure(exception) =>
        println(s"Error while computing addresses for UOPs : ${exception.getMessage}")
        Failure(exception)
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
            Success(dataOffset(idx + 1) should equal(dataWithoutOffset(1)))
          case Failure(exception) =>
            println(s"Error while computing addresses for INP without an offset : ${exception.getMessage}")
            Failure(exception)
        }
      case Failure(exception) =>
        println(s"Error while computing addresses for INP with an offset : ${exception.getMessage}")
        Failure(exception)
    }
  }

  it should ""
}