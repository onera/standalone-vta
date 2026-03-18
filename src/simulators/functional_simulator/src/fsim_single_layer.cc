/***************************
    PRE-PROCESSOR DIRECTIVES
****************************/
#include "../include/simulator_header.h"
#include "../include/vta_device_backend.h"
// Define the data type
using inp_dtype = int32_t;
using wgt_dtype = int32_t;
using acc_dtype = int32_t;

extern bool g_use_verilator;
#ifdef VERILATOR_BUILD_ENABLED
extern VerilatorRunConfig g_verilator_config;
#endif
// structure to hold all data specific to one layer
struct LayerContext {
  int id;
  std::string suffix;

  // Buffers (Host side)
  std::vector<inp_dtype> inpA, outC;
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

/********************
    FSIM_NN
*********************/
int fsim_single_layer() {
  // Variable to print results
  bool doPrint = true;

  // Define the current location
  std::filesystem::path currentPath = std::filesystem::current_path();

  // Helper for paths
  auto construct_path = [&](const std::string &filename) {
    return (currentPath / ".." / ".." / ".." / "compiler_output" / filename)
        .string();
  };

// 0. PROFILER SETUP
// -----------------
#ifndef VERILATOR_BUILD_ENABLED
  const tvm::runtime::PackedFunc *profiler_clear =
      tvm::runtime::Registry::Get("vta.simulator.profiler_clear");
  const tvm::runtime::PackedFunc *profiler_status =
      tvm::runtime::Registry::Get("vta.simulator.profiler_status");
  const tvm::runtime::PackedFunc *profiler_debug_mode =
      tvm::runtime::Registry::Get("vta.simulator.profiler_debug_mode");

  if (!profiler_clear || !profiler_status || !profiler_debug_mode) {
    std::cerr << "ERROR: Profiler functions not found." << std::endl;
    return -1;
  }
  (*profiler_clear)();
  int debug_flag = 0;
  (*profiler_debug_mode)(debug_flag);
#endif

  // 1. ALLOCATE VTA
  // ---------------
  // Allocate the VTA device
  VTADeviceHandle vta_device = VTADeviceAlloc();

  // 2. DEFINE GLOBAL FILE PATHES
  // ----------------------------
  // Layer name with base info
  std::string fileLayerNamePath = construct_path("layers_name.csv");
  CsvMap layers_name_map = load_csv_to_map(fileLayerNamePath);

  // 3. GET NUMBER OF LAYERS AND THE DEBUG FLAG
  // ------------------------------------------
  // Get the number of VTA IRs
  int nb_vta_ir = strToInt(get_csv_value(layers_name_map, "nb_vta_ir", 1));

  // Get the debug flag (print option)
  std::string debug_str = get_csv_value(layers_name_map, "nb_vta_ir", 2);
  bool debug = (debug_str == "True");

  if (debug)
    printf("\n\nThere %d VTA IRs! \n", nb_vta_ir);

  // 4. LOAD, EXECUTE, FREE A LAYER
  // ------------------------------
  int block_size;
  for (int i = 0; i < nb_vta_ir; ++i) {
    LayerContext ctx;
    ctx.id = i;

    // 4.1 ALLOCATE THE LAYER
    // ----------------------

    // A. GET SUFFIX OF THE CURRENT LAYER
    // ---
    ctx.suffix = get_csv_value(layers_name_map, std::to_string(i), 1);
    if (debug)
      printf("\n--- Loading Layer %d (Suffix: %s) ---\n", i,
             ctx.suffix.c_str());

    // B. LOAD LAYER-RELATED FILES
    // ----
    // Layer general information (create a MAP)
    std::string fileMetadataPath =
        construct_path("metadata" + ctx.suffix + ".csv");
    CsvMap metadata_map = load_csv_to_map(fileMetadataPath);

    // Binaries
    std::string fileInpPath = construct_path("input" + ctx.suffix + ".bin");
    std::string fileWgtPath = construct_path("weight" + ctx.suffix + ".bin");
    std::string fileAccPath =
        construct_path("accumulator" + ctx.suffix + ".bin");
    std::string fileAddAccPath =
        construct_path("add_accumulator" + ctx.suffix + ".bin");
    std::string fileUopPath = construct_path("uop" + ctx.suffix + ".bin");
    std::string fileInsnPath =
        construct_path("instructions" + ctx.suffix + ".bin");

    // C. READ METADATA INFO
    // ---
    // Block size and square
    block_size = strToInt(get_csv_value(metadata_map, "BS", 2));
    std::string out_square_str = get_csv_value(metadata_map, "BS", 1);
    bool out_square = (out_square_str == "True");

    // Dimensions
    int A_row = strToInt(get_csv_value(metadata_map, "A", 1));
    int A_col = strToInt(get_csv_value(metadata_map, "A", 2));
    int X_row = strToInt(get_csv_value(metadata_map, "X", 1));
    int X_col = strToInt(get_csv_value(metadata_map, "X", 2));
    int Y_row = strToInt(get_csv_value(metadata_map, "Y", 1));
    int Y_col = strToInt(get_csv_value(metadata_map, "Y", 2));
    int C_row = strToInt(get_csv_value(metadata_map, "C", 1));
    int C_col = strToInt(get_csv_value(metadata_map, "C", 2));

    // D. READ AND SHAPE THE DATA
    // ---
    // Input A
    std::vector<inp_dtype> raw_inpA = read_binary_file<inp_dtype>(fileInpPath);
    if (A_row <= 0 || A_col <= 0)
      ctx.inpA = raw_inpA;
    else
      ctx.inpA = data_formatting(raw_inpA, A_row, A_col, block_size, true);

    // Weight B
    ctx.wgtB = read_binary_file<wgt_dtype>(fileWgtPath);

    // Acc X
    std::vector<acc_dtype> raw_accX = read_binary_file<acc_dtype>(fileAccPath);
    if (X_row <= 0 || X_col <= 0)
      ctx.accX = raw_accX;
    else
      ctx.accX = data_formatting(raw_accX, X_row, X_col, block_size, true);

    // Acc Y
    std::vector<acc_dtype> raw_accY =
        read_binary_file<acc_dtype>(fileAddAccPath);
    if (Y_row <= 0 || Y_col <= 0)
      ctx.accY = raw_accY;
    else
      ctx.accY = data_formatting(raw_accY, Y_row, Y_col, block_size, true);

    // Output C (buffer space)
    std::vector<inp_dtype> raw_outC;
    if (C_row <= 0 || C_col <= 0)
      ctx.outC = raw_outC;
    else
      ctx.outC =
          data_formatting(raw_outC, C_row, C_col, block_size, out_square);

    // Instructions & UOPs
    ctx.uop_buffer = read_binary_file<uop_t>(fileUopPath);
    ctx.insn_buffer = read_binary_file<instruction_t>(fileInsnPath);

    // E. ALLOCATE VTA MEMORY (virtual DRAM)
    // ---
    ctx.mem_inpA = VTAMemAlloc(ctx.inpA.size() * sizeof(inp_dtype), 1);
    ctx.mem_wgtB = VTAMemAlloc(ctx.wgtB.size() * sizeof(wgt_dtype), 1);
    ctx.mem_accX = VTAMemAlloc(ctx.accX.size() * sizeof(acc_dtype), 1);
    ctx.mem_accY = VTAMemAlloc(ctx.accY.size() * sizeof(acc_dtype), 1);
    ctx.mem_outC = VTAMemAlloc(ctx.outC.size() * sizeof(inp_dtype), 1);
    ctx.mem_uop = VTAMemAlloc(ctx.uop_buffer.size() * sizeof(uop_t), 1);
    ctx.mem_insn =
        VTAMemAlloc(ctx.insn_buffer.size() * sizeof(instruction_t), 1);

    // Get physical address for instructions
    ctx.phy_add_insn = VTAMemGetPhyAddr(ctx.mem_insn);

    // F. WRITE THE DATA IN VIRTUAL DRAM
    // ---
    VTAMemCopyFromHost(ctx.mem_inpA, ctx.inpA.data(),
                       ctx.inpA.size() * sizeof(inp_dtype));
    VTAMemCopyFromHost(ctx.mem_wgtB, ctx.wgtB.data(),
                       ctx.wgtB.size() * sizeof(wgt_dtype));
    VTAMemCopyFromHost(ctx.mem_accX, ctx.accX.data(),
                       ctx.accX.size() * sizeof(acc_dtype));
    VTAMemCopyFromHost(ctx.mem_accY, ctx.accY.data(),
                       ctx.accY.size() * sizeof(acc_dtype));
    VTAMemCopyFromHost(ctx.mem_outC, ctx.outC.data(),
                       ctx.outC.size() * sizeof(inp_dtype));
    VTAMemCopyFromHost(ctx.mem_uop, ctx.uop_buffer.data(),
                       ctx.uop_buffer.size() * sizeof(uop_t));
    VTAMemCopyFromHost(ctx.mem_insn, ctx.insn_buffer.data(),
                       ctx.insn_buffer.size() * sizeof(instruction_t));

    // 4.2 EXECUTE THE LAYER
    // ---------------------

    // ---
    // Execute the layer
    int flag =
        VTADeviceRun(vta_device, ctx.phy_add_insn, ctx.insn_buffer.size(), 0);

    // Check the execution was successful
    if (flag != 0) {
      std::cerr << "ERROR: Execution failed at layer " << ctx.suffix
                << std::endl;
      VTADeviceFree(vta_device);
      VTAMemFree(ctx.mem_inpA);
      VTAMemFree(ctx.mem_wgtB);
      VTAMemFree(ctx.mem_accX);
      VTAMemFree(ctx.mem_accY);
      VTAMemFree(ctx.mem_outC);
      VTAMemFree(ctx.mem_uop);
      VTAMemFree(ctx.mem_insn);
      return EXIT_FAILURE;
    }

    // Copy Result Back
    VTAMemCopyToHost(ctx.outC.data(), ctx.mem_outC,
                     ctx.outC.size() * sizeof(inp_dtype));

    // 4.3 FREE THE LAYER
    // ------------------
    VTAMemFree(ctx.mem_inpA);
    VTAMemFree(ctx.mem_wgtB);
    VTAMemFree(ctx.mem_accX);
    VTAMemFree(ctx.mem_accY);
    VTAMemFree(ctx.mem_outC);
    VTAMemFree(ctx.mem_uop);
    VTAMemFree(ctx.mem_insn);

    // 4.4 PRINT
    // ---------
    if (doPrint) {
      printf("\n\nRESULT LAYER %d:\n", ctx.id);
      printf("Final result = {");
      print_vector(ctx.outC.data(), ctx.outC.size());
      printf("\n} \n");
    }
  }

// 5. DEBUGGER
// -----------
#ifndef VERILATOR_BUILD_ENABLED
  if (debug) {
    std::string profile_json = (*profiler_status)();
    std::cout << "\n--- Profiler Status ---" << std::endl
              << profile_json << std::endl;
  }
#endif

  // 5. FREE THE VTA
  // ---------------
  VTADeviceFree(vta_device);

  // Return OK
  return EXIT_SUCCESS;
}

/****************
    MAIN FUNCTION
*****************/
#ifdef VERILATOR_BUILD_ENABLED
static void print_usage(const char *prog) {

  fprintf(
      stderr,
      "Usage: %s [OPTIONS]"
      "--verilator: toggle verilator backend simulation"
      "  Verilator-only flags:\n"
      "          [--trace]              Enable waveform tracing (format set at "
      "compile time)\n"
      "          [--trace-file PATH]    Waveform output file (default: "
      "vtashell.fst/.vcd)\n"
      "          [--sv-log PATH]        Redirect SV $display output to PATH\n"
      "          [--timeout-cycles N]   Max RTL clock cycles before abort "
      "(default: 500000)\n",
      prog);
}
int main(int argc, char **argv) {
  // Verilator-only config values (populated below, applied after parsing)
  bool parsed_trace = false;
  std::string trace_file_arg = "";
  std::string sv_log_arg = "";
  uint32_t timeout_cycles = 500000;

  for (int i = 1; i < argc; ++i) {
    if (strcmp(argv[i], "--verilator") == 0) {
      g_use_verilator = true;
    } else if (strcmp(argv[i], "--trace") == 0) {
      parsed_trace = true;
    } else if (strcmp(argv[i], "--trace-file") == 0 && i + 1 < argc) {
      trace_file_arg = argv[++i];
    } else if (strcmp(argv[i], "--sv-log") == 0 && i + 1 < argc) {
      sv_log_arg = argv[++i];
    } else if (strcmp(argv[i], "--timeout-cycles") == 0 && i + 1 < argc) {
      timeout_cycles = static_cast<uint32_t>(atoi(argv[++i]));
    } else if (strcmp(argv[i], "--help") == 0 || strcmp(argv[i], "-h") == 0) {
      print_usage(argv[0]);
      return 0;
    } else {
      fprintf(stderr, "Unknown argument: %s\n", argv[i]);
      print_usage(argv[0]);
      return 1;
    }
  }
  g_verilator_config.trace_enabled = parsed_trace;
  g_verilator_config.trace_file = trace_file_arg;
  g_verilator_config.timeout_cycles = timeout_cycles;
  if (g_use_verilator) {
    printf("[Cycle Accurate Simulation] Backend: Verilated RTL (VTAShell)\n");
  } else {
    printf("[Functional Simulation] Backend: C++ functional model\n");
  }
  return fsim_single_layer();
}
#else
int main() { return fsim_single_layer(); }
#endif
