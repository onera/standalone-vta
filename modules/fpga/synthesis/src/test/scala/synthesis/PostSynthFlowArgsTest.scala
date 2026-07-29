package fpga.synthesis

import org.scalatest.flatspec.AnyFlatSpec
import org.scalatest.matchers.should.Matchers

/** The DUT-source contract of PostSynthFlow: either --shell-dir (OOC-synth it)
  * or --netlist (reuse a cached one) must be given.
  */
class PostSynthFlowArgsTest extends AnyFlatSpec with Matchers {
  private val common = Array(
    "--tb",
    "tb",
    "--comp-dir",
    "comp",
    "--golden-dir",
    "golden",
    "--out",
    os.temp.dir().toString,
    "--layers",
    "QLinearConv1"
  )

  "PostSynthFlow" should "reject a run with neither --shell-dir nor --netlist" in {
    PostSynthFlow.run(common) shouldBe 1
  }
}
