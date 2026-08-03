package fpga.host

import org.scalatest.flatspec.AnyFlatSpec
import org.scalatest.matchers.should.Matchers
import fpga.host.models.GoldenSupport
import fpga.host.parsers.ConfigParser

/** load_input.tcl must `dow` the reference dir's input_nn.bin, never the
  * compiler dir's. The compiler dir has not held that file since the reference
  * was split out, so a codegen that still looks there emits the "not found"
  * error branch instead of a dow line.
  */
class InputTclRefDirTest extends AnyFlatSpec with Matchers {
  for (name <- GoldenSupport.cases) {
    s"load_input.tcl [$name]" should "dow input_nn.bin from the reference dir" in {
      val c = GoldenSupport.loadCase(name)
      val outDir = GoldenSupport.sandbox("input-tcl-refdir", name)
      val refDir = GoldenSupport.sandbox("input-tcl-refsrc", name)
      os.write.over(refDir / "input_nn.bin", Array.fill[Byte](784)(7))

      GenNnBaremetal.generate(
        compDir = c.comp.toString,
        outdir = outDir.toString,
        ddrBase = c.ddrBase,
        cfg = ConfigParser.load(c.cfg.toString),
        refDir = Some(refDir.toString)
      )

      val tcl = os.read(outDir / "load_input.tcl")
      tcl should include(s"dow -data {${refDir / "input_nn.bin"}}")
      tcl should not include ("input_nn.bin not found")
    }
  }
}
