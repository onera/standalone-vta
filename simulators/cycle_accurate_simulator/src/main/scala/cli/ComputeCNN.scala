package cli

import chiseltest.iotesters.PeekPokeTester
import util.BinaryReader.{DataType, computeCSVFile, readFile}
import util.{Filter, GenericSim}
import util.Reshape.{reshape, vector_to_map}
import vta.core.Compute
import vta.util.config.Parameters

import java.io.File
import scala.util.matching.Regex
import scala.util.{Failure, Success}

class ComputeCNN(c: Compute, CNN_param: String, doCompare: Boolean = true, debug: Boolean = true, fromResources: Boolean = false)
  extends PeekPokeTester(c) {

  /** params contains a description of the CNN
    * layers : Int = number of layers of the CNN
    * doReshape : Boolean = whether the output of the layer needs reshaping
    * For each layer, if doReshape = true, the reshaping parameters are listed
      ** Filter parameters : in case of average pooling, removes unnecessary vectors from output
        * uop : Int = initial index in output scratchpad upon which to begin filtering process
        * loop_in : Int = internal loops
        * loop_out : Int = external loops
        * dst_in : Int
        * dst_out : Int
      ** Reshape parameters : reshaping filtered output into next-layer input
        * block_col : Int
        * block_size : Int
        * out_matrix_height : Int
        * out_matrix_width : Int
        * batch_size : Int
        * out_tensor_channel : Int
        * out_tensor_height : Int
        * out_tensor_width : Int
        * kernel_size : (Int; Int)
        * stride : Int
        * isSquare : Boolean
  */
  val params = computeCSVFile(CNN_param, fromResources, isBaseAddr = false)
  val nb_layers = params("layers").toInt
  var outScratchpad: Map[BigInt, Array[BigInt]] = Map.empty

  def fileExists(filePath: String): Boolean = {
    val newFilePath =
      if (!fromResources) {
        val projectRoot = new File("../../")
        val compilerOutputDir = new File(projectRoot, "compiler_output")
        val basePath = compilerOutputDir.getCanonicalPath
        s"$basePath/" + filePath
      }
      else {
        filePath
      }
    new File(newFilePath).exists()
  }

  for (i <- 1 to nb_layers) {
    val inputFile = if (i == 1)
      ComputeSimulator.build_scratchpad_binary("input.bin", DataType.INP, ComputeSimulator.getBaseAddr(s"base_addr_L$i.csv", fromResources)("inp"), isDRAM = false, fromResources)
    else outScratchpad

    val computeSimulator =
      if (doCompare && fileExists(s"outL$i.bin")) {
        new ComputeSimulator(c,
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
          doCompare = true, debug, fromResources)
      }
      else {
        new ComputeSimulator(c,
          s"instructions_L$i.bin",
          s"uop_L$i.bin",
          inputFile,
          //params(s"input$i"),
          //(if (i == 0) "input.bin" else outScratchpad),
          s"weight_L$i.bin",
          s"out_init_L$i.bin",
          "accumulator.bin",
          s"base_addr_L$i.csv",
          doCompare = false, debug, fromResources)
      }

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

class ComputeLeNet5_generic_file_exists extends GenericSim("ComputeLeNet5_generic_file_exists", (p:Parameters) =>
  new Compute(false)(p), (c: Compute) => new ComputeCNN(c, "lenet_params.csv"))