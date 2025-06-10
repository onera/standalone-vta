package util

import org.scalatest.flatspec.AnyFlatSpec
import org.scalatest.matchers.should
import util.Reshape._
import util.BinaryReader._

import scala.util.{Failure, Success}

class ReshapeTest extends AnyFlatSpec with should.Matchers {

  "Reshape" should "match cycle-accurate sim output Layer1 of LeNet-5 with ref" in {
    val outL1_ref = computeAddresses("outL1.bin", DataType.OUT, "00000000", false, false)
    val outL1_sim = ??? //sortie de computesim ou utiliser out_expect
  }

  it should "match cycle-accurate sim input Layer2 of LeNet-5 with reshaped output Layer1" in {
    val outL1_ref = computeAddresses("outL1.bin", DataType.OUT, "00000000", isDRAM = false, fromResources = false)
    val inpL2_ref = computeAddresses("inpL2.bin", DataType.INP, "00000000", isDRAM = false, fromResources = false) //.toArray.map(_._1).sorted
    outL1_ref match {
      case Success(data_out) =>
        inpL2_ref match {
          case Success(data_inp) =>
            println(data_inp(0).mkString("Array(", ", ", ")"))
            println(data_out(0).mkString("Array(", ", ", ")"))
            println(data_inp.size * 16)
            val inpL2_vec = data_inp.toSeq.sortBy(_._1).flatMap {
              case (_, array) => array
            }.toArray
            println(inpL2_vec.length)
            val outL1_vec = data_out.toSeq.sortBy(_._1).flatMap {
              case (_, array) => array
            }.toArray
            val reshaped_outL1 = reshape(outL1_vec, 1, 16, 196, 6, 1, 6, 14, 14, (5, 5), 1, isSquare = true)
            println(reshaped_outL1.mkString("Array(", ", ", ")"))
            for (inp_val <- inpL2_vec) {
              for (reshaped_out_val <- reshaped_outL1) {
                inp_val should equal(reshaped_out_val)
              }
            }
          case Failure(exception) =>
            fail(s"Error while reshaping output of layer1 : ${exception.getMessage}")
        }
      case Failure(exception) =>
        fail(s"Error while reshaping output of layer1 : ${exception.getMessage}")
    }
  }

  it should "match input layer3 of lenet-5 with reshaped output layer2" in {
    val outL2_ref = computeAddresses("outL2.bin", DataType.OUT, "00000000", isDRAM = false, fromResources = false)
    print("outL2 ok\n")
    val inpL3_ref = computeAddresses("inpL3.bin", DataType.INP, "00000000", isDRAM = false, fromResources = false)
    print("inpL3 ok\n")
    outL2_ref match {
      case Success(data_out) =>
        inpL3_ref match {
          case Success(data_inp) =>
            val inpL3_vec = data_inp.toArray.map(_._1).sorted
            val outL2_vec = data_out.toArray.map(_._1).sorted
            val reshaped_outL2 = reshape(outL2_vec, 1, 16, 25, 16, 1, 16, 5, 5, (5, 5), 1, isSquare = false)
            for (inp_val <- inpL3_vec) {
              for (reshaped_out_val <- reshaped_outL2) {
                println(inp_val + "  " + reshaped_out_val)
                inp_val should equal(reshaped_out_val)
              }
            }
          case Failure(exception) =>
            fail(s"Error while reshaping output of layer2 : ${exception.getMessage}")
        }
      case Failure(exception) =>
        fail(s"Error while reshaping output of layer2: ${exception.getMessage}")
    }
  }
}