package util

import scala.math.BigDecimal.int2bigDecimal

object Filter {
  // LeNet-5 filter parameters
  // uop = 0, dst_in = 2, dst_out = 56, loop_in = loop_out = 14 for layer1
  // uop = 0, dst_in = 2, dst_out = 20, loop_in = 5, loop_out = 5 for layer2

  /**
   * A function that filters out the 'useless' data in the simulator output after average pooling for LeNet-5
   * @param scratchpad output of simulator
   * @param uop initial index in scratchpad
   * @param loop_in number of inner loops
   * @param loop_out number of outer loops
   * @param dst_in parameter for inner loop
   * @param dst_out parameter for outer loop
   * @return filtered scratchpad
   */
  def filter(scratchpad: Map[BigInt, Array[BigInt]], uop: Int, loop_in: Int, loop_out: Int, dst_in: Int, dst_out: Int): Map[BigInt, Array[BigInt]] = { // should have OUT scratchpad of size 208 after filtering
    // Filtering out 'useless' data post-average pooling
    var filteredOut: Map[BigInt, Array[BigInt]] = Map.empty
    var i: BigInt = 0
    for (i0 <- 0 until loop_in) {
      for (i1 <- 0 until loop_out) {
        filteredOut += (i -> scratchpad(BigInt(i1 * dst_in + i0 * dst_out + uop)))
        i += BigInt(1)
      }
    }
    // Adding padding to the filtered scratchpad
    val divider = filteredOut.size.toDouble / 16
    if (divider != 0) {
      for (k <- filteredOut.size until math.ceil(divider).toInt * 16) {
        filteredOut += (BigInt(k) -> Array(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0).map(_.toBigInt))
      }
    }
    filteredOut
  }
}