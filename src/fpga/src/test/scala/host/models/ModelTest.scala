package fpga.host.models

import org.scalatest.flatspec.AnyFlatSpec
import org.scalatest.matchers.should.Matchers
import fpga.host.models.Model

class ModelTest extends AnyFlatSpec with Matchers {
  "Model helpers" should "match the Python formatting/naming" in {
    Model.hex32(0x10L) shouldBe "0x00000010u"
    Model.hex32(0xabcdefL) shouldBe "0x00ABCDEFu"
    Model.safeCName("", 3) shouldBe "l3"
    Model.safeCName("_L1", 0) shouldBe "_L1"
    Model.safeCName("3a.b", 0) shouldBe "_3a_b"
    Model.staticLoadOrder shouldBe Seq("INSN", "UOP", "WGT", "ACC")
    Model.layerBinfile("/c", "ACC", "L1") shouldBe "/c/accumulatorL1_block.bin"
    Model.layerBinfile("/c", "WGT", "L1") shouldBe "/c/weightL1.bin"
  }
}
