package fpga.host.models

import vta.models.CompilerOutputModel.DependencyInfo

/** Data models for the generated baremetal artifacts.
  *
  * Each case class carries exactly the inputs one emitted file needs; the
  * rendering lives in the matching `Emittable`/`Exportable` instance in
  * [[fpga.host.exporters]]. Keeping the model here (pure data) and the
  * rendering there keeps `models` free of `os.write` side effects.
  */

/** `nn_ddr_map.h` - the `nn_layers[]` LayerDesc table. */
final case class DdrMap(layers: Seq[Model.LayerInfo], ddrBase: Long)

/** `nn_exec_plan.h` - the ordered `nn_exec_steps[]` table.
  *
  * `suffixToIdx` / `cpuOut` / `ctParams` are pre-resolved by the caller (the
  * CLI pipeline) and passed through; when `None` they are recomputed from
  * `layers` exactly as the standalone emitter did.
  */
final case class ExecPlan(
  dep: DependencyInfo,
  layers: Seq[Model.LayerInfo],
  ddrBase: Long,
  compDir: String,
  blockSize: Int = 16,
  suffixToIdx: Option[Map[String, Int]] = None,
  cpuOut: Option[Map[String, Long]] = None,
  logOutWidth: Int = 3,
  ctParams: Option[Map[String, CtParams]] = None
)

/** An XSDB `dow` loader script (`load_nn.tcl` / `load_nn_static.tcl`).
  *
  * `scriptName` is the destination file's own name, embedded in the usage
  * banner; the rendering is otherwise path-independent so it is supplied here
  * rather than read back from the export path.
  *
  * `refDir` is the reference_output dir holding input_nn.bin; None means no
  * reference is available and the raw-input section is omitted.
  */
final case class LoadTcl(
  layers: Seq[Model.LayerInfo],
  ddrBase: Long,
  compDir: String,
  scriptName: String,
  includeInput: Boolean,
  extraBlobs: Seq[ExtraBlob] = Nil,
  refDir: Option[String] = None
)

/** `load_input.tcl` - loads only `input_nn.bin` into the scratch region.
  *
  * `refDir` is the reference_output dir holding input_nn.bin; None means no
  * reference is available and the raw-input section is omitted.
  */
final case class InputTcl(
  layers: Seq[Model.LayerInfo],
  ddrBase: Long,
  compDir: String,
  refDir: Option[String] = None
)

/** `nn_bin_data.S` - one `.incbin` section per static buffer per layer. */
final case class AsmIncbin(
  layers: Seq[Model.LayerInfo],
  emitCheck: Boolean = false,
  extraBlobs: Seq[ExtraBlob] = Nil
)

/** `nn_vta_sections.ld` - placement of each `.incbin` section at its address.
  */
final case class LinkerFragment(
  layers: Seq[Model.LayerInfo],
  ddrBase: Long,
  emitCheck: Boolean = false,
  extraBlobs: Seq[ExtraBlob] = Nil
)

/** `nn_sd_manifest.h` plus, when `stageFiles` is set, the staged `.bin` set
  * under `sdCardDir`.
  *
  * Unlike the header-only artifacts this can also copy the referenced binaries,
  * so its `Exportable` instance is bespoke (it does more than write `path`).
  * `stageFiles = false` emits the header alone - the manifest only reads the
  * binaries' sizes, never their contents.
  *
  * `refDir` is the reference_output dir holding input_nn.bin; None means no
  * reference is available and the raw-input section is omitted.
  */
final case class SdManifest(
  layers: Seq[Model.LayerInfo],
  ddrBase: Long,
  compDir: String,
  sdCardDir: String,
  sdDir: String = "",
  emitRefs: Boolean = false,
  extraBlobs: Seq[ExtraBlob] = Nil,
  stageFiles: Boolean = true,
  refDir: Option[String] = None
)

/** `nn_debug_map.h` - the per-layer `DebugLayerDesc nn_debug[]` table. */
final case class DebugMap(layers: Seq[Model.LayerInfo])

/** `nn_cpu_debug_map.h` - the per-CPU-op `DebugCpuStep nn_cpu_debug[]` table.
  *
  * `refDir` is the reference_output dir holding input_nn.bin; None means no
  * reference is available and the raw-input section is omitted.
  */
final case class CpuDebugMap(
  dep: DependencyInfo,
  layers: Seq[Model.LayerInfo],
  cfg: HwConfig.ConfigParams,
  suffixToIdx: Map[String, Int],
  ddrBase: Long,
  compDir: String,
  refDir: Option[String] = None
)
