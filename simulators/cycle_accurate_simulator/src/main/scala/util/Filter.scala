package util

import scala.math.BigDecimal.int2bigDecimal

object Filter {
  // LeNet-5 filter parameters
  // uop = 0, dst_in = 2, dst_out = 56, loop_in = loop_out = 14 for layer1

  def filter(scratchpad: Map[BigInt, Array[BigInt]], uop: Int, loop_in: Int, loop_out: Int, dst_in: Int, dst_out: Int): Map[BigInt, Array[BigInt]] = { // should have OUT scratchpad of size 208 after filtering
    val filteredOut: Map[BigInt, Array[BigInt]] = Map.empty
    var i = 0
    for (i0 <- 0 until loop_in) {
      for (i1 <- 0 until loop_out) {
        val dst_idx = i0 * dst_in + i1 * dst_out + uop
        scratchpad(dst_idx) -> filteredOut(i)
        i += 1
      }
    }
    val divider = filteredOut.size.toDouble / 16
    if (divider != 0) {
      for (k <- filteredOut.size until filteredOut.size + math.ceil(divider).toInt) {
        Array(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0).map(_.toBigInt) -> filteredOut(k)
      }
    }
    print(filteredOut.size) //to test with outL1_sram.bin
    filteredOut
  }
}