package util

import botkop.numsca._
import breeze.linalg.{DenseMatrix, DenseVector}
import spire.implicits.convertableOps
import treadle2.executable.DataType
import util.BinaryReader.DataType.INP

import scala.collection.immutable.Nil.:::
import scala.collection.mutable.{ArrayBuffer, ListBuffer}
import scala.reflect.ClassTag
//import botkop.{numsca => ns}
//import ns.Tensor

object Reshape {

  def pushBack[T: ClassTag](original: Array[T], elem: T): Array[T] = {
    val array = new Array[T](original.length + 1)
    Array.copy(original, 0, array, 0, original.length)
    array(original.length) = elem
    array
  }

  def toBlocks(vector: Array[BigInt], blockCol: Int, blockSize: Int): Array[Array[Array[Array[BigInt]]]] = { // vector: Vector[Byte] ?


    //val npvec = DenseVector(vector.toArray)
    //var B = ArrayBuffer.empty[Int]
    var B: Array[Array[Array[Array[BigInt]]]] = Array.empty
    val elements_per_full_row = blockCol * blockSize * blockSize
    val block_row = vector.length / elements_per_full_row

    val remaining = vector.length % elements_per_full_row
    val last_row_exists = remaining > 0

    for (i <- 0 until block_row) {
      //val row = ArrayBuffer.empty[Int]
      var row: Array[Array[Array[BigInt]]] = Array.empty

      for (j <- 0 until blockCol) {
        val start = (i * blockCol + j) * blockSize * blockSize
        val end = start + blockSize * blockSize

        val block: Array[Array[BigInt]] = (0 until blockSize).map { r =>
          (0 until blockSize).map { c =>
            vector(start + r * blockSize + c).toBigInt
          }.toArray
        }.toArray
        row = pushBack(row, block)
      }
      B = pushBack(B, row)
    }

    if (last_row_exists) {
      val elements_per_block = remaining / blockCol
      val subheight = elements_per_block / blockSize
      var last_row: Array[Array[Array[BigInt]]] = Array.empty
      val base_index = block_row * elements_per_full_row
      for (j <- 0 until blockCol) {
        val start = base_index + j * elements_per_block
        val end = start + elements_per_block
        //val block = vector.slice(start, end)
        var block_flat = Array.empty[BigInt]
        for (k <- start until math.min(end, vector.length)) {
          block_flat = pushBack(block_flat, vector(k))
        }
        print("ok\n")
        while (block_flat.length < subheight * blockSize) {
          block_flat = pushBack(block_flat, 0)
        }
        print("ok\n")
        val block: Array[Array[BigInt]] = Array.tabulate(subheight, blockSize)((r, c) =>
          block_flat(r * blockSize + c).toBigInt
        )
        last_row = pushBack(last_row, block)
        print("ok\n")
      }
      B = pushBack(B, last_row)
    }
    print("toBlocks done !\n")
    B
  }


  def unsplit(list_blocks: Array[Array[Array[Array[BigInt]]]], block_size: Int, matrix_height: Int, matrix_width: Int): Array[Array[BigInt]] = {
    val reconstructed: Array[Array[BigInt]] = Array.fill(matrix_height, matrix_width)(0) //.map(_.toByte)
    //val reconstructed: Array[Array[Byte]] = Array.ofDim[Byte](matrixHeight, matrixWidth)
    for (i <- 0 until matrix_height) {
      for (j <- 0 until matrix_width) {
        val deltaHeight = i / block_size
        val deltaWidth = j / block_size

        val r = i % block_size
        val t = j % block_size

        if (deltaHeight < list_blocks.size && deltaWidth < list_blocks(deltaHeight).size) {
          val block = list_blocks(deltaHeight)(deltaWidth)
          if (r < block.size && t < block(r).size) {
            reconstructed(i)(j) = block(r)(t)
          }
        }
      }
    }
    print("unsplit done !\n")
    reconstructed
  }


  def mat_to_tensor(res: Array[Array[BigInt]], batch_size: Int, output_channels: Int, output_height: Int, output_width: Int): Array[Array[Array[Array[BigInt]]]] = {
    val tensor: Array[Array[Array[Array[BigInt]]]] = Array.fill(batch_size, output_channels, output_height, output_width)(BigInt(0))
    var idx = 0
    for (h <- res(0).indices) {
      for (w <- res.indices) {
        val b = idx / (output_channels * output_height * output_width)
        var remainder = idx % (output_channels * output_height * output_width)
        val c = remainder / (output_height * output_width)
        remainder = remainder % (output_height * output_width)
        val y = remainder / output_width
        val x = remainder % output_width

        if (b < batch_size && c < output_channels && y < output_height && x < output_width) {
          tensor(b)(c)(y)(x) = res(w)(h)
        }
        idx = idx+1
      }
    }
    print("mat_to_tensor done !\n")
    tensor
  }


