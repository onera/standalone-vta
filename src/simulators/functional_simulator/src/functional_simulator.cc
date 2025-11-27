/***************************
    PRE-PROCESSOR DIRECTIVES
****************************/
#include "../include/simulator_header.h"
#include "../external_lib/tvm/packed_func.h"
#include "../external_lib/tvm/registry.h"
#include <vector>
#include <string>
#include <iostream>

// structure to hold all data specific to one layer
struct LayerContext {
    int id;
    std::string suffix;
    
    // Metadata
    int C_row, C_col; // Needed for verification logic
    
    // Buffers (Host side)
    std::vector<int8_t> inpA, wgtB, outC, refC;
    std::vector<int32_t> accX, accY;
    std::vector<uop_t> uop_buffer;
    std::vector<instruction_t> insn_buffer;

    // Memory Pointers (VTA side)
    void* mem_inpA = nullptr;
    void* mem_wgtB = nullptr;
    void* mem_accX = nullptr;
    void* mem_accY = nullptr;
    void* mem_outC = nullptr;
    void* mem_uop  = nullptr;
    void* mem_insn = nullptr;

    // Physical Addresses
    vta_phy_addr_t phy_add_insn;
};

/********************
    EXECUTE_SIMULATOR
*********************/
int execute_simulator() {
    // Variable to print results
    bool doPrint = false;

    // Define the current location
    std::filesystem::path currentPath = std::filesystem::current_path();

    // Helper for paths
    auto construct_path = [&](const std::string& filename) {
        return (currentPath / ".." / ".." / ".." / "compiler_output" / filename).string();
    };

    // 1. GET NUMBER OF LAYERS AND THE DEBUG FLAG
    // ------------------------------------------
    std::string fileLayerNamePath = construct_path("layers_name.csv");
    std::string nb_vta_ir_str = getCsvElementByName(fileLayerNamePath, "nb_vta_ir", 1);
    int nb_vta_ir = strToInt(nb_vta_ir_str);

    // Get the debug flag (print option)
    std::string debug_str = getCsvElementByName(fileLayerNamePath, "nb_vta_ir", 2);
    // Clean the variable for robust comparison
    debug_str.erase(std::remove(debug_str.begin(), debug_str.end(), '\n'), debug_str.end());
    debug_str.erase(std::remove(debug_str.begin(), debug_str.end(), '\r'), debug_str.end());
    debug_str.erase(std::remove(debug_str.begin(), debug_str.end(), ' '), debug_str.end());
    // Set the debug flag
    bool debug = (debug_str == "True");

    if (debug) printf("DEBUG: Found %d layers to execute.\n", nb_vta_ir);

    // Vector to store all layers
    std::vector<LayerContext> layers;
    layers.reserve(nb_vta_ir);


    // 2. LOAD AND ALLOCATE ALL LAYERS
    // -------------------------------
    for (int i = 0; i < nb_vta_ir; ++i) {
        LayerContext ctx;
        ctx.id = i;

        // Get Suffix for this specific layer (column "0", "1", "2"...)
        ctx.suffix = getCsvElementByName(fileLayerNamePath, std::to_string(i), 1);
        
        if (debug) printf("\n--- Loading Layer %d (Suffix: %s) ---\n", i, ctx.suffix.c_str());

        // READ METADATA
        std::string fileMetadataPath = construct_path("metadata" + ctx.suffix + ".csv");

        std::string block_size_str = getCsvElementByName(fileMetadataPath, "BS", 2);
        int block_size = strToInt(block_size_str);

        std::string out_square_str = getCsvElementByName(fileMetadataPath, "BS", 1);
        bool out_square = (out_square_str == "True");

        // Dimensions
        int A_row = strToInt(getCsvElementByName(fileMetadataPath, "A", 1));
        int A_col = strToInt(getCsvElementByName(fileMetadataPath, "A", 2));
        int X_row = strToInt(getCsvElementByName(fileMetadataPath, "X", 1));
        int X_col = strToInt(getCsvElementByName(fileMetadataPath, "X", 2));
        int Y_row = strToInt(getCsvElementByName(fileMetadataPath, "Y", 1));
        int Y_col = strToInt(getCsvElementByName(fileMetadataPath, "Y", 2));
        ctx.C_row = strToInt(getCsvElementByName(fileMetadataPath, "C", 1));
        ctx.C_col = strToInt(getCsvElementByName(fileMetadataPath, "C", 2));

        // READ BINARIES
        std::string fileInpPath = construct_path("input" + ctx.suffix + ".bin");
        std::string fileWgtPath = construct_path("weight" + ctx.suffix + ".bin");
        std::string fileAccPath = construct_path("accumulator" + ctx.suffix + ".bin");
        std::string fileAddAccPath = construct_path("add_accumulator" + ctx.suffix + ".bin");
        std::string fileOutPath = construct_path("output" + ctx.suffix + ".bin");
        std::string fileRefPath = construct_path("reference" + ctx.suffix + ".bin");
        std::string fileUopPath = construct_path("uop" + ctx.suffix + ".bin");
        std::string fileInsnPath = construct_path("instructions" + ctx.suffix + ".bin");

        // Input A
        std::vector<int8_t> raw_inpA = read_binary_file<int8_t>(fileInpPath);
        if (A_row <= 0 || A_col <= 0) ctx.inpA = raw_inpA;
        else ctx.inpA = data_formatting(raw_inpA, A_row, A_col, block_size, true);

        // Weight B
        ctx.wgtB = read_binary_file<int8_t>(fileWgtPath);

        // Acc X
        std::vector<int32_t> raw_accX = read_binary_file<int32_t>(fileAccPath);
        if (X_row <= 0 || X_col <= 0) ctx.accX = raw_accX;
        else ctx.accX = data_formatting(raw_accX, X_row, X_col, block_size, true);

        // Acc Y
        std::vector<int32_t> raw_accY = read_binary_file<int32_t>(fileAddAccPath);
        if (Y_row <= 0 || Y_col <= 0) ctx.accY = raw_accY;
        else ctx.accY = data_formatting(raw_accY, Y_row, Y_col, block_size, true);

        // Output C (buffer space)
        ctx.outC = read_binary_file<int8_t>(fileOutPath);

        // Reference C
        std::vector<int8_t> raw_refC = read_binary_file<int8_t>(fileRefPath);
        if (ctx.C_row <= 0 || ctx.C_col <= 0) ctx.refC = raw_refC;
        else ctx.refC = data_formatting(raw_refC, ctx.C_row, ctx.C_col, block_size, out_square);

        // Instructions & UOPs
        ctx.uop_buffer = read_binary_file<uop_t>(fileUopPath);
        ctx.insn_buffer = read_binary_file<instruction_t>(fileInsnPath);

        // ALLOCATE VTA MEMORY
        ctx.mem_inpA = VTAMemAlloc(ctx.inpA.size() * sizeof(int8_t), 1);
        ctx.mem_wgtB = VTAMemAlloc(ctx.wgtB.size() * sizeof(int8_t), 1);
        ctx.mem_accX = VTAMemAlloc(ctx.accX.size() * sizeof(int32_t), 1);
        ctx.mem_accY = VTAMemAlloc(ctx.accY.size() * sizeof(int32_t), 1);
        ctx.mem_outC = VTAMemAlloc(ctx.outC.size() * sizeof(int8_t), 1);
        ctx.mem_uop  = VTAMemAlloc(ctx.uop_buffer.size() * sizeof(uop_t), 1);
        ctx.mem_insn = VTAMemAlloc(ctx.insn_buffer.size() * sizeof(instruction_t), 1);

        // GET PHYSICAL ADDRESSES
        ctx.phy_add_insn = VTAMemGetPhyAddr(ctx.mem_insn);
        // Note: You can get others here if you need to debug print them, 
        // but typically only the instruction PHY address is passed to DeviceRun directly
        // assuming the instructions themselves contain the phy offsets for other buffers.
        
        // COPY TO DEVICE
        VTAMemCopyFromHost(ctx.mem_inpA, ctx.inpA.data(), ctx.inpA.size() * sizeof(int8_t));
        VTAMemCopyFromHost(ctx.mem_wgtB, ctx.wgtB.data(), ctx.wgtB.size() * sizeof(int8_t));
        VTAMemCopyFromHost(ctx.mem_accX, ctx.accX.data(), ctx.accX.size() * sizeof(int32_t));
        VTAMemCopyFromHost(ctx.mem_accY, ctx.accY.data(), ctx.accY.size() * sizeof(int32_t));
        VTAMemCopyFromHost(ctx.mem_outC, ctx.outC.data(), ctx.outC.size() * sizeof(int8_t));
        VTAMemCopyFromHost(ctx.mem_uop,  ctx.uop_buffer.data(), ctx.uop_buffer.size() * sizeof(uop_t));
        VTAMemCopyFromHost(ctx.mem_insn, ctx.insn_buffer.data(), ctx.insn_buffer.size() * sizeof(instruction_t));

        // Add to list
        layers.push_back(ctx);
    }

    // 3. PROFILER SETUP
    // -----------------
    const tvm::runtime::PackedFunc* profiler_clear = tvm::runtime::Registry::Get("vta.simulator.profiler_clear");
    const tvm::runtime::PackedFunc* profiler_status = tvm::runtime::Registry::Get("vta.simulator.profiler_status");
    const tvm::runtime::PackedFunc* profiler_debug_mode = tvm::runtime::Registry::Get("vta.simulator.profiler_debug_mode");

    if (!profiler_clear || !profiler_status || !profiler_debug_mode) {
        std::cerr << "ERROR: Profiler functions not found." << std::endl;
        return -1;
    }
    (*profiler_clear)();
    int debug_flag = 0; 
    (*profiler_debug_mode)(debug_flag);


    // 4. EXECUTE ALL LAYERS
    // ---------------------
    VTADeviceHandle vta_device = VTADeviceAlloc(); // Allocate device handle once

    for (const auto& ctx : layers) {
        if (debug) printf("DEBUG: Executing Layer %d...\n", ctx.id);
        
        int flag = VTADeviceRun(vta_device, ctx.phy_add_insn, ctx.insn_buffer.size(), 0);
        
        if (flag != 0) {
            std::cerr << "ERROR: Execution failed at layer " << ctx.id << std::endl;
            VTADeviceFree(vta_device);
            return EXIT_FAILURE;
        }
    }


    // 5. READ BACK, VERIFY AND FREE ALL LAYERS
    // ----------------------------------------
    if (debug) {
        std::string profile_json = (*profiler_status)();
        std::cout << "\n--- Profiler Status ---" << std::endl << profile_json << std::endl;
    }

    bool allCorrect = true;

    for (int i = 0; i < nb_vta_ir; ++i) {
        LayerContext& ctx = layers[i]; // Use reference to modify if needed, though vectors are inside
        
        // Copy Result Back
        VTAMemCopyToHost(ctx.outC.data(), ctx.mem_outC, ctx.outC.size() * sizeof(int8_t));

        // Optional: Copy others back if needed for debug
        // VTAMemCopyToHost(ctx.inpA.data(), ctx.mem_inpA, ctx.inpA.size() * sizeof(int8_t));

        // Compare
        bool layerCorrect = compare_vector(ctx.outC.data(), ctx.refC.data(), ctx.outC.size());
        if (!layerCorrect) {
            printf("FAILURE: Layer %d Output mismatch!\n", ctx.id);
            allCorrect = false;
        } else {
            if (debug) printf("SUCCESS: Layer %d matches reference.\n", ctx.id);
        }
        
        if (doPrint || !layerCorrect) {
            printf("\n\nRESULT LAYER %d:\n", ctx.id);
            printf("Final result = {");
            print_int8_vector(ctx.outC.data(), ctx.outC.size());
            printf("\n} \n");
        }

        // Free Memory
        VTAMemFree(ctx.mem_inpA);
        VTAMemFree(ctx.mem_wgtB);
        VTAMemFree(ctx.mem_accX);
        VTAMemFree(ctx.mem_accY);
        VTAMemFree(ctx.mem_outC);
        VTAMemFree(ctx.mem_uop);
        VTAMemFree(ctx.mem_insn);
    }

    VTADeviceFree(vta_device);

    if (allCorrect) return EXIT_SUCCESS;
    else return EXIT_FAILURE;
}

/****************
    MAIN FUNCTION
*****************/
int main() {
    return execute_simulator();
}