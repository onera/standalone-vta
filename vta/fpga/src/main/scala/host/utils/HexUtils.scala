package fpga.utils

object HexUtils {
  def parseAddr(add: String) = BigInt(add, 16).toLong
}
