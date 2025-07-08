package util

import org.scalatest.flatspec.AnyFlatSpec
import org.scalatest.matchers.should
import util.BinaryReader.{DataType, computeAddresses, printMap}
import util.Filter.filter

import scala.util.{Failure, Success}

class FilterTest extends AnyFlatSpec with should.Matchers {
  "Filter" should "correctly filter LeNet L1 output" in {
    val outL1_ref = computeAddresses("examples_compute/lenet5/outL1_test.bin", DataType.OUT, "00000000", isDRAM = false, fromResources = true)
    val outL1_sram = computeAddresses("examples_compute/lenet5/outL1.bin", DataType.OUT, "00000000", isDRAM = false, fromResources = true)
    outL1_ref match {
      case Success(data) =>
        outL1_sram match {
          case Success(data_sram) =>
            val filteredOut = filter(data_sram, 0, 14, 14, 2, 56)
            for {
              key <- data.keySet
              value = filteredOut(key)
              val_ref = data(key)
            } yield value should equal(val_ref)
            data.size should equal(filteredOut.size)
          case Failure(exception) =>
            fail(s"Error while filtering output of layer1 : ${exception.getMessage}")
        }
      case Failure(exception) =>
        fail(s"Error while filtering output of layer1 : ${exception.getMessage}")
    }
  }


  it should "correctly filter LeNet L2 output" in {
    val outL2_ref = computeAddresses("examples_compute/lenet5/outL2_test.bin", DataType.OUT, "00000000", isDRAM = false, fromResources = true)
    val outL2_sram = computeAddresses("examples_compute/lenet5/outL2.bin", DataType.OUT, "00000000", isDRAM = false, fromResources = true)
    outL2_ref match {
      case Success(data) =>
        outL2_sram match {
          case Success(data_sram) =>
            val filteredOut = filter(data_sram, 0, 5, 5, 2, 20)
            for {
              key <- data.keySet
              value = filteredOut(key)
              val_ref = data(key)
            } yield value should equal(val_ref)
            data.size should equal(filteredOut.size)
          case Failure(exception) =>
            fail(s"Error while filtering output of layer2 : ${exception.getMessage}")
        }
      case Failure(exception) =>
        fail(s"Error while filtering output of layer2 : ${exception.getMessage}")
    }
  }
}