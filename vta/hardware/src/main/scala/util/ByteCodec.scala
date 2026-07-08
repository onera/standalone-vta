package vta.util

object ByteCodec {

  def bytesToHexWord(
      bytes: Array[Byte],
      bytesPerWord: Int = 8,
      littleEndian: Boolean = false
  ): String = {
    require(
      bytesPerWord > 0,
      s"bytesPerWord must be positive, got $bytesPerWord"
    )
    val pad = Array.fill[Byte](bytesPerWord - bytes.length)(0)
    val ordered =
      if (littleEndian) pad ++ bytes.reverse
      else pad ++ bytes
    ordered.iterator.map(b => f"${b & 0xff}%02x").mkString
  }

  /** Read up to `n` bytes from `in`, returning exactly that many unless EOF is
    * reached first. An empty array signals EOF. Java 1.8 compatible replacement
    * for `InputStream.readNBytes(int)` (added in Java 9).
    */
  def readUpToNBytes(in: java.io.InputStream, n: Int): Array[Byte] = {
    val buf = new Array[Byte](n)
    var off = 0
    var r = 0
    while (off < n && { r = in.read(buf, off, n - off); r } != -1) off += r
    if (off == n) buf
    else java.util.Arrays.copyOf(buf, off)
  }

  /** Convert a byte array into one hex string per `bytesPerWord`-byte group.
    *
    * Each output string has exactly `2 * bytesPerWord` characters and is
    * written MSB-first so it reads as a single unsigned integer for
    * `$readmemh`.
    */
  def bin2hex(
      bytes: Array[Byte],
      bytesPerWord: Int = 8,
      littleEndian: Boolean = false
  ): Array[String] = {
    require(
      bytesPerWord > 0,
      s"bytesPerWord must be positive, got $bytesPerWord"
    )
    bytes
      .grouped(bytesPerWord)
      .map { g =>
        val pad = Array.fill[Byte](bytesPerWord - g.length)(0)
        val ordered =
          if (littleEndian) pad ++ g.reverse
          else pad ++ g
        ordered.iterator.map(b => f"${b & 0xff}%02x").mkString
      }
      .toArray
  }
}
