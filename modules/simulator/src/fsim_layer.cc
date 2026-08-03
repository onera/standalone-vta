/***************************
    SHARED FSIM LAYER SCAFFOLDING
****************************/
// Implementations shared by run_nn() (fsim_nn.cc) and run_single_layer()
// (fsim_single_layer.cc). See include/fsim_layer.h for the rationale.

#include "../include/fsim_layer.h"

/********************
    PATH HELPERS
*********************/
// Default directory bases.
#ifndef VTA_COMPILER_OUTPUT
#define VTA_COMPILER_OUTPUT "compiler_output"
#endif
#ifndef VTA_SIMULATOR_OUTPUT
#define VTA_SIMULATOR_OUTPUT "simulators_output"
#endif
#ifndef VTA_REFERENCE_OUTPUT
#define VTA_REFERENCE_OUTPUT "reference_output"
#endif

// Runtime override of the simulator-output dir (set from --output in main()).
std::string g_sim_output_override;
std::string g_comp_dir_override;
std::string g_ref_dir_override;

std::string compiler_output_path(const std::filesystem::path &cwd,
                                 const std::string &file) {
  const std::string base =
      g_comp_dir_override.empty() ? VTA_COMPILER_OUTPUT : g_comp_dir_override;
  return (cwd / base / file).lexically_normal().string();
}

std::string sim_output_path(const std::filesystem::path &cwd,
                            const std::string &file) {
  const std::string base = g_sim_output_override.empty()
                               ? VTA_SIMULATOR_OUTPUT
                               : g_sim_output_override;
  return (cwd / base / file).lexically_normal().string();
}

std::string reference_output_path(const std::filesystem::path &cwd,
                                  const std::string &file) {
  const std::string base =
      g_ref_dir_override.empty() ? VTA_REFERENCE_OUTPUT : g_ref_dir_override;
  return (cwd / base / file).lexically_normal().string();
}

/********************
    LAYER LOAD + ALLOCATE + COPY
*********************/
void load_and_allocate_layer(LayerContext &ctx,
                             const std::filesystem::path &cwd, int &block_size,
                             bool load_input, bool guard_empty) {
  auto path = [&](const std::string &f) {
    return compiler_output_path(cwd, f);
  };

  // B. LOAD LAYER-RELATED FILE PATHS
  // ---
  std::string fileMetadataPath = path("metadata" + ctx.suffix + ".csv");
  CsvMap metadata_map = load_csv_to_map(fileMetadataPath);

  std::string fileWgtPath = path("weight" + ctx.suffix + ".bin");
  std::string fileAccPath = path("accumulator" + ctx.suffix + ".bin");
  std::string fileAddAccPath = path("add_accumulator" + ctx.suffix + ".bin");
  std::string fileUopPath = path("uop" + ctx.suffix + ".bin");
  std::string fileInsnPath = path("instructions" + ctx.suffix + ".bin");

  // C. READ METADATA INFO
  // ---
  // Block size
  block_size = strToInt(get_csv_value(metadata_map, "BS", 1));

  // Dimensions and per-buffer square flag (column 3)
  int A_row = strToInt(get_csv_value(metadata_map, "A", 1));
  int A_col = strToInt(get_csv_value(metadata_map, "A", 2));
  bool A_square = (get_csv_value(metadata_map, "A", 3) == "True");

  int X_row = strToInt(get_csv_value(metadata_map, "X", 1));
  int X_col = strToInt(get_csv_value(metadata_map, "X", 2));
  bool X_square = (get_csv_value(metadata_map, "X", 3) == "True");

  int Y_row = strToInt(get_csv_value(metadata_map, "Y", 1));
  int Y_col = strToInt(get_csv_value(metadata_map, "Y", 2));
  bool Y_square = (get_csv_value(metadata_map, "Y", 3) == "True");

  int C_row = strToInt(get_csv_value(metadata_map, "C", 1));
  int C_col = strToInt(get_csv_value(metadata_map, "C", 2));
  bool C_square = (get_csv_value(metadata_map, "C", 3) == "True");

  // D. READ AND SHAPE THE DATA
  // ---
  // Input A. Single-layer mode reads the input file (input_nn.bin from the
  // reference dir if present, else the compiler's per-op input{suffix}.bin);
  // the NN path leaves raw_inpA empty and fills inpA later via chaining.
  // Either way the same shaping runs, so inpA's size (hence the mem_inpA
  // allocation / DRAM layout) is identical in both modes. Tolerant of an
  // empty input.
  std::vector<inp_dtype> raw_inpA;
  if (load_input) {
    // Existence-check first to avoid read_binary_file's perror on the missing
    // candidate (test_gemm / test_alu have no input_nn.bin).
    std::string fileInputNNPath = reference_output_path(cwd, "input_nn.bin");
    std::string filePerOpInpPath = path("input" + ctx.suffix + ".bin");
    std::error_code inp_ec;
    std::string fileInpPath =
        (std::filesystem::exists(fileInputNNPath, inp_ec) &&
         std::filesystem::file_size(fileInputNNPath, inp_ec) > 0)
            ? fileInputNNPath
            : filePerOpInpPath;
    raw_inpA = read_binary_file<inp_dtype>(fileInpPath);
  }
  if (A_row <= 0 || A_col <= 0)
    ctx.inpA = raw_inpA;
  else
    ctx.inpA = data_formatting(raw_inpA, A_row, A_col, block_size, A_square);

  // Weight B
  ctx.wgtB = read_binary_file<wgt_dtype>(fileWgtPath);

  // Acc X
  std::vector<acc_dtype> raw_accX = read_binary_file<acc_dtype>(fileAccPath);
  if (X_row <= 0 || X_col <= 0)
    ctx.accX = raw_accX;
  else
    ctx.accX = data_formatting(raw_accX, X_row, X_col, block_size, X_square);

  // Acc Y
  std::vector<acc_dtype> raw_accY = read_binary_file<acc_dtype>(fileAddAccPath);
  if (Y_row <= 0 || Y_col <= 0)
    ctx.accY = raw_accY;
  else
    ctx.accY = data_formatting(raw_accY, Y_row, Y_col, block_size, Y_square);

  // Output C (buffer space)
  std::vector<out_dtype> raw_outC;
  if (C_row <= 0 || C_col <= 0)
    ctx.outC = raw_outC;
  else
    ctx.outC = data_formatting(raw_outC, C_row, C_col, block_size, C_square);

  // Instructions & UOPs
  ctx.uop_buffer = read_binary_file<uop_t>(fileUopPath);
  ctx.insn_buffer = read_binary_file<instruction_t>(fileInsnPath);

  // E. ALLOCATE VTA MEMORY (virtual DRAM)
  // ---
  // guard_empty mirrors the compiler's skip-empty rule (a 0-size VTAMemAlloc
  // creates a 0-page entry that does not advance the page table).
  auto alloc = [&](size_t bytes) -> void * {
    if (guard_empty)
      return bytes ? VTAMemAlloc(bytes, 1) : nullptr;
    return VTAMemAlloc(bytes, 1);
  };
  ctx.mem_inpA = alloc(ctx.inpA.size() * sizeof(inp_dtype));
  ctx.mem_wgtB = alloc(ctx.wgtB.size() * sizeof(wgt_dtype));
  ctx.mem_accX = alloc(ctx.accX.size() * sizeof(acc_dtype));
  ctx.mem_accY = alloc(ctx.accY.size() * sizeof(acc_dtype));
  ctx.mem_outC = alloc(ctx.outC.size() * sizeof(out_dtype));
  ctx.mem_uop = alloc(ctx.uop_buffer.size() * sizeof(uop_t));
  ctx.mem_insn = alloc(ctx.insn_buffer.size() * sizeof(instruction_t));

  // Get physical address for instructions
  ctx.phy_add_insn = VTAMemGetPhyAddr(ctx.mem_insn);

  // F. WRITE THE DATA IN VIRTUAL DRAM
  // ---
  auto copy = [&](void *mem, const void *src, size_t bytes) {
    if (!guard_empty || mem)
      VTAMemCopyFromHost(mem, const_cast<void *>(src), bytes);
  };
  copy(ctx.mem_inpA, ctx.inpA.data(), ctx.inpA.size() * sizeof(inp_dtype));
  copy(ctx.mem_wgtB, ctx.wgtB.data(), ctx.wgtB.size() * sizeof(wgt_dtype));
  copy(ctx.mem_accX, ctx.accX.data(), ctx.accX.size() * sizeof(acc_dtype));
  copy(ctx.mem_accY, ctx.accY.data(), ctx.accY.size() * sizeof(acc_dtype));
  copy(ctx.mem_outC, ctx.outC.data(), ctx.outC.size() * sizeof(out_dtype));
  copy(ctx.mem_uop, ctx.uop_buffer.data(),
       ctx.uop_buffer.size() * sizeof(uop_t));
  copy(ctx.mem_insn, ctx.insn_buffer.data(),
       ctx.insn_buffer.size() * sizeof(instruction_t));
}