  def im2row(X: Array[Array[Array[Array[BigInt]]]], kernel_size: (Int, Int), stride: Int): Array[Array[BigInt]] = {
    val batch_size = X.size
    val input_channels = X(0).size
    val input_height = X(0)(0).size
    val input_width = X(0)(0)(0).size
    val kernel_height = kernel_size._1
    val kernel_width = kernel_size._2

    val output_height = (input_height - kernel_height) / stride + 1
    val output_width = (input_width - kernel_width) / stride + 1

    val rows = batch_size * output_height * output_width
    val cols = input_channels * kernel_height * kernel_width
    val result: Array[Array[BigInt]] = Array.fill(rows, cols)(BigInt(0))

    var row_idx = 0
    for (b <- 0 until batch_size) {
      for (i <- 0 to (input_height- kernel_height) by stride) {
        for (j <- 0 to (input_width - kernel_width) by stride) {
          var col_idx = 0
          for (c <- 0 until input_channels) {
            for (ki <- 0 until kernel_height) {
              for (kj <- 0 until kernel_width) {
                result(row_idx)(col_idx) = X(b)(c)(i + ki)(j+ kj)
                col_idx +=1
              }
            }
          }
          row_idx += 1
        }
      }
    }
    print("im2row done !\n")
    result
  }



  def matrix_padding(matrix: Array[Array[BigInt]], block_size: Int = 16, isWeight: Boolean = false, isSquare: Boolean = true): Array[Array[BigInt]] = {
    val n_row = matrix.length
    val n_col = matrix(0).length

    val target_rows = {
      if (isWeight || isSquare) {
        ((n_row - 1) / block_size + 1) * block_size
      }
      else {
        n_row
      }
    }
    val target_cols = ((n_col - 1) / block_size + 1) * block_size

    val padded_matrix: Array[Array[BigInt]] = Array.fill(target_rows, target_cols)(BigInt(0))

    for (i <- 0 until n_row) {
      for (j <- 0 until n_col) {
        padded_matrix(i)(j) = matrix(i)(j)
      }
    }
    print("matrix_padding done !\n")
    padded_matrix
  }


  def matrix_splitting(matrix: Array[Array[BigInt]], block_size: Int = 16, isWeight: Boolean = false, isSquare: Boolean = true): (Array[Array[Array[BigInt]]], Int) = {
    val n_row = matrix.size
    val n_col = matrix(0).size

//    if (n_col % block_size != 0) {
//      throw new
//    }

    val blocks_col = n_col / block_size
    var blocks: Array[Array[Array[BigInt]]] = Array.empty

    if (isWeight || isSquare) {
//      if (n_row % block_size != 0) {
//        throw new
//      }
      val blocks_row = n_row / block_size
      for (i <- 0 until blocks_row) {
        for (j <- 0 until blocks_col) {
          val block: Array[Array[BigInt]] = Array.fill(block_size, block_size)(0.toBigInt)
          for (r <- 0 until block_size) {
            for (c <- 0 until block_size) {
              block(r)(c) = matrix(i * block_size + r)(j * block_size + c)
            }
          }
          blocks = pushBack(blocks, block)
        }
      }
    }
    else {
      val blocks_row = (n_row + block_size - 1) / block_size
      for (i <- 0 until blocks_row) {
        for (j <- 0 until blocks_col) {
          val row_start = i * block_size
          val row_end = math.min((i + 1) * block_size, n_row)

          val block: Array[Array[BigInt]] = Array.fill(row_end - row_start, block_size)(0.toBigInt)
          for (r <- 0 until row_end - row_start) {
            for (c <- 0 until block_size) {
              block(r)(c) = matrix(row_start + r)(j * block_size + c)
            }
          }
          blocks = pushBack(blocks, block)
        }
      }
    }
    print("matrix_splitting done !\n")
    (blocks, blocks_col)
  }


  def reshape(vector: Array[BigInt], block_col: Int, block_size: Int, out_matrix_height: Int, out_matrix_width: Int, batch_size: Int,
              out_tensor_channel: Int, out_tensor_height: Int, out_tensor_width: Int, kernel_size: (Int, Int), stride: Int, isSquare: Boolean): Array[BigInt] = {

    // Vector -> Blocks
    val list_blocks = toBlocks(vector, block_col, block_size)
    // Blocks -> Matrix (unpad)
    val previous_matrix = unsplit(list_blocks, block_size, out_matrix_height, out_matrix_width)
    // Matrix -> Tensor
    val tensor = mat_to_tensor(previous_matrix, batch_size, out_tensor_channel, out_tensor_height, out_tensor_width)
    // Tensor -> New Matrix (unpad)
    val new_matrix = im2row(tensor, kernel_size, stride)
    // New Matrix -> Padded Matrix
    val padded_matrix = matrix_padding(new_matrix, block_size, false, isSquare)
    // Padded Matrix -> Blocks
    val (blocks, _) = matrix_splitting(padded_matrix, block_size, false, isSquare)
    // Blocks -> Vector (flatten blocks)
    val reshapedVector: Array[BigInt] = for {
      block <- blocks
      row   <- block
      value <- row
    } yield value
    print("reshaping done !\n")
    reshapedVector
  }

  def vector_to_map(vector: Array[BigInt], baseAddress: String): Map[BigInt, Array[BigInt]] = {
    val baseAddrBigInt = BigInt(baseAddress, 16) // Value of base address in BigInt
    val map = {
      for {
        (d, i) <- vector.grouped(INP.nbValues).toArray.zipWithIndex
      } yield {
        println(d.mkString("Array(", ", ", ")"))
        (BigInt(i) + baseAddrBigInt) -> d
      }
    }.toMap
    map
  }
}

