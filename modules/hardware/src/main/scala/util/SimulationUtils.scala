package vta.util
import chisel3.layers.Verification
import chisel3.simulator.{HasSimulator, LayerControl, Settings}
import svsim.{CommonCompilationSettings, CommonSettingsModifications}

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
      // Append to v1 so this composes with other settings modifications
      // (e.g. CLI-driven FST tracing) rather than overwriting them.
      v1.copy(verilogPreprocessorDefines =
        v1.verilogPreprocessorDefines.appended(
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
          Verification.Cover,
          Verification
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
