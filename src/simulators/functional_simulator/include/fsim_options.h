#ifndef FSIM_OPTIONS_H_
#define FSIM_OPTIONS_H_

#include <cstdint>
#include <string>

// Parsed command-line options shared by run_nn() and run_single_layer().
//
// Owned and populated by main() in src/fsim_main.cc; the per-mode impls treat
// it as read-only.
struct FsimOptions {
  // Mode: layer_idx < 0 → run the full NN graph. Otherwise run only that
  // VTA IR layer (single-layer mode).
  int layer_idx = -1;

  // Single-layer extras (ignored in NN mode).
  bool verbose = false;
  std::string output_path;

  // Common runtime knobs.
  bool dump_layers = false;
  uint64_t dram_base = 0;
  bool no_hw_reset = false;

  // Verilator-backend knobs (only meaningful in the vsim binary).
  bool trace_enabled = false;
  std::string sv_log_file;
  uint32_t timeout_cycles = 500000;
};

int run_nn(const FsimOptions &opts);
int run_single_layer(int layer_idx, const FsimOptions &opts);

#endif // FSIM_OPTIONS_H_
