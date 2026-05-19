package vta.util
import chisel3.simulator.HasSimulator
import svsim.CommonCompilationSettings
import svsim.CommonSettingsModifications
import chisel3.layer.LayerConfig
import chisel3.simulator.LayerControl
import vta.util.UserDefined.DebugLayer
import chisel3.simulator.Settings
import chisel3.layers.Verification

object SimulationUtils {

  /** Verilator simulator with FST waveDump enabled
    *
    * @return
    *   HasSimulator
    */
  def verilatorWithWaveDump: HasSimulator = HasSimulator.simulators
    .verilator(verilatorSettings =
      svsim.verilator.Backend.CompilationSettings.default.withTraceStyle(
        Some(
          svsim.verilator.Backend.CompilationSettings
            .TraceStyle(
              svsim.verilator.Backend.CompilationSettings.TraceKind.Fst(),
              traceUnderscore = true,
              maxArraySize = Some(1024),
              maxWidth = Some(1024),
              traceDepth = Some(1024)
            )
        )
      )
    )

  val compilationSettings = svsim.CommonCompilationSettings.default

  /** Compilation settings modification for enabling memory initialization from
    * file It defines the ENABLE_INITIAL_MEM_ pre processor macro that guard
    * $readmemh calls in system verilog
    */
  object EnableMemInitVerilog extends CommonSettingsModifications {

    override def apply(
        v1: CommonCompilationSettings
    ): CommonCompilationSettings = {
      v1.copy(
        verilogPreprocessorDefines =
          compilationSettings.verilogPreprocessorDefines.appended(
            CommonCompilationSettings
              .VerilogPreprocessorDefine("ENABLE_INITIAL_MEM_")
          )
      )
    }

  }

  /** Simulation settings that disable the DebugLayer by default
    */
  def debugLayerDisabled[A <: chisel3.Module] = {
    val default = Settings.default[A]
    Settings(
      verilogLayers = LayerControl
        .Enable(
          Verification.Assert,
          Verification.Assume,
          Verification.Cover
        ),
      assertVerboseCond = default.assertVerboseCond,
      printfCond = default.printfCond,
      stopCond = default.stopCond,
      plusArgs = default.plusArgs,
      enableWavesAtTimeZero = default.enableWavesAtTimeZero,
      randomization = default.randomization
    )
  }

}
