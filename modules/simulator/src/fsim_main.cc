/***************************
    UNIFIED ENTRY POINT
****************************
    Single main() shared by build/fsim (C++ functional backend) and
    build/vsim (Verilator RTL backend). The backend is baked into the
    binary via VERILATOR_BUILD_ENABLED; there is no runtime flag for it.

    Mode (NN vs single-layer) is chosen at runtime by --layer N: absent
    runs the full NN graph through run_nn(); present runs only that VTA
    IR via run_single_layer().
****************************/
#include "../include/driver.h"
#include "../include/fsim_layer.h" // sim_output_path, g_sim_output_override
#include "../include/fsim_options.h"
#include "../include/vta_device_backend.h"

#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <filesystem>
#include <string>

static void print_usage(const char *prog) {
  std::fprintf(
      stderr,
      "Usage: %s [OPTIONS]\n"
      "\n"
      "Mode:\n"
      "  --layer N             Run only VTA IR layer N (default: "
      "full NN graph)\n"
      "\n"
      "Runtime:\n"
      "  --verbose             Print the layer result to stdout "
      "(single-layer only)\n"
      "  --output DIR          Directory for every file the simulator "
      "writes (final_output, dumps, traces, log).\n"
      "                        Defaults to the compile-time simulator-output "
      "dir (simulators_output) when omitted.\n"
      "  --comp-dir DIR        Directory the compiler outputs are read from.\n"
      "                        Defaults to the compile-time compiler-output "
      "dir when omitted.\n"
      "  --ref-dir DIR         Directory the reference is read from "
      "(input_nn.bin, reference.bin).\n"
      "                        Defaults to the compile-time reference-output "
      "dir when omitted.\n"
      "  --dump-layers         Dump per-layer raw input/output to the "
      "output dir\n"
#ifdef VERILATOR_BUILD_ENABLED
      "\n"
      "Verilator-backend flags:\n"
      "  --dram-base 0xADDR    Shift every DRAM buffer by this base\n"
      "  --no-hw-reset         Reset the VTA only on the first layer\n"
      "  --trace               Per-layer waveform to "
      "<output-dir>/trace_<layer>.{fst,vcd}\n"
      "  --sv-log PATH         Redirect SystemVerilog $display to "
      "PATH\n"
      "  --timeout-cycles N    Abort after N RTL cycles (default: "
      "500000)\n"
      "  --no-timeout          Disable the cycle timeout\n"
#endif
      "\n"
      "  -h, --help            Show this message\n",
      prog);
}

static bool parse_required_value(const char *flag, int argc, char **argv,
                                 int &i, const char *&out) {
  if (i + 1 >= argc) {
    std::fprintf(stderr, "Error: %s requires a value\n", flag);
    return false;
  }
  out = argv[++i];
  return true;
}

int main(int argc, char **argv) {
  FsimOptions opts;

  for (int i = 1; i < argc; ++i) {
    const char *arg = argv[i];
    const char *val = nullptr;

    if (std::strcmp(arg, "--layer") == 0) {
      if (!parse_required_value(arg, argc, argv, i, val))
        return 1;
      opts.layer_idx = std::atoi(val);
    } else if (std::strcmp(arg, "--verbose") == 0) {
      opts.verbose = true;
    } else if (std::strcmp(arg, "--output") == 0) {
      if (!parse_required_value(arg, argc, argv, i, val))
        return 1;
      opts.output_dir = val;
    } else if (std::strcmp(arg, "--comp-dir") == 0) {
      if (!parse_required_value(arg, argc, argv, i, val))
        return 1;
      opts.comp_dir = val;
    } else if (std::strcmp(arg, "--ref-dir") == 0) {
      if (!parse_required_value(arg, argc, argv, i, val))
        return 1;
      opts.ref_dir = val;
    } else if (std::strcmp(arg, "--dump-layers") == 0) {
      opts.dump_layers = true;
#ifdef VERILATOR_BUILD_ENABLED
    } else if (std::strcmp(arg, "--dram-base") == 0) {
      if (!parse_required_value(arg, argc, argv, i, val))
        return 1;
      opts.dram_base = std::strtoull(val, nullptr, 0);
    } else if (std::strcmp(arg, "--no-hw-reset") == 0) {
      opts.no_hw_reset = true;
    } else if (std::strcmp(arg, "--trace") == 0) {
      opts.trace_enabled = true;
    } else if (std::strcmp(arg, "--sv-log") == 0) {
      if (!parse_required_value(arg, argc, argv, i, val))
        return 1;
      opts.sv_log_file = val;
    } else if (std::strcmp(arg, "--timeout-cycles") == 0) {
      if (!parse_required_value(arg, argc, argv, i, val))
        return 1;
      opts.timeout_cycles = static_cast<uint32_t>(std::atoi(val));
    } else if (std::strcmp(arg, "--no-timeout") == 0) {
      opts.timeout_cycles = 0;
#endif
    } else if (std::strcmp(arg, "--help") == 0 || std::strcmp(arg, "-h") == 0) {
      print_usage(argv[0]);
      return 0;
    } else {
      std::fprintf(stderr, "Unknown argument: %s\n", arg);
      print_usage(argv[0]);
      return 1;
    }
  }

  g_sim_output_override = opts.output_dir;
  g_comp_dir_override = opts.comp_dir;
  g_ref_dir_override = opts.ref_dir;

  // Backend selection is baked in at compile time.
#ifdef VERILATOR_BUILD_ENABLED
  g_use_verilator = true;
#ifdef VTA_VERIF_DEBUG
  if (opts.sv_log_file.empty()) {
    opts.sv_log_file =
        sim_output_path(std::filesystem::current_path(), "verilator.log");
  }
#endif
  g_verilator_config.trace_enabled = opts.trace_enabled;
  g_verilator_config.sv_log_file = opts.sv_log_file;
  g_verilator_config.timeout_cycles = opts.timeout_cycles;
  g_verilator_config.reset_between_layers = !opts.no_hw_reset;

  // DRAM base must be set before the first VTAMemAlloc. The Verilated backend
  // programs the VCR data pointers to this base (RTL drives the HW address
  // adders); vsim-only knob.
  if (opts.dram_base != 0) {
    VTASetDramBase(opts.dram_base);
    std::printf("[fsim] dram-base = 0x%llx\n",
                static_cast<unsigned long long>(opts.dram_base));
  }
#else
  g_use_verilator = false;
#endif

#ifdef VERILATOR_BUILD_ENABLED
  std::printf("[Cycle Accurate Simulation] Backend: Verilated RTL\n");
  if (opts.trace_enabled)
    std::printf("[Info] tracing is enabled: performance may suffer\n");
  if (opts.no_hw_reset)
    std::printf("[fsim] no-hw-reset: core resets only on the first layer\n");
#else
  std::printf("[Functional Simulation] Backend: C++ functional model\n");
#endif

  if (opts.dump_layers)
    std::printf("[fsim] dump-layers: writing per-layer bins to %s\n",
                sim_output_path(std::filesystem::current_path(), "").c_str());

  const int rc = opts.layer_idx >= 0 ? run_single_layer(opts.layer_idx, opts)
                                     : run_nn(opts);

#ifdef VERILATOR_BUILD_ENABLED
  if (!g_verilator_config.sv_log_file.empty())
    std::printf("SystemVerilog log written to %s\n",
                g_verilator_config.sv_log_file.c_str());
#endif

  return rc;
}
