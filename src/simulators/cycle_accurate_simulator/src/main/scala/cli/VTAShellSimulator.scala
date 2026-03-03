package cli

import vta.test.VTAShellTest
import vta.parsers.DramJsonParser.parseJsonMemoryInitFile
import vta.parsers.DramJsonParser.parseMemorySections
import vta.util.MemoryInitializer.exportHexFiles
import vta.parsers.DramJsonParser.getMemoryConfigurations

// FIXME: simple app, needs refinement
object VTAShellSimulator extends App with VTAShellTest {

  require(args.size == 1)
  val dramInit = parseJsonMemoryInitFile(args.head)

  exportHexFiles(parseMemorySections(dramInit), os.pwd / "generatedResources")

  runVtaTestWithInitializedMem(getMemoryConfigurations(args.head), 1000, true)
}
