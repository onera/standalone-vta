package fpga.synthesis

import org.scalatest.flatspec.AnyFlatSpec
import org.scalatest.matchers.should.Matchers

class CompareOutTest extends AnyFlatSpec with Matchers {

  /** Build a minimal fixture tree in a temp dir:
    * compilerOut/memory_addresses<L>.csv with an OUT row at `base`
    * goldenDir/output<L>.bin = the expected bytes and a writes.log covering
    * layer index 0.
    */
  private def fixture(
    layer: String,
    base: Long,
    golden: Array[Byte],
    writes: Seq[(Long, Long, Int)] // (addr, data64, strb8)
  ): (os.Path, os.Path, os.Path) = {
    val root = os.temp.dir()
    val comp = root / "compiler_output"; os.makeDir.all(comp)
    val gold = root / "simulators_output"; os.makeDir.all(gold)
    os.write(
      comp / s"memory_addresses$layer.csv",
      s"OUT,${base.toHexString},0\n"
    )
    os.write(gold / s"output$layer.bin", golden)
    val log = root / "writes.log"
    os.write(
      log,
      writes
        .map { case (a, d, s) =>
          f"${a.toHexString} ${d.toHexString} ${s.toHexString} 0"
        }
        .mkString("\n") + "\n"
    )
    (log, comp, gold)
  }

  "CompareOut" should "return 0 when every golden byte matches the strobed writes" in {
    // golden = 2 bytes {0xAB, 0xCD} at base 0x100, one beat writes both (strb=0x03).
    val (log, comp, gold) =
      fixture(
        "L0",
        0x100,
        Array(0xab.toByte, 0xcd.toByte),
        Seq((0x100L, 0xcdabL, 0x03))
      )
    CompareOut.run(
      Array(
        "--writes",
        log.toString,
        "--layers",
        "L0",
        "--compiler-out",
        comp.toString,
        "--golden-dir",
        gold.toString
      )
    ) shouldBe 0
  }

  it should "return 1 when a strobe leaves a golden byte unwritten" in {
    // strb=0x01 writes only byte 0; byte 1 (0xCD) is never written -> mismatch.
    val (log, comp, gold) =
      fixture(
        "L0",
        0x100,
        Array(0xab.toByte, 0xcd.toByte),
        Seq((0x100L, 0xcdabL, 0x01))
      )
    CompareOut.run(
      Array(
        "--writes",
        log.toString,
        "--layers",
        "L0",
        "--compiler-out",
        comp.toString,
        "--golden-dir",
        gold.toString
      )
    ) shouldBe 1
  }

  it should "return 1 when a written byte differs from the golden" in {
    val (log, comp, gold) =
      fixture(
        "L0",
        0x100,
        Array(0xab.toByte, 0xcd.toByte),
        Seq((0x100L, 0xceabL, 0x03))
      ) // byte1 = 0xCE != 0xCD
    CompareOut.run(
      Array(
        "--writes",
        log.toString,
        "--layers",
        "L0",
        "--compiler-out",
        comp.toString,
        "--golden-dir",
        gold.toString
      )
    ) shouldBe 1
  }

  it should "handle a 64-bit data beat with the top bit set (unsigned parse)" in {
    // golden = 8 bytes 0x11..0x88; one beat writes all 8 (strb=0xFF).
    // data little-endian byte0=0x11 .. byte7=0x88 -> 0x8877665544332211 (MSB set).
    val golden =
      Array(0x11, 0x22, 0x33, 0x44, 0x55, 0x66, 0x77, 0x88).map(_.toByte)
    val (log, comp, gold) =
      fixture("L0", 0x100, golden, Seq((0x100L, 0x8877665544332211L, 0xff)))
    CompareOut.run(
      Array(
        "--writes",
        log.toString,
        "--layers",
        "L0",
        "--compiler-out",
        comp.toString,
        "--golden-dir",
        gold.toString
      )
    ) shouldBe 0
  }

  it should "bucket writes by layer index using the relocation stride" in {
    val root = os.temp.dir()
    val comp = root / "compiler_output"; os.makeDir.all(comp)
    val gold = root / "simulators_output"; os.makeDir.all(gold)
    val stride = 0x200000L
    // Two layers, each 2 bytes at OUT base 0x100 in their own coordinate space.
    os.write(comp / "memory_addressesL0.csv", "OUT,100,0\n")
    os.write(comp / "memory_addressesL1.csv", "OUT,100,0\n")
    os.write(gold / "outputL0.bin", Array(0xa1, 0xa2).map(_.toByte))
    os.write(gold / "outputL1.bin", Array(0xb1, 0xb2).map(_.toByte))
    // L0 beat at abs 0x100 (idx 0); L1 beat at abs stride+0x100 (idx 1).
    os.write(
      root / "writes.log",
      Seq(
        f"${0x100L.toHexString} ${0xa2a1L.toHexString} 3 0",
        f"${(stride + 0x100L).toHexString} ${0xb2b1L.toHexString} 3 0"
      ).mkString("\n") + "\n"
    )
    CompareOut.run(
      Array(
        "--writes",
        (root / "writes.log").toString,
        "--layers",
        "L0,L1",
        "--compiler-out",
        comp.toString,
        "--golden-dir",
        gold.toString
      )
    ) shouldBe 0
  }

  it should "skip a layer whose golden is missing and still pass" in {
    // L0 matches; L9 has no output bin -> SKIP (not a failure, no crash reading its csv).
    val (log, comp, gold) =
      fixture(
        "L0",
        0x100,
        Array(0xab.toByte, 0xcd.toByte),
        Seq((0x100L, 0xcdabL, 0x03))
      )
    CompareOut.run(
      Array(
        "--writes",
        log.toString,
        "--layers",
        "L0,L9",
        "--compiler-out",
        comp.toString,
        "--golden-dir",
        gold.toString
      )
    ) shouldBe 0
  }
}
