package vta.util

import chisel3._
import chisel3.simulator.scalatest.ChiselSim
import org.scalatest.flatspec.AnyFlatSpec
import vta.DefaultPynqConfig
import vta.util.config._
import vta.util.SimulationUtils.debugLayerDisabled
import chisel3.simulator.ChiselOptionsModifications
import chisel3.simulator.FirtoolOptionsModifications
import chisel3.simulator.HasSimulator
import chisel3.simulator.scalatest.HasCliOptions
import chisel3.simulator.scalatest.HasCliOptions.CliOption
import chisel3.testing.HasTestingDirectory
import svsim.BackendSettingsModifications
import svsim.CommonSettingsModifications
import chisel3.simulator.Settings
import svsim.CommonCompilationSettings.VerilogPreprocessorDefine
import scala.runtime.BoxedUnit

trait EmitFst {
  this: HasCliOptions =>
  addOption(
    CliOption.flag(
      name = "emitFst",
      help =
        "compile with FST waveform support and start dumping waves at time zero",
      updateCommonSettings = (options) => {
        options.copy(
          verilogPreprocessorDefines =
            options.verilogPreprocessorDefines :+ VerilogPreprocessorDefine(
              svsim.Backend.HarnessCompilationFlags.enableFstTracingSupport
            ),
          simulationSettings = options.simulationSettings.copy(
            enableWavesAtTimeZero = true
          )
        )
      },
      updateBackendSettings = (options) =>
        options match {
          case options: svsim.verilator.Backend.CompilationSettings =>
            options.withTraceStyle(
              Some(
                svsim.verilator.Backend.CompilationSettings.TraceStyle(
                  svsim.verilator.Backend.CompilationSettings.TraceKind.Fst(),
                  traceUnderscore = true,
                  maxArraySize = Some(1024),
                  maxWidth = Some(1024),
                  traceDepth = Some(1024)
                )
              )
            )
          case options: svsim.vcs.Backend.CompilationSettings =>
            throw new IllegalArgumentException("not implemented for vcs")
        }
    )
  )
}
trait DebugLayerCliOption {
  this: HasCliOptions =>
  addOption(
    CliOption.flag(
      "debug",
      "enables debug"
    )
  )
}

/** Enables `$readmemh` memory initialization for tests that load simulation
  * memories from external `.mem` files. Mix in after [[AnyFlatSpecSim]] so the
  * override wins; it layers mem-init on top of the CLI options rather than
  * replacing them.
  */
trait EnableMemInit extends HasCliOptions { this: org.scalatest.TestSuite =>
  override implicit def commonSettingsModifications
      : svsim.CommonSettingsModifications =
    (s: svsim.CommonCompilationSettings) =>
      SimulationUtils.EnableMemInitVerilog(super.commonSettingsModifications(s))
}

trait AnyFlatSpecSim
    extends AnyFlatSpec
    with ChiselSim
    with DebugLayerCliOption
    with EmitFst {

  implicit val p: Parameters = new DefaultPynqConfig

  def customSettings[A <: Module] = (for {
    _ <- getOption[BoxedUnit]("debug")
  } yield {
    Settings.default[A]
  }).getOrElse(debugLayerDisabled)

  override def simulate[T <: Module](
      module: => T,
      chiselOpts: Array[String] = Array.empty,
      firtoolOpts: Array[String] = Array.empty,
      settings: Settings[T] = customSettings[T],
      additionalResetCycles: Int = 0,
      subdirectory: Option[String] = None
  )(stimulus: T => Unit)(implicit
      hasSimulator: HasSimulator,
      testingDirectory: HasTestingDirectory,
      chiselOptsModifications: ChiselOptionsModifications,
      firtoolOptsModifications: FirtoolOptionsModifications,
      commonSettingsModifications: CommonSettingsModifications,
      backendSettingsModifications: BackendSettingsModifications
  ): Unit = super.simulate(
    module,
    chiselOpts,
    firtoolOpts,
    settings,
    additionalResetCycles,
    subdirectory
  )(stimulus)(
    hasSimulator,
    testingDirectory,
    chiselOptsModifications,
    firtoolOptsModifications,
    commonSettingsModifications,
    backendSettingsModifications
  )
}
class GenericSim[T <: Module, C <: Parameters](
    tag: String,
    dutFactory: (Parameters) => T,
    testerFactory: (T) => Unit
) extends AnyFlatSpecSim {

  behavior of tag
  it should "not have expect violations" in {
    simulate(dutFactory(p))(testerFactory)
  }
}
