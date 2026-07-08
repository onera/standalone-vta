package fpga.host.utils

import org.scalatest.flatspec.AnyFlatSpec
import org.scalatest.matchers.should.Matchers
import fpga.host.utils.PyFmt

class PyFmtTest extends AnyFlatSpec with Matchers {
  "PyFmt.float" should "match CPython repr on common quant values" in {
    PyFmt.float(0.0) shouldBe "0.0"
    PyFmt.float(1.0) shouldBe "1.0"
    PyFmt.float(3.0) shouldBe "3.0"
    PyFmt.float(0.5) shouldBe "0.5"
    PyFmt.float(2.5) shouldBe "2.5"
    PyFmt.float(0.0078125) shouldBe "0.0078125"
    PyFmt.float(0.00390625) shouldBe "0.00390625"
    PyFmt.float(0.0001) shouldBe "0.0001"
    PyFmt.float(0.00001) shouldBe "1e-05"
    PyFmt.float(-0.25) shouldBe "-0.25"
    PyFmt.float(123456.0) shouldBe "123456.0"
    PyFmt.float(1e16) shouldBe "1e+16"
  }
}
