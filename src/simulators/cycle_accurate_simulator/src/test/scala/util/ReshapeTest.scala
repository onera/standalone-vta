package util

import org.scalatest.flatspec.AnyFlatSpec
import org.scalatest.matchers.should
import util.Reshape._
import util.BinaryReader._

import scala.util.{Failure, Success}

class ReshapeTest extends AnyFlatSpec with should.Matchers {

  "Reshape" should "match cycle-accurate sim input Layer2 of LeNet-5 with reshaped output Layer1" in {
    val outL1_ref = computeAddresses("examples_compute/lenet5/outL1_test.bin", DataType.OUT, "00000000", isDRAM = false, fromResources = true)
    val inpL2_ref = computeAddresses("examples_compute/lenet5/inpL2.bin", DataType.INP, "00000000", isDRAM = false, fromResources = true)
    outL1_ref match {
      case Success(data_out) =>
        inpL2_ref match {
          case Success(data_inp) =>
            val inpL2_vec = data_inp.toSeq.sortBy(_._1).flatMap {
              case (_, array) => array
            }.toArray
            val outL1_vec = data_out.toSeq.sortBy(_._1).flatMap {
              case (_, array) => array
            }.toArray
            val reshaped_outL1 = reshape(outL1_vec, 1, 16, 196, 6, 1, 6, 14, 14, (5, 5), 1, isSquare = true)
            for {
              key <- vector_to_map(reshaped_outL1, "00000000").keySet
              value = vector_to_map(reshaped_outL1, "00000000")(key)
              val_ref = data_inp(key)
            } yield value should equal(val_ref)
            reshaped_outL1 should equal(inpL2_vec)
          case Failure(exception) =>
            fail(s"Error while reshaping output of layer1 : ${exception.getMessage}")
        }
      case Failure(exception) =>
        fail(s"Error while reshaping output of layer1 : ${exception.getMessage}")
    }
  }

  it should "match input layer3 of lenet-5 with reshaped output layer2" in {
    val outL2_ref = computeAddresses("examples_compute/lenet5/outL2_test.bin", DataType.OUT, "00000000", isDRAM = false, fromResources = true)
    val inpL3_ref = computeAddresses("examples_compute/lenet5/inpL3.bin", DataType.INP, "00000000", isDRAM = false, fromResources = true)
    outL2_ref match {
      case Success(data_out) =>
        inpL3_ref match {
          case Success(data_inp) =>
            val inpL3_vec = data_inp.toSeq.sortBy(_._1).flatMap {
              case (_, array) => array
            }.toArray
            val outL2_vec = data_out.toSeq.sortBy(_._1).flatMap {
              case (_, array) => array
            }.toArray
            val reshaped_outL2 = reshape(outL2_vec, 1, 16, 25, 16, 1, 16, 5, 5, (5, 5), 1, isSquare = false)
            reshaped_outL2 should equal(inpL3_vec)
          case Failure(exception) =>
            fail(s"Error while reshaping output of layer2 : ${exception.getMessage}")
        }
      case Failure(exception) =>
        fail(s"Error while reshaping output of layer2: ${exception.getMessage}")
    }
  }
}