package fpga.synthesis

import org.scalatest.flatspec.AnyFlatSpec
import org.scalatest.matchers.should.Matchers
import fpga.host.models.GoldenSupport

class EmitXilinxTest extends AnyFlatSpec with Matchers {
  "emitXilinx" should "write package_ip.tcl and return the matching VLNV" in {
    val out = GoldenSupport.sandbox("emit-xilinx")
    val vlnv = vta.XilinxEmit.emitXilinx(out)
    vlnv shouldBe "onera:user:VTA:0.2.0"
    val tcl = os.read(out / "package_ip.tcl")
    tcl should include("""set ip_vendor  "onera"""")
    tcl should include("""set ip_name    "VTA"""")
  }
}
