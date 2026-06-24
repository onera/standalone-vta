package cli

import org.scalatest.flatspec.AnyFlatSpec
import org.scalatest.matchers.should.Matchers
import cli.VTAShellSimulator
import vta.tags.LongTests
import cli.VTAShellSimBinary

@LongTests
class VTAShellSimulatorTest extends AnyFlatSpec with Matchers {

  behavior of "VTAShellSimulator"

  // FIXME: use resources instead
  val basePath = for {
    millRoot <- sys.env.get("MILL_WORKSPACE_ROOT")
  } yield {
    millRoot + "/"
  }
  it should "run for the resource test" in {
    VTAShellSimulator.main(
      Array(
        s"${basePath.getOrElse("")}src/test/resources/examples_shell/dram_state.json"
      )
    )
  }

  it should "run for binary files" in {
    VTAShellSimBinary.main(
      Array(
        s"${basePath.getOrElse("")}src/test/resources/examples_compute/lenet5_conv1",
        ""
      )
    )
  }
}
