package cli

import chiseltest.iotesters.PeekPokeTester
import util.BinaryReader.{DataType, computeCSVFile, readCSVFile}
import util.{Filter, GenericSim}
import util.Reshape.{reshape, vector_to_map}
import vta.core.Compute
import vta.util.config.Parameters

import java.io.File
import scala.util.matching.Regex
import scala.util.{Failure, Success}

class ComputeCNN(c: Compute, CNN_param: String, doCompare: Boolean = true, debug: Boolean = true, fromResources: Boolean = false)
  extends PeekPokeTester(c) {

  val params = computeCSVFile(CNN_param, fromResources, isBaseAddr = false)
  val nb_layers = params("layers").toInt
  var outScratchpad: Map[BigInt, Array[BigInt]] = Map.empty

  for (i <- 1 to nb_layers) {
    val inputFile = if (i == 1)
      ComputeSimulator.build_scratchpad_binary("input.bin", DataType.INP, ComputeSimulator.getBaseAddr(s"base_addr_L$i.csv", fromResources)("inp"), isDRAM = false, fromResources)
    else outScratchpad

    val computeSimulator = new ComputeSimulator(c,
      s"instructions_L$i.bin",
      s"uop_L$i.bin",
      inputFile,
      //params(s"input$i"),
      //(if (i == 0) "input.bin" else outScratchpad),
      s"weight_L$i.bin",
      s"out_init_L$i.bin",
      "accumulator.bin",
      s"outL$i.bin",
      s"base_addr_L$i.csv",
      doCompare, debug, fromResources)

    outScratchpad =
      if (params(s"doReshape$i").toBoolean) {
        val filteredOut = Filter.filter(computeSimulator.getOutScratchpad, params(s"uop$i").toInt, params(s"loop_in$i").toInt, params(s"loop_out$i").toInt,
          params(s"dst_in$i").toInt, params(s"dst_out$i").toInt)
        val out_vec = filteredOut.toSeq.sortBy(_._1).flatMap {
          case (_, array) => array
        }.toArray
        val pattern = """\((\d+);(\d+)\)""".r
        val kernel_size = params(s"kernel_size$i") match {
          case pattern(a, b) =>
            (a.toInt, b.toInt)
        }
        val reshaped_out = reshape(out_vec, params(s"block_col$i").toInt, params(s"block_size$i").toInt, params(s"out_matrix_height$i").toInt,
          params(s"out_matrix_width$i").toInt, params(s"batch_size$i").toInt, params(s"out_tensor_channel$i").toInt, params(s"out_tensor_height$i").toInt,
          params(s"out_tensor_width$i").toInt, kernel_size, params(s"stride$i").toInt, params(s"isSquare$i").toBoolean)
        val j = i + 1
        val base_addr_inp = ComputeSimulator.getBaseAddr(s"base_addr_L$j.csv", fromResources = false)
        vector_to_map(reshaped_out, base_addr_inp("inp"))
      }
      else {
        computeSimulator.getOutScratchpad
      }
  }
}

class ComputeLeNet5_generic extends GenericSim("ComputeLeNet5_generic", (p:Parameters) =>
  new Compute(false)(p), (c: Compute) => new ComputeCNN(c, "lenet_params.csv"))