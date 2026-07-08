package fpga.host

import org.scalatest.flatspec.AnyFlatSpec
import org.scalatest.matchers.should.Matchers
import fpga.host.models.GoldenSupport

class GenInitDramTestGemmTest extends AnyFlatSpec with Matchers {
  private val gemm =
    os.Path(
      java.nio.file.Paths
        .get(getClass.getClassLoader.getResource("host-golden").toURI)
    ) / "gemm-test"

  "synthesis mode" should "reproduce the golden init_dram.h" in {
    val out = GoldenSupport.sandbox("gen-init-dram") / "init_dram.h"
    GenInitDramTestGemm.generate(out.toString)
    os.read(out) shouldBe os.read(gemm / "init_dram.h")
  }

  "formatInsnArray" should "emit a 4-word VTAInsn row" in {
    GenInitDramTestGemm.formatInsnArray("x", Array(3L, 0L, 0L, 0L)) shouldBe
      "static const VTAInsn x[] = {\n    {{0x00000003u, 0x00000000u, 0x00000000u, 0x00000000u}}\n};\n"
  }

  "formatCArray" should "right-justify to the max width" in {
    // maxLen = max(len("-8"), len("1"), len("100")) = max(2, 1, 3) = 3
    // Each padded to 3: " -8", "  1", "100"
    // Row with 4-space prefix: "     -8,   1, 100"
    val expected = "static const std::int32_t v[] = {\n     -8,   1, 100\n};\n"
    GenInitDramTestGemm.formatCArray(
      "v",
      Array(-8, 1, 100),
      "int32",
      3
    ) shouldBe expected
  }
}
