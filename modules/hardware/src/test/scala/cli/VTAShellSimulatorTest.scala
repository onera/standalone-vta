package cli

import cli.{VTAShellSimBinary, VTAShellSimulator}
import org.scalatest.flatspec.AnyFlatSpec
import org.scalatest.matchers.should.Matchers
import vta.tags.LongTests
import vta.util.FileManager.getResourceAsFile

@LongTests
class VTAShellSimulatorTest extends AnyFlatSpec with Matchers {

  behavior of "VTAShellSimulator"

  val dramStateJson =
    getResourceAsFile("examples_shell/dram_state.json").get.getCanonicalPath()
  val lenet5ConvDir = getClass.getClassLoader
    .getResource("examples_compute/lenet5_conv1")
    .getPath()

  it should "run for the resource test" in {
    VTAShellSimulator.main(
      Array(
        dramStateJson
        // s"${basePath.getOrElse("")}src/test/resources/examples_shell/dram_state.json"
      )
    )
  }

  it should "run for binary files" in {
    VTAShellSimBinary.main(
      Array(
        lenet5ConvDir,
        // s"${basePath.getOrElse("")}src/test/resources/examples_compute/lenet5_conv1",
        ""
      )
    )
  }
}