/********************
    FREE
*********************/
void free_layer(LayerContext &ctx) {
  if (ctx.mem_inpA)
    VTAMemFree(ctx.mem_inpA);
  if (ctx.mem_wgtB)
    VTAMemFree(ctx.mem_wgtB);
  if (ctx.mem_accX)
    VTAMemFree(ctx.mem_accX);
  if (ctx.mem_accY)
    VTAMemFree(ctx.mem_accY);
  if (ctx.mem_outC)
    VTAMemFree(ctx.mem_outC);
  if (ctx.mem_uop)
    VTAMemFree(ctx.mem_uop);
  if (ctx.mem_insn)
    VTAMemFree(ctx.mem_insn);
}

/********************
    PROFILER
*********************/
ProfilerHandles setup_profiler() {
  ProfilerHandles h;
  // The verilated backend has no functional-model profiler.
  if (g_use_verilator)
    return h;

  h.clear = tvm::runtime::Registry::Get("vta.simulator.profiler_clear");
  h.status = tvm::runtime::Registry::Get("vta.simulator.profiler_status");
  h.debug_mode =
      tvm::runtime::Registry::Get("vta.simulator.profiler_debug_mode");

  if (!h.clear || !h.status || !h.debug_mode) {
    std::cerr << "ERROR: Profiler functions not found." << std::endl;
    return ProfilerHandles{}; // all null → caller treats as failure
  }

  (*h.clear)();
  int debug_flag = 0;
  (*h.debug_mode)(debug_flag);
  return h;
}

/********************
    VERILATOR TRACE FILE
*********************/
void update_trace_file(const std::filesystem::path &cwd,
                       const std::string &suffix) {
#ifdef VERILATOR_BUILD_ENABLED
  if (g_use_verilator && g_verilator_config.trace_enabled) {
#ifdef TRACE_FORMAT_VCD
    const std::string trace_ext = ".vcd";
#else
    const std::string trace_ext = ".fst";
#endif
    g_verilator_config.trace_file =
        sim_output_path(cwd, "trace_" + suffix + trace_ext);
  }
#else
  (void)cwd;
  (void)suffix;
#endif
}
