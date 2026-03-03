package vta.cli

import org.scalatest.flatspec.AnyFlatSpec
import org.scalatest.matchers.should.Matchers
import cli.VTAShellSimulator

class VTAShellSimulatorTest extends AnyFlatSpec with Matchers {

  behavior of "VTAShellSimulator"

  it should "run for the resource test" in {
    VTAShellSimulator.main(
      Array("src/test/resources/examples_shell/dram_state.json")
    )
  }
}
