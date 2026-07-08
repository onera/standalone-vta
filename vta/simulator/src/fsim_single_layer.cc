/***************************
    PRE-PROCESSOR DIRECTIVES
****************************/
#include "../include/fsim_layer.h" // dtypes, LayerContext, shared load/free/profiler helpers
#include "../include/fsim_options.h"
#include <cstdio>

/********************
    FSIM_NN
*********************/
int run_single_layer(int layer_index, const FsimOptions &opts) {
  const bool verbose = opts.verbose;
  // Define the current location
  std::filesystem::path currentPath = std::filesystem::current_path();

  // Path helper (shared impl in fsim_layer.cc).
  auto construct_path = [&](const std::string &filename) {
    return compiler_output_path(currentPath, filename);
  };

  // 1. DEFINE GLOBAL FILE PATHES
  // ----------------------------
  // Layer name with base info
  std::string fileLayerNamePath = construct_path("layers_name.csv");
  CsvMap layers_name_map = load_csv_to_map(fileLayerNamePath);

  // 2. GET NUMBER OF LAYERS AND THE DEBUG FLAG
  // ------------------------------------------
  // Get the number of VTA IRs
  int nb_vta_ir = strToInt(get_csv_value(layers_name_map, "nb_vta_ir", 1));

  // Get the debug flag (print option)
  std::string debug_str = get_csv_value(layers_name_map, "nb_vta_ir", 2);
  bool debug = (debug_str == "True");

  if (debug)
    printf("\n\nThere %d VTA IRs! \n", nb_vta_ir);

  // Validate the requested target layer.
  if (layer_index < 0 || layer_index >= nb_vta_ir) {
    std::cerr << "ERROR: Requested layer index " << layer_index
              << " is out of range [0, " << nb_vta_ir << ")." << std::endl;
    return EXIT_FAILURE;
  }

  // 3. PASS 1 - LOAD AND ALLOCATE LAYERS 0..=layer_index
  // ----------------------------------------------------
  // Only one layer is executed (layer_index), but the compiler lays out DRAM
  // cumulatively: layer N's instructions encode logical addresses that assume
  // every prior layer's buffers are already resident. So we load and allocate
  // layers 0..=layer_index to reproduce that layout up to the target. Layers
  // after the target live at higher addresses and are never referenced, so they
  // are not loaded. This mirrors fsim_nn's two-phase structure, minus chaining.
  std::vector<LayerContext> layers;
  layers.reserve(layer_index + 1);

  int block_size = 0;
  for (int i = 0; i <= layer_index; ++i) {
    LayerContext ctx;
    ctx.id = i;

    // A. GET SUFFIX OF THE CURRENT LAYER
    // ---
    ctx.suffix = get_csv_value(layers_name_map, std::to_string(i), 1);
    if (debug)
      printf("\n--- Loading Layer %d (Suffix: %s) ---\n", i,
             ctx.suffix.c_str());

    // Load + allocate this layer's buffers (shared with NN mode). Single-layer
    // mode reads the input file into inpA and guards empty buffers (skip 0-size
    // allocs) to keep DRAM addressing in lock-step with the compiler.
    load_and_allocate_layer(ctx, currentPath, block_size,
                            /*load_input=*/true, /*guard_empty=*/true);

    // Keep the layer (in load order).
    layers.push_back(std::move(ctx));
  }

  // Single final cleanup: free every non-null buffer of every layer, then the
  // device. Freeing only happens here (never between layers) so the address
  // chain built in Pass 1 stays intact through all executions.
  auto free_all_layers = [&]() {
    for (LayerContext &c : layers)
      free_layer(c);
  };

  // 4. PROFILER SETUP
  // -----------------
  // Functional backend only; returns null handles under the verilated backend.
  ProfilerHandles prof = setup_profiler();
  if (!g_use_verilator && !prof.clear)
    return -1;

  // 5. ALLOCATE VTA
  // ---------------
  // Allocate the VTA device
  VTADeviceHandle vta_device = VTADeviceAlloc();

  // 6. PASS 2 - EXECUTE ONLY THE TARGET LAYER
  // -----------------------------------------
  // The target is the last layer loaded in Pass 1 (index layer_index).
  {
    LayerContext &ctx = layers[layer_index];
    if (debug)
      printf("\n--- Executing Layer %d (Suffix: %s) ---\n", ctx.id,
             ctx.suffix.c_str());

    // Per-layer trace: update trace_file before Run() reads it (verilated
    // backend only; no-op otherwise).
    update_trace_file(currentPath, ctx.suffix);

    // Execute the layer
    int flag =
        VTADeviceRun(vta_device, ctx.phy_add_insn, ctx.insn_buffer.size(), 0);

    // Check the execution was successful
    if (flag != 0) {
      std::cerr << "ERROR: Execution failed at layer " << ctx.suffix
                << std::endl;
      free_all_layers();
      VTADeviceFree(vta_device);
      return EXIT_FAILURE;
    }

    // Copy Result Back
    if (ctx.mem_outC)
      VTAMemCopyToHost(ctx.outC.data(), ctx.mem_outC,
                       ctx.outC.size() * sizeof(out_dtype));

    // Print the result (only with --verbose)
    if (verbose) {
      printf("\n\nRESULT LAYER %d:\n", ctx.id);
      printf("Final result = {");
      print_vector(ctx.outC.data(), ctx.outC.size());
      printf("\n} \n");
    }

    // Dump the raw output bytes.
    if (!g_sim_output_override.empty()) {
      const std::string output_path = sim_output_path(
          currentPath, "layer" + std::to_string(ctx.id) + "_output.bin");
      std::error_code ec;
      std::filesystem::create_directories(
          std::filesystem::path(output_path).parent_path(), ec);
      std::ofstream out_file(output_path, std::ios::binary);
      if (!out_file.is_open()) {
        std::cerr << "ERROR: Could not open output file " << output_path
                  << std::endl;
      } else {
        out_file.write(reinterpret_cast<const char *>(ctx.outC.data()),
                       ctx.outC.size() * sizeof(out_dtype));
        if (verbose)
          printf("Wrote raw output (%zu bytes) to %s\n",
                 ctx.outC.size() * sizeof(out_dtype), output_path.c_str());
      }
    }
  }

  // 7. DEBUGGER
  // -----------
  if (prof.status && debug) {
    std::string profile_json = (*prof.status)();
    std::cout << "\n--- Profiler Status ---" << std::endl
              << profile_json << std::endl;
  }

  // 8. FREE EVERYTHING
  // ------------------
  free_all_layers();
  VTADeviceFree(vta_device);

  // Return OK
  return EXIT_SUCCESS;
}
