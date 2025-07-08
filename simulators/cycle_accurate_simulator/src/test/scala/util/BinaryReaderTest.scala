package util

import org.scalatest.flatspec.AnyFlatSpec
import org.scalatest.matchers.should
import util.BinaryReader._

import java.io.File
import java.math.BigInteger
import scala.util.{Failure, Success}

class BinaryReaderTest extends AnyFlatSpec with should.Matchers {

  /* Decoding INP */
  "BinaryReader" should "decode correctly the first vector of INP (16 Bytes) in a binary file (16x16)" in {
    val result = computeAddresses("examples_compute/16x16/input.bin", DataType.INP, "00000000", isDRAM = false, fromResources = true)
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

  it should "decode the vectors 0 and 16 and 32 of INP in 32x32_relu" in {
    val result = computeAddresses("examples_compute/32x32_relu/input.bin", DataType.INP, "00000000", isDRAM = false, fromResources = true)
    val inp0 = Array("02",
      "00",
      "FE",
      "FE",
      "01",
      "FF",
      "FF",
      "00",
      "FD",
      "FC",
      "00",
      "FC",
      "FE",
      "00",
      "00",
      "FF")
    val inp16 = Array("02",
      "FE",
      "FD",
      "FD",
      "FF",
      "FC",
      "FD",
      "FF",
      "02",
      "FF",
      "02",
      "00",
      "FC",
      "FC",
      "FF",
      "FF")
    val inp32 = Array("01",
      "FD",
      "FD",
      "00",
      "00",
      "FE",
      "FF",
      "FE",
      "00",
      "FC",
      "00",
      "FF",
      "00",
      "01",
      "02",
      "FF")
    val inp0_dec = inp0.map { hex =>
      val decimal = java.lang.Integer.parseInt(hex, 16)
      if (decimal >= 128) BigInt(decimal - 256) else BigInt(decimal)
    }
    val inp16_dec = inp16.map { hex =>
      val decimal = java.lang.Integer.parseInt(hex, 16)
      if (decimal >= 128) BigInt(decimal - 256) else BigInt(decimal)
    }
    val inp32_dec = inp32.map { hex =>
      val decimal = java.lang.Integer.parseInt(hex, 16)
      if (decimal >= 128) BigInt(decimal - 256) else BigInt(decimal)
    }
    result match {
      case Success(data) =>
        data(0) should equal(inp0_dec)
        data(16) should equal(inp16_dec)
        data(32) should equal(inp32_dec)
      case Failure(exception) =>
        fail(s"Error while computing addresses for INP : ${exception.getMessage}")
    }
  }

  it should "return the same value if an offset is or isn't used for the first vector of INP" in {
    val resultOffset = computeAddresses("examples_compute/lenet5_layer1/input.bin", DataType.INP, "00001000", isDRAM = false, fromResources = true)
    val resultWithoutOffset = computeAddresses("examples_compute/lenet5_layer1/input.bin", DataType.INP, "00000000", isDRAM = false, fromResources = true)

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
    val resultOffset = computeAddresses("examples_compute/lenet5_layer1/input.bin", DataType.INP, offset, isDRAM = false, fromResources = true)
    val resultWithoutOffset = computeAddresses("examples_compute/lenet5_layer1/input.bin", DataType.INP, "00000000", isDRAM = false, fromResources = true)
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

//  it should "decode the content of binary files in /compiler_output" in {
//    // test done on files for matrix_16x16 - will work for make FILENAME=matrix_16x16
//    val baseAddr = computeCSVFile("memory_addresses.csv", fromResources = false)
//    val inp = computeAddresses("input.bin", DataType.INP, baseAddr("inp"), isDRAM = false, fromResources = false)
//    val inp_vec0 = Array(-1, 0, -3, -4, -2, -2, 2, -2, 0, -3, -4, 2, 0, -4, -4, 1)
//    inp match {
//      case Success(data) =>
//        data(0) should equal(inp_vec0)
//      case Failure(exception) =>
//        fail(s"Error while computing addresses for INP : ${exception.getMessage}")
//    }
//  }


  /* Decoding WGT */
  it should "decode all the WGT vectors in 32x32_relu" in {
    val result = computeAddresses("examples_compute/32x32_relu/weight.bin", DataType.WGT, "00000000", isDRAM = false, fromResources = true)
    val vecWGT_0 = Array("FD",
      "02",
      "FE",
      "00",
      "00",
      "FD",
      "FE",
      "FF",
      "00",
      "FC",
      "FF",
      "FE",
      "FD",
      "FF",
      "FF",
      "00",
      "02",
      "FC",
      "02",
      "00",
      "00",
      "FC",
      "FE",
      "FF",
      "FF",
      "02",
      "FE",
      "FC",
      "FE",
      "FC",
      "FE",
      "FC",
      "FD",
      "FF",
      "FF",
      "00",
      "FF",
      "00",
      "00",
      "FD",
      "FE",
      "FC",
      "FD",
      "FD",
      "00",
      "FF",
      "FF",
      "02",
      "FD",
      "FE",
      "01",
      "00",
      "FE",
      "FE",
      "02",
      "FC",
      "02",
      "01",
      "FC",
      "02",
      "00",
      "00",
      "FD",
      "FC",
      "FF",
      "01",
      "FE",
      "FD",
      "02",
      "FE",
      "01",
      "FD",
      "FE",
      "FF",
      "FD",
      "00",
      "02",
      "FF",
      "02",
      "FD",
      "FC",
      "02",
      "01",
      "01",
      "FD",
      "FD",
      "00",
      "00",
      "FF",
      "00",
      "01",
      "FE",
      "00",
      "FF",
      "FF",
      "FE",
      "FE",
      "02",
      "01",
      "00",
      "00",
      "FC",
      "02",
      "FD",
      "FE",
      "00",
      "FC",
      "02",
      "FE",
      "FD",
      "00",
      "02",
      "FC",
      "FC",
      "01",
      "FE",
      "FF",
      "01",
      "02",
      "FE",
      "02",
      "01",
      "FE",
      "02",
      "01",
      "FD",
      "FE",
      "FD",
      "02",
      "FF",
      "FC",
      "FD",
      "02",
      "00",
      "FE",
      "00",
      "FF",
      "00",
      "FE",
      "FF",
      "FF",
      "FF",
      "01",
      "FF",
      "FC",
      "FE",
      "01",
      "FE",
      "FE",
      "01",
      "FD",
      "FE",
      "FE",
      "FE",
      "FE",
      "00",
      "00",
      "FF",
      "FF",
      "FC",
      "02",
      "FF",
      "02",
      "02",
      "02",
      "FD",
      "FD",
      "00",
      "01",
      "FD",
      "FD",
      "FD",
      "FD",
      "02",
      "02",
      "02",
      "FC",
      "00",
      "01",
      "FE",
      "01",
      "01",
      "01",
      "FF",
      "FF",
      "02",
      "FE",
      "FD",
      "FF",
      "01",
      "FE",
      "FC",
      "FE",
      "FC",
      "FC",
      "00",
      "01",
      "00",
      "02",
      "FC",
      "01",
      "FF",
      "FF",
      "FE",
      "FE",
      "FC",
      "FF",
      "00",
      "01",
      "FF",
      "FC",
      "FF",
      "FD",
      "FF",
      "01",
      "FE",
      "FE",
      "FF",
      "FC",
      "FC",
      "FC",
      "FE",
      "FF",
      "FE",
      "FF",
      "FD",
      "00",
      "FD",
      "02",
      "FF",
      "01",
      "FD",
      "FD",
      "FC",
      "01",
      "02",
      "FD",
      "FC",
      "FD",
      "02",
      "01",
      "02",
      "FC",
      "FE",
      "00",
      "FD",
      "FF",
      "FF",
      "FF",
      "FF",
      "01",
      "00",
      "FF",
      "FF",
      "01",
      "FE")
    val vecWGT_1 = Array("FD",
      "01",
      "FF",
      "FE",
      "FF",
      "FF",
      "FD",
      "FF",
      "FC",
      "FD",
      "00",
      "02",
      "FD",
      "FE",
      "02",
      "00",
      "FE",
      "00",
      "02",
      "FF",
      "FE",
      "FE",
      "00",
      "02",
      "FF",
      "FC",
      "02",
      "FD",
      "FE",
      "00",
      "FD",
      "FD",
      "00",
      "FC",
      "FE",
      "FF",
      "02",
      "01",
      "FC",
      "01",
      "00",
      "02",
      "FD",
      "02",
      "01",
      "00",
      "FC",
      "FE",
      "02",
      "FE",
      "FE",
      "02",
      "02",
      "00",
      "FC",
      "FD",
      "FC",
      "02",
      "02",
      "FC",
      "FE",
      "02",
      "02",
      "00",
      "00",
      "FF",
      "FE",
      "00",
      "FC",
      "FF",
      "01",
      "02",
      "FD",
      "FD",
      "02",
      "FC",
      "00",
      "FE",
      "01",
      "FC",
      "FC",
      "FF",
      "02",
      "FC",
      "02",
      "FD",
      "FC",
      "01",
      "01",
      "01",
      "00",
      "FD",
      "00",
      "02",
      "FD",
      "01",
      "FF",
      "02",
      "FC",
      "00",
      "FE",
      "FF",
      "00",
      "FD",
      "02",
      "FC",
      "02",
      "01",
      "FE",
      "02",
      "01",
      "FC",
      "FC",
      "01",
      "00",
      "FC",
      "FC",
      "FC",
      "FF",
      "02",
      "01",
      "FF",
      "FD",
      "01",
      "02",
      "01",
      "02",
      "02",
      "FE",
      "00",
      "00",
      "00",
      "FD",
      "FE",
      "FD",
      "00",
      "00",
      "FF",
      "FD",
      "FE",
      "FD",
      "FE",
      "FC",
      "01",
      "FE",
      "FF",
      "FC",
      "FF",
      "FD",
      "00",
      "01",
      "FD",
      "FD",
      "FF",
      "00",
      "FE",
      "00",
      "02",
      "FF",
      "00",
      "01",
      "00",
      "FE",
      "02",
      "FF",
      "FC",
      "FD",
      "FC",
      "FF",
      "02",
      "01",
      "FE",
      "02",
      "FC",
      "01",
      "FD",
      "01",
      "01",
      "FD",
      "FC",
      "FC",
      "FD",
      "FE",
      "FC",
      "02",
      "FC",
      "FD",
      "FD",
      "FC",
      "00",
      "FF",
      "00",
      "00",
      "01",
      "FD",
      "00",
      "FD",
      "FC",
      "02",
      "FD",
      "FC",
      "FF",
      "02",
      "FF",
      "01",
      "FD",
      "02",
      "01",
      "FF",
      "FD",
      "02",
      "FC",
      "02",
      "FF",
      "00",
      "FD",
      "01",
      "FD",
      "FC",
      "FC",
      "00",
      "00",
      "00",
      "01",
      "FE",
      "FD",
      "00",
      "FE",
      "01",
      "FC",
      "02",
      "FD",
      "01",
      "FE",
      "02",
      "FC",
      "FC",
      "02",
      "01",
      "FD",
      "FD",
      "FD",
      "01",
      "FF",
      "02",
      "02",
      "FE",
      "FF",
      "FD",
      "FD",
      "02",
      "02",
      "FF",
      "01",
      "FC",
      "FE")
    val vecWGT_2 = Array("02",
      "FD",
      "00",
      "FE",
      "02",
      "FD",
      "01",
      "02",
      "01",
      "FD",
      "02",
      "FC",
      "FD",
      "FF",
      "FF",
      "FF",
      "02",
      "00",
      "FC",
      "FD",
      "FF",
      "01",
      "FF",
      "00",
      "FC",
      "02",
      "00",
      "00",
      "FE",
      "00",
      "FE",
      "FE",
      "FE",
      "02",
      "FC",
      "FC",
      "00",
      "FE",
      "FF",
      "FE",
      "00",
      "01",
      "FF",
      "FE",
      "00",
      "FE",
      "FE",
      "FF",
      "01",
      "FD",
      "FC",
      "01",
      "02",
      "FE",
      "FC",
      "00",
      "FD",
      "00",
      "FE",
      "FD",
      "01",
      "FD",
      "01",
      "FC",
      "FC",
      "FC",
      "FE",
      "00",
      "00",
      "01",
      "01",
      "00",
      "00",
      "FF",
      "FE",
      "01",
      "01",
      "02",
      "FE",
      "01",
      "01",
      "FD",
      "FD",
      "FD",
      "FF",
      "01",
      "FE",
      "FD",
      "00",
      "FC",
      "FE",
      "02",
      "00",
      "01",
      "FF",
      "01",
      "FE",
      "FD",
      "00",
      "01",
      "00",
      "FE",
      "FD",
      "FE",
      "00",
      "00",
      "00",
      "FD",
      "00",
      "02",
      "FC",
      "01",
      "02",
      "02",
      "FF",
      "FF",
      "00",
      "FF",
      "01",
      "FE",
      "FE",
      "FD",
      "FE",
      "FF",
      "FF",
      "FC",
      "FC",
      "00",
      "FD",
      "02",
      "FC",
      "FE",
      "01",
      "FC",
      "FC",
      "01",
      "FE",
      "FD",
      "FF",
      "FC",
      "00",
      "FF",
      "FD",
      "FF",
      "02",
      "FC",
      "02",
      "FE",
      "FE",
      "FC",
      "FD",
      "01",
      "02",
      "FD",
      "00",
      "FE",
      "01",
      "02",
      "02",
      "FD",
      "01",
      "02",
      "01",
      "FC",
      "01",
      "FE",
      "FF",
      "FF",
      "FC",
      "FC",
      "02",
      "FE",
      "FE",
      "00",
      "FC",
      "01",
      "02",
      "02",
      "00",
      "FF",
      "FC",
      "02",
      "FD",
      "FE",
      "FC",
      "FC",
      "00",
      "FD",
      "FE",
      "FE",
      "FF",
      "02",
      "00",
      "FD",
      "01",
      "FE",
      "FF",
      "FF",
      "FC",
      "01",
      "FF",
      "01",
      "FD",
      "FD",
      "FC",
      "FF",
      "02",
      "02",
      "00",
      "FD",
      "FE",
      "FC",
      "FF",
      "FE",
      "00",
      "01",
      "FD",
      "FC",
      "FC",
      "01",
      "FC",
      "01",
      "FC",
      "FC",
      "FD",
      "FE",
      "FC",
      "02",
      "00",
      "00",
      "FF",
      "FE",
      "00",
      "00",
      "02",
      "FD",
      "FC",
      "02",
      "FF",
      "00",
      "FD",
      "01",
      "FC",
      "FE",
      "FD",
      "02",
      "02",
      "01",
      "02",
      "FF",
      "FF",
      "01",
      "FC",
      "FF",
      "00",
      "00")
    val vecWGT_3 = Array("02",
      "01",
      "FF",
      "FD",
      "00",
      "02",
      "02",
      "FC",
      "00",
      "FC",
      "01",
      "FF",
      "FE",
      "FE",
      "FE",
      "FD",
      "00",
      "FD",
      "FD",
      "02",
      "01",
      "02",
      "FC",
      "FD",
      "01",
      "01",
      "00",
      "02",
      "02",
      "FD",
      "FF",
      "FC",
      "00",
      "FC",
      "FC",
      "FE",
      "FC",
      "02",
      "00",
      "FD",
      "FC",
      "FE",
      "02",
      "FC",
      "02",
      "00",
      "01",
      "FE",
      "FD",
      "02",
      "FD",
      "FE",
      "FF",
      "FF",
      "FE",
      "FD",
      "FE",
      "FD",
      "01",
      "FC",
      "FE",
      "FF",
      "01",
      "02",
      "02",
      "02",
      "01",
      "FD",
      "FE",
      "FC",
      "FD",
      "00",
      "FC",
      "02",
      "FF",
      "FF",
      "FC",
      "01",
      "FF",
      "FD",
      "FF",
      "FE",
      "FE",
      "01",
      "FD",
      "FC",
      "FF",
      "FD",
      "FC",
      "02",
      "00",
      "00",
      "01",
      "02",
      "FD",
      "FC",
      "FE",
      "FF",
      "02",
      "FC",
      "FE",
      "01",
      "01",
      "FC",
      "FC",
      "FF",
      "00",
      "FF",
      "02",
      "FF",
      "FF",
      "02",
      "01",
      "01",
      "FC",
      "00",
      "FD",
      "FF",
      "FD",
      "FF",
      "FE",
      "01",
      "FD",
      "01",
      "FC",
      "00",
      "FF",
      "00",
      "FD",
      "00",
      "FF",
      "FE",
      "02",
      "00",
      "02",
      "FE",
      "FE",
      "FF",
      "00",
      "FD",
      "00",
      "01",
      "FD",
      "00",
      "FC",
      "00",
      "FF",
      "FC",
      "FC",
      "01",
      "FE",
      "02",
      "00",
      "02",
      "01",
      "FC",
      "FF",
      "FC",
      "FE",
      "FE",
      "FE",
      "FF",
      "00",
      "01",
      "02",
      "02",
      "FC",
      "FD",
      "FD",
      "FC",
      "02",
      "FD",
      "FE",
      "00",
      "FF",
      "02",
      "02",
      "01",
      "00",
      "FC",
      "FC",
      "FC",
      "02",
      "FC",
      "FD",
      "FF",
      "00",
      "FD",
      "FC",
      "FC",
      "00",
      "02",
      "00",
      "FE",
      "FD",
      "FD",
      "FF",
      "FD",
      "00",
      "00",
      "00",
      "FD",
      "FF",
      "FC",
      "00",
      "FD",
      "01",
      "FE",
      "FE",
      "FD",
      "FD",
      "00",
      "FF",
      "FF",
      "FC",
      "FF",
      "02",
      "FE",
      "FE",
      "02",
      "FE",
      "01",
      "FD",
      "FC",
      "FF",
      "FF",
      "02",
      "00",
      "FE",
      "FF",
      "02",
      "00",
      "00",
      "FF",
      "FE",
      "FC",
      "00",
      "00",
      "FC",
      "00",
      "FD",
      "FC",
      "FE",
      "01",
      "FD",
      "FF",
      "00",
      "FE",
      "01",
      "00",
      "FE",
      "02",
      "FD",
      "FE",
      "FE",
      "01")
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
    val wgtVec_3: Array[BigInt] = vecWGT_3.map { hex =>
      val decimal = java.lang.Integer.parseInt(hex, 16)
      if (decimal >= 128) BigInt(decimal - 256) else BigInt(decimal)
    }
    result match {
      case Success(data) =>
        data(0) should equal(wgtVec_0)
        data(1) should equal(wgtVec_1)
        data(2) should equal(wgtVec_2)
        data(3) should equal(wgtVec_3)
      case Failure(exception) =>
        fail(s"Error while computing addresses for WGT : ${exception.getMessage}")
    }
  }


  /* Decoding OUT */
  it should "decode vectors 0 and 16 of OUT in 32x32_relu" in {
    val result = computeAddresses("examples_compute/32x32_relu/out.bin", DataType.OUT, "00000000", isDRAM = false, fromResources = true)
    val out = Array(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0)
    result match {
      case Success(data) =>
        data(0) should equal(out)
        data(16) should equal(out)
      case Failure(exception) =>
        fail(s"Error while computing addresses for OUT : ${exception.getMessage}")
    }
  }


  /* Decoding EXPECT_OUT */
  it should "decode correctly the first vector of EXPECT_OUT (16 Bytes) in a binary file" in {
    val result = computeAddresses("examples_compute/16x16/expected_out.bin", DataType.OUT, "00000000", isDRAM = false, fromResources = true)
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

  it should "decode vectors 0 and 16 of EXPECT_OUT in 32x32_relu" in {
    val result = computeAddresses("examples_compute/32x32_relu/expected_out.bin", DataType.OUT, "00000000", isDRAM = false, fromResources = true)
    val vec0 = Array("51",
      "34",
      "40",
      "0C",
      "05",
      "1D",
      "09",
      "01",
      "47",
      "2E",
      "3A",
      "1B",
      "30",
      "57",
      "31",
      "32")
    val vec16 = Array("38",
      "39",
      "0B",
      "3F",
      "4E",
      "18",
      "0A",
      "1B",
      "08",
      "3A",
      "13",
      "68",
      "47",
      "47",
      "1E",
      "2E")
    val vec0_dec: Array[BigInt] = vec0.map { hex =>
      val decimal = java.lang.Integer.parseInt(hex, 16)
      if (decimal >= 128) BigInt(decimal - 256) else BigInt(decimal)
    }
    val vec16_dec: Array[BigInt] = vec16.map { hex =>
      val decimal = java.lang.Integer.parseInt(hex, 16)
      if (decimal >= 128) BigInt(decimal - 256) else BigInt(decimal)
    }
    result match {
      case Success(data) =>
        data(0) should equal(vec0_dec)
        data(16) should equal(vec16_dec)
      case Failure(exception) =>
        fail(s"Error while computing addresses for EXPECT_OUT : ${exception.getMessage}")
    }
  }


  /* Decoding ACC */
  it should "decode ACC in average_pooling" in {
    val acc = computeAddresses("examples_compute/average_pooling/accumulator.bin", DataType.ACC, "00000000", isDRAM = true, fromResources = true)
    val acc_json = Array(-2, 2, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0)
    acc match {
      case Success(data) =>
        data(64) should equal(acc_json)
      case Failure(exception) =>
        fail(s"Error while computing addresses for ACC : ${exception.getMessage}")
    }
  }

  it should "decode correctly the first vector of ACC" in {
    val result = computeAddresses("examples_compute/16x16_relu/accumulator.bin", DataType.ACC, "00000000", isDRAM = true, fromResources = true)
    result match {
      case Success(data) =>
        data(0) should equal(Array(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0))
      case Failure(exception) =>
        fail(s"Error while computing addresses for ACC : ${exception.getMessage}")
    }
  }

  it should "decode correctly the first vector of ACC (64 Bytes) in a binary file (layer1)" in {
    val result = computeAddresses("examples_compute/lenet5_layer1/accumulator.bin", DataType.ACC, "00000000", isDRAM = true, fromResources = true)
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


  /* Decoding UOP */
  it should "decode correctly the UOPs (4 Bytes each) in a binary file (conv1)" in {
    val result = computeAddresses("examples_compute/lenet5_conv1/uop.bin", DataType.UOP, "00000000", isDRAM = true, fromResources = true)
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

  it should "decode correctly all the UOPs of a binary file (32x32_relu)" in {
    val result = computeAddresses("examples_compute/32x32_relu/uop.bin", DataType.UOP, "00000000", isDRAM = true, fromResources = true)
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

  /* Decoding Instructions */
  it should "decode correctly the first instruction (16 Bytes) in a binary file (layer1)" in {
    val result = computeAddresses("examples_compute/lenet5_layer1/instructions.bin", DataType.INSN, "00000000", isDRAM = false, fromResources = true)

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

  it should "decode correctly the last instruction in a binary file (layer1)" in {
    val result = computeAddresses("examples_compute/lenet5_layer1/instructions.bin", DataType.INSN, "00000000", isDRAM = false, fromResources = true)
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

  it should "decode the instructions in a binary file (32x32_relu)" in {
    val result = computeAddresses("examples_compute/32x32_relu/instructions.bin", DataType.INSN, "00000000", isDRAM = false, fromResources = true)
    val I0 = BigInt(
      Array(
        ("00000001", 96),
        ("00010001", 64),
        ("00000040", 32),
        ("00000000", 0)
      ).map { case (hex, shift) =>
        new BigInteger(hex, 16).shiftLeft(shift)
      }.reduce(_ add _))

    val I1 = BigInt(
      Array(
        ("00000000", 96),
        ("00000800", 64),
        ("00200008", 32),
        ("002000A2", 0)
      ).map { case (hex, shift) =>
        new BigInteger(hex, 16).shiftLeft(shift)
      }.reduce(_ add _))

    val I2 = BigInt(
      Array(
        ("00000040", 96),
        ("00400001", 64),
        ("00000004", 32),
        ("00000110", 0)
      ).map { case (hex, shift) =>
        new BigInteger(hex, 16).shiftLeft(shift)
      }.reduce(_ add _))

    val I3 = BigInt(
      Array(
        ("00000004", 96),
        ("00040001", 64),
        ("00000000", 32),
        ("800000C0", 0)
      ).map { case (hex, shift) =>
        new BigInteger(hex, 16).shiftLeft(shift)
      }.reduce(_ add _))

    val I4 = BigInt(
      Array(
        ("00000004", 96),
        ("00040001", 64),
        ("00000040", 32),
        ("04000408", 0)
      ).map { case (hex, shift) =>
        new BigInteger(hex, 16).shiftLeft(shift)
      }.reduce(_ add _))

    val I5 = BigInt(
      Array(
        ("00002002", 96),
        ("04000800", 64),
        ("00200010", 32),
        ("00A00102", 0)
      ).map { case (hex, shift) =>
        new BigInteger(hex, 16).shiftLeft(shift)
      }.reduce(_ add _))

    val I6 = BigInt(
      Array(
        ("00000001", 96),
        ("00010001", 64),
        ("00000040", 32),
        ("14001400", 0)
      ).map { case (hex, shift) =>
        new BigInteger(hex, 16).shiftLeft(shift)
      }.reduce(_ add _))

    val I7 = BigInt(
      Array(
        ("00009002", 96),
        ("00000800", 64),
        ("00800008", 32),
        ("00C00544", 0)
      ).map { case (hex, shift) =>
        new BigInteger(hex, 16).shiftLeft(shift)
      }.reduce(_ add _))

    val I11 = BigInt(
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
        data(0) should equal(Array(I0))
        data(1) should equal(Array(I1))
        data(2) should equal(Array(I2))
        data(3) should equal(Array(I3))
        data(4) should equal(Array(I4))
        data(5) should equal(Array(I5)) // GEMM
        data(6) should equal(Array(I6))
        data(7) should equal(Array(I7)) // RELU
        data(11) should equal(Array(I11))
      case Failure(exception) =>
        fail(s"Error while computing addresses for instructions : ${exception.getMessage}")
    }
  }

  /* Decoding CSV file for the base memory addresses */
  it should "decode the content of the csv file" in {
    val baseAddresses = computeCSVFile("examples_compute/lenet5_conv1/memory_addresses.csv", fromResources = true)
    //    baseAddresses.foreach { case (key, value) =>
    //      println(s"Clé: $key | Valeur: $value")
    //    }
    baseAddresses("inp") should equal("00000000")
    baseAddresses("wgt") should equal("00000000")
    baseAddresses("out") should equal("00000000")
    baseAddresses("uop") should equal("0000d000")
    baseAddresses("acc") should equal("0000e000")
  }
}