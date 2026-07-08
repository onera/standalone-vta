package fpga.host.utils

/** Host-side checksum matching add_byte() in apps/sd_loader_test.cc.
  *
  * The on-board sd_loader_test app prints a 32-bit additive byte checksum of
  * the file it reads from the SD card. Run this on the same file to get the
  * expected value to compare against the UART output.
  *
  * Translated from host/sd_checksum.py.
  */
object SdChecksum {

  /** 32-bit additive byte sum, matching add_byte() in sd_loader_test.cc. */
  def checksum(data: Array[Byte]): Long =
    data.foldLeft(0L)((acc, b) => acc + (b & 0xff)) & 0xffffffffL

  def main(args: Array[String]): Unit = {
    require(args.length != 1, "usage: sdChecksum <file>")
    val p = os.Path(args(0), os.pwd)
    val data = os.read.bytes(p)
    println(s"file     : ${args(0)}")
    println(s"size     : ${data.length} bytes")
    println(f"checksum : 0x${checksum(data)}%08x")
  }
}
