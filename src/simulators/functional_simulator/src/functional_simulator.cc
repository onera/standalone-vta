/*!
 * \file functional_simulator.cc
 * \brief Main entry point for the VTA functional/RTL simulator.
 *
 * Usage:
 *   build/functional_simulator [--verilator] [--insn <path>] [--uop <path>]
 *                              [--inp <path>] [--wgt <path>]
 *                              [--acc <path>] [--out <path>]
 *                              [--insn-count <N>]
 *
 * Without --verilator: runs the C++ functional model.
 * With    --verilator: drives the Verilated VTAShell RTL.
 *
 * Default paths are relative to the compiler_output/ directory at the repo
 * root (three levels up from src/simulators/functional_simulator/).
 */

#include "../include/simulator_header.h"
#include "../include/vta_device_backend.h"

#include <cstring>
#include <filesystem>
#include <iostream>
#include <string>
#include <vector>

// Defined in sim_driver.cc, exposed via vta_device_backend.h
extern bool g_use_verilator;
#ifdef VERILATOR_BUILD_ENABLED
extern VerilatorRunConfig g_verilator_config;
#endif

static void print_usage(const char *prog) {
  fprintf(stderr,
          "Usage: %s [--verilator] [--insn PATH] [--uop PATH] [--inp PATH]\n"
          "          [--wgt PATH] [--acc PATH] [--out PATH] [--insn-count N]\n"
          "  Verilator-only flags:\n"
          "          [--trace]              Enable waveform tracing (format set at compile time)\n"
          "          [--trace-file PATH]    Waveform output file (default: vtashell.fst/.vcd)\n"
          "          [--sv-log PATH]        Redirect SV $display output to PATH\n",
          prog);
}

