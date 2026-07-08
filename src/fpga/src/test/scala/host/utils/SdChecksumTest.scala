package fpga.host.utils

import org.scalatest.flatspec.AnyFlatSpec
import org.scalatest.matchers.should.Matchers

class SdChecksumTest extends AnyFlatSpec with Matchers {

  "checksum" should "sum bytes as unsigned and return a 32-bit value" in {
    // -1.toByte = 0xFF unsigned = 255; total = 1+2+3+255 = 261
    SdChecksum.checksum(Array[Byte](1, 2, 3, -1)) shouldBe (1L + 2L + 3L + 255L)
  }

  it should "return 0 for an empty array" in {
    SdChecksum.checksum(Array.empty[Byte]) shouldBe 0L
  }

  it should "wrap at 32 bits" in {
    // 256 bytes of value 0xFF: sum = 256 * 255 = 65280 (fits in 32 bits here)
    val data = Array.fill(256)(0xff.toByte)
    val expected = (256L * 255L) & 0xffffffffL
    SdChecksum.checksum(data) shouldBe expected
  }
}
