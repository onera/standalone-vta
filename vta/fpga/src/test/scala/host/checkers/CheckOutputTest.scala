package fpga.host

import org.scalatest.flatspec.AnyFlatSpec
import org.scalatest.matchers.should.Matchers
import fpga.host.checkers.CheckOutput

class CheckOutputTest extends AnyFlatSpec with Matchers {

  /** Build the block-tiled representation of an NCHW array (inverse of detile).
    * raw[(rb*Cb+cb)*B*B + rr*B + cc] = nchw[c*N + n]
    */
  private def tile(
    nchw: Array[Byte],
    C: Int,
    H: Int,
    W: Int,
    B: Int
  ): Array[Byte] = {
    val N = H * W
    val Cb = (C + B - 1) / B
    val rawSize = ((N + B - 1) / B) * Cb * B * B
    val raw = new Array[Byte](rawSize)
    for (n <- 0 until N) {
      val rb = n / B; val rr = n % B
      for (c <- 0 until C) {
        val cb = c / B; val cc = c % B
        raw((rb * Cb + cb) * B * B + rr * B + cc) = nchw(c * N + n)
      }
    }
    raw
  }

  "detile" should "round-trip a known NCHW layout (C=2,H=2,W=2,B=2)" in {
    val C = 2; val H = 2; val W = 2; val B = 2
    val N = H * W
    // NCHW: element at (c, n) = c*N+n cast to byte
    val nchw = Array.tabulate(C * N)(i => i.toByte)
    val raw = tile(nchw, C, H, W, B)
    CheckOutput.detile(raw, C, H, W, B).toList shouldBe nchw.toList
  }

  it should "round-trip with non-power-of-two C (C=3,H=2,W=2,B=2)" in {
    val C = 3; val H = 2; val W = 2; val B = 2
    val N = H * W
    val nchw = Array.tabulate(C * N)(i => (i * 7 + 3).toByte)
    val raw = tile(nchw, C, H, W, B)
    CheckOutput.detile(raw, C, H, W, B).toList shouldBe nchw.toList
  }

  "reportDiff" should "return true for identical arrays" in {
    val a = Array[Byte](1, 2, 3, 4)
    CheckOutput.reportDiff("test", a, a.clone()) shouldBe true
  }

  it should "return false for arrays that differ" in {
    val a = Array[Byte](1, 2, 3, 4)
    val b = Array[Byte](1, 2, 3, 5)
    CheckOutput.reportDiff("test", a, b) shouldBe false
  }

  it should "return false for arrays of different sizes" in {
    val a = Array[Byte](1, 2, 3)
    val b = Array[Byte](1, 2, 3, 4)
    CheckOutput.reportDiff("test", a, b) shouldBe false
  }
}
