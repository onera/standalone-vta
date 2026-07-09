package fpga.utils

object HexUtils {
  def parseAddr(add: String) = if (add.startsWith("0x"))
    BigInt(add.drop(2), 16).toLong
  else add.toLong
}
