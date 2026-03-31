package vta.util
import chisel3.simulator.HasSimulator
import svsim.CommonCompilationSettings
import svsim.CommonSettingsModifications

object SimulationUtils {

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
}