int main(int argc, char **argv) {
  // Default binary paths (relative to compiler_output/ at repo root)
  namespace fs = std::filesystem;
  fs::path base = fs::current_path() / ".." / ".." / ".." / "compiler_output";

  std::string insn_path = (base / "instructions.bin").string();
  std::string uop_path = (base / "uop.bin").string();
  std::string inp_path = (base / "input.bin").string();
  std::string wgt_path = (base / "weight.bin").string();
  std::string acc_path = (base / "accumulator.bin").string();
  std::string out_path = (base / "output.bin").string();
  uint32_t insn_count_override = 0; // 0 = use file size

  // Verilator-only config values (populated below, applied after parsing)
  bool        parsed_trace   = false;
  std::string trace_file_arg = "";
  std::string sv_log_arg     = "";

  // Parse arguments
  for (int i = 1; i < argc; ++i) {
    if (strcmp(argv[i], "--verilator") == 0) {
      g_use_verilator = true;
    } else if (strcmp(argv[i], "--insn") == 0 && i + 1 < argc) {
      insn_path = argv[++i];
    } else if (strcmp(argv[i], "--uop") == 0 && i + 1 < argc) {
      uop_path = argv[++i];
    } else if (strcmp(argv[i], "--inp") == 0 && i + 1 < argc) {
      inp_path = argv[++i];
    } else if (strcmp(argv[i], "--wgt") == 0 && i + 1 < argc) {
      wgt_path = argv[++i];
    } else if (strcmp(argv[i], "--acc") == 0 && i + 1 < argc) {
      acc_path = argv[++i];
    } else if (strcmp(argv[i], "--out") == 0 && i + 1 < argc) {
      out_path = argv[++i];
    } else if (strcmp(argv[i], "--insn-count") == 0 && i + 1 < argc) {
      insn_count_override = static_cast<uint32_t>(atoi(argv[++i]));
    } else if (strcmp(argv[i], "--trace") == 0) {
      parsed_trace = true;
    } else if (strcmp(argv[i], "--trace-file") == 0 && i + 1 < argc) {
      trace_file_arg = argv[++i];
    } else if (strcmp(argv[i], "--sv-log") == 0 && i + 1 < argc) {
      sv_log_arg = argv[++i];
    } else if (strcmp(argv[i], "--help") == 0 || strcmp(argv[i], "-h") == 0) {
      print_usage(argv[0]);
      return 0;
    } else {
      fprintf(stderr, "Unknown argument: %s\n", argv[i]);
      print_usage(argv[0]);
      return 1;
    }
  }

#ifdef VERILATOR_BUILD_ENABLED
  g_verilator_config.trace_enabled = parsed_trace;
  g_verilator_config.trace_file    = trace_file_arg;
  g_verilator_config.sv_log_file   = sv_log_arg;
#endif

  if (g_use_verilator) {
    printf("[functional_simulator] Backend: Verilated RTL (VTAShell)\n");
    out_path = (base / "output_verilator.bin").string();
  } else {
    printf("[functional_simulator] Backend: C++ functional model\n");
  }

  // Read binary files
  using instruction_t = uint64_t[2]; // 128-bit instruction
  using uop_t = uint32_t;            // 32-bit UOP

  auto insn_buf = read_binary_file<uint8_t>(insn_path);
  auto uop_buf = read_binary_file<uint8_t>(uop_path);
  auto inp_buf = read_binary_file<uint8_t>(inp_path);
  auto wgt_buf = read_binary_file<uint8_t>(wgt_path);
  auto acc_buf = read_binary_file<uint8_t>(acc_path);

  if (insn_buf.empty()) {
    fprintf(stderr, "ERROR: could not read instruction file: %s\n",
            insn_path.c_str());
    return 1;
  }

  uint32_t insn_count =
      insn_count_override
          ? insn_count_override
          : static_cast<uint32_t>(insn_buf.size() / 16); // 128-bit per insn

  // Allocate VTA virtual DRAM in the order the standalone compiler expects:
  //   INP(0x1000), WGT(0x2000), ACC(0x3000), OUT(0x4000), UOP(0x5000),
  //   INSN(0x6000)
  // Each VTAMemAlloc advances the VirtualMemoryManager by one 4 KB page, so
  // this order matches the absolute DRAM addresses the compiler encoded in the
  // instructions (see compiler_output/memory_addresses.csv).
  size_t out_size = acc_buf.empty() ? (inp_buf.empty() ? 64 : inp_buf.size())
                                    : acc_buf.size();

  void *mem_inp = VTAMemAlloc(inp_buf.empty() ? 4 : inp_buf.size(), 1);
  void *mem_wgt = VTAMemAlloc(wgt_buf.empty() ? 4 : wgt_buf.size(), 1);
  void *mem_acc = VTAMemAlloc(acc_buf.empty() ? 4 : acc_buf.size(), 1);
  void *mem_out = VTAMemAlloc(out_size, 1);
  void *mem_uop = VTAMemAlloc(uop_buf.empty() ? 4 : uop_buf.size(), 1);
  void *mem_insn = VTAMemAlloc(insn_buf.size(), 1);

  if (!inp_buf.empty())
    VTAMemCopyFromHost(mem_inp, inp_buf.data(), inp_buf.size());
  if (!wgt_buf.empty())
    VTAMemCopyFromHost(mem_wgt, wgt_buf.data(), wgt_buf.size());
  if (!acc_buf.empty())
    VTAMemCopyFromHost(mem_acc, acc_buf.data(), acc_buf.size());
  if (!uop_buf.empty())
    VTAMemCopyFromHost(mem_uop, uop_buf.data(), uop_buf.size());
  VTAMemCopyFromHost(mem_insn, insn_buf.data(), insn_buf.size());

  VTABufferAddrs addrs;
  addrs.insn = VTAMemGetPhyAddr(mem_insn);
  addrs.uop = VTAMemGetPhyAddr(mem_uop);
  addrs.inp = VTAMemGetPhyAddr(mem_inp);
  addrs.wgt = VTAMemGetPhyAddr(mem_wgt);
  addrs.acc = VTAMemGetPhyAddr(mem_acc);
  addrs.out = VTAMemGetPhyAddr(mem_out);

  // Run simulator
  VTADeviceHandle dev = VTADeviceAlloc();
  static_cast<VTADeviceBackend *>(dev)->SetBufferAddresses(addrs);
  int ret = VTADeviceRun(dev, addrs.insn, insn_count, 0);
  VTADeviceFree(dev);

  if (ret != 0) {
    fprintf(stderr, "ERROR: VTADeviceRun returned %d\n", ret);
  } else {
    printf("[functional_simulator] Execution completed successfully.\n");

    // Write output
    std::vector<uint8_t> out_data(out_size);
    VTAMemCopyToHost(out_data.data(), mem_out, out_size);

    std::ofstream out_file(out_path, std::ios::binary);
    if (out_file) {
      out_file.write(reinterpret_cast<const char *>(out_data.data()), out_size);
      printf("[functional_simulator] Output written to: %s\n",
             out_path.c_str());
    }
  }

  VTAMemFree(mem_inp);
  VTAMemFree(mem_wgt);
  VTAMemFree(mem_acc);
  VTAMemFree(mem_out);
  VTAMemFree(mem_uop);
  VTAMemFree(mem_insn);

  return ret;
}
