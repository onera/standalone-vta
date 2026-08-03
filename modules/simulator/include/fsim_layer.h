/*!
 * \file fsim_layer.h
 * \brief Shared scaffolding for the functional-simulator entry points.
 *
 * run_nn() (src/fsim_nn.cc) and run_single_layer() (src/fsim_single_layer.cc)
 * share the per-layer data structure, the compiler_output / simulators_output
 * path helpers, the load+allocate+copy of a layer's buffers, the TVM profiler
 * setup, the Verilator per-layer trace-file update, and the per-layer free.
 * Those pieces live here so the two entry points only keep their distinct
 * execution logic (NN chaining / CPU-op dispatch vs. single-layer single run).
 */

#ifndef FSIM_LAYER_H_
#define FSIM_LAYER_H_

#include "../include/simulator_header.h" // common types, CSV/binary helpers, TVM
#include "../include/vta_device_backend.h" // g_use_verilator, VerilatorRunConfig, VTAMem*

// All data specific to one layer: host-side buffers, the VTA-side (virtual
// DRAM) pointers, and the instruction stream's physical address.
struct LayerContext {
  int id;
  std::string suffix;

  // Buffers (Host side)
  std::vector<inp_dtype> inpA;
  std::vector<out_dtype> outC;
  std::vector<wgt_dtype> wgtB;
  std::vector<acc_dtype> accX, accY;
  std::vector<uop_t> uop_buffer;
  std::vector<instruction_t> insn_buffer;

  // Other buffer for execution
  std::vector<int8_t> res;  // Result
  std::vector<float> value; // Float values

  // Memory Pointers (VTA side)
  void *mem_inpA = nullptr;
  void *mem_wgtB = nullptr;
  void *mem_accX = nullptr;
  void *mem_accY = nullptr;
  void *mem_outC = nullptr;
  void *mem_uop = nullptr;
  void *mem_insn = nullptr;

  // Physical Addresses
  vta_phy_addr_t phy_add_insn;
};

// Runtime override of the simulator-output dir, populated from --output in
// main(). Empty means "use the compile-time VTA_SIMULATOR_OUTPUT default".
extern std::string g_sim_output_override;
extern std::string g_comp_dir_override;
// Runtime override of the reference dir, populated from --ref-dir in main().
// The reference dir holds input_nn.bin and reference.bin, which are written by
// reference_onnx.py, not by the compiler. Empty means "use the compile-time
// VTA_REFERENCE_OUTPUT default".
extern std::string g_ref_dir_override;

// Path helpers.
std::string compiler_output_path(const std::filesystem::path &cwd,
                                 const std::string &file);
std::string sim_output_path(const std::filesystem::path &cwd,
                            const std::string &file);
std::string reference_output_path(const std::filesystem::path &cwd,
                                  const std::string &file);

// Load layer `ctx` (its `suffix` must already be set) from compiler_output/:
// read metadata{suffix}.csv, shape the ACC/OUT (and, when load_input, the INP)
// buffers via data_formatting, read the uop/instruction streams, allocate the
// matching VTA DRAM, and copy the host buffers into it. Writes the layer's
// block size to `block_size`.
//
//   load_input  - true  : resolve and read the input file into inpA. Prefers
//                          input_nn.bin from the reference dir (the raw network
//                          image, written by reference_onnx.py); falls back to
//                          the compiler's per-op input{suffix}.bin when that is
//                          absent, which is the raw-VTA-IR fixture case.
//                 false : leave inpA empty (the NN path fills it later via the
//                          chaining/reshape step).
//   guard_empty - true  : skip 0-size VTAMemAlloc and null-guard the copies,
//                          mirroring the compiler's skip-empty DRAM rule.
//                 false : allocate/copy every buffer unconditionally (the NN
//                          path's historical behavior).
void load_and_allocate_layer(LayerContext &ctx,
                             const std::filesystem::path &cwd, int &block_size,
                             bool load_input, bool guard_empty);

// Free every non-null VTA-side buffer of a layer. Never freed between layers by
// the callers, so the DRAM address chain built during load stays intact.
void free_layer(LayerContext &ctx);

// TVM profiler handles for the functional backend. All null when running the
// verilated backend (g_use_verilator). setup_profiler() also clears the
// profiler and disables its debug mode; a non-null `clear` means the lookups
// succeeded.
struct ProfilerHandles {
  const tvm::runtime::PackedFunc *clear = nullptr;
  const tvm::runtime::PackedFunc *status = nullptr;
  const tvm::runtime::PackedFunc *debug_mode = nullptr;
};
ProfilerHandles setup_profiler();

// Verilator only: point g_verilator_config.trace_file at this layer's waveform
// before Run() reads it. No-op outside the verilated build.
void update_trace_file(const std::filesystem::path &cwd,
                       const std::string &suffix);

#endif // FSIM_LAYER_H_
