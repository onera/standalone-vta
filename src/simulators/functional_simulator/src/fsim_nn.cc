/***************************
    PRE-PROCESSOR DIRECTIVES
****************************/
#include "../include/simulator_header.h"
#include "../external_lib/tvm/packed_func.h"
#include "../external_lib/tvm/registry.h"
#include <vector>
#include <string>
#include <iostream>
#include <unordered_map>

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
    FSIM_NN
*********************/
int fsim_nn() {
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

    // Map to store layers by name
    std::unordered_map<std::string, LayerContext> layers_map;
    layers_map.reserve(nb_vta_ir); // Optionnal
    // List to keep the default load order
    std::vector<std::string> loaded_layer_names;
    loaded_layer_names.reserve(nb_vta_ir); // Optionnal


    // 2. LOAD AND ALLOCATE ALL LAYERS
    // -------------------------------
    int block_size;
    for (int i = 0; i < nb_vta_ir; ++i) {
        LayerContext ctx;
        ctx.id = i;

        // Get Suffix for this specific layer (column "0", "1", "2"...)
        ctx.suffix = getCsvElementByName(fileLayerNamePath, std::to_string(i), 1);
        
        if (debug) printf("\n--- Loading Layer %d (Suffix: %s) ---\n", i, ctx.suffix.c_str());

        // READ METADATA
        std::string fileMetadataPath = construct_path("metadata" + ctx.suffix + ".csv");

        std::string block_size_str = getCsvElementByName(fileMetadataPath, "BS", 2);
        block_size = strToInt(block_size_str);

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
        
        // COPY TO DEVICE
        VTAMemCopyFromHost(ctx.mem_inpA, ctx.inpA.data(), ctx.inpA.size() * sizeof(int8_t));
        VTAMemCopyFromHost(ctx.mem_wgtB, ctx.wgtB.data(), ctx.wgtB.size() * sizeof(int8_t));
        VTAMemCopyFromHost(ctx.mem_accX, ctx.accX.data(), ctx.accX.size() * sizeof(int32_t));
        VTAMemCopyFromHost(ctx.mem_accY, ctx.accY.data(), ctx.accY.size() * sizeof(int32_t));
        VTAMemCopyFromHost(ctx.mem_outC, ctx.outC.data(), ctx.outC.size() * sizeof(int8_t));
        VTAMemCopyFromHost(ctx.mem_uop,  ctx.uop_buffer.data(), ctx.uop_buffer.size() * sizeof(uop_t));
        VTAMemCopyFromHost(ctx.mem_insn, ctx.insn_buffer.data(), ctx.insn_buffer.size() * sizeof(instruction_t));

        // Stock in the map
        layers_map[ctx.suffix] = ctx;
        // Keep the load order
        loaded_layer_names.push_back(ctx.suffix);
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

    
    // 4. DEFINE THE EXECUTION ORDER AND INFO
    // --------------------------------------
    std::string fileDependencyPath = construct_path("dependency.csv");
    std::string nb_steps_str = getCsvElementByName(fileDependencyPath, "nb_steps", 1);
    // Clean the variable for robust comparison
    nb_steps_str.erase(std::remove(nb_steps_str.begin(), nb_steps_str.end(), '\n'), nb_steps_str.end());
    nb_steps_str.erase(std::remove(nb_steps_str.begin(), nb_steps_str.end(), '\r'), nb_steps_str.end());
    nb_steps_str.erase(std::remove(nb_steps_str.begin(), nb_steps_str.end(), ' '), nb_steps_str.end());
    // Convert in integer
    int nb_steps = strToInt(nb_steps_str);

    if (debug) printf("\n\nDEBUG: There are %d steps: \n", nb_steps);
        

    // // Define the execution order
    // // -> Default order: std::vector<std::string>& execution_order = loaded_layer_names;
    std::vector<std::string> execution_order;
    execution_order.reserve(nb_steps); // Optionnal

    for (int i = 0; i < nb_steps; ++i) {
        // Get the name
       std::string layer_to_execute = getCsvElementByName(fileDependencyPath, std::to_string(i), 2);
       // Clean
       layer_to_execute.erase(std::remove(layer_to_execute.begin(), layer_to_execute.end(), '\n'), layer_to_execute.end());
       layer_to_execute.erase(std::remove(layer_to_execute.begin(), layer_to_execute.end(), '\r'), layer_to_execute.end());
       layer_to_execute.erase(std::remove(layer_to_execute.begin(), layer_to_execute.end(), ' '), layer_to_execute.end());

       // Add to the execution order
       execution_order.push_back(layer_to_execute);
    }



    // 5. EXECUTE ALL LAYERS (in execution_order)
    // ---------------------
    VTADeviceHandle vta_device = VTADeviceAlloc(); // Allocate device handle once

    for (const std::string& layer_name : execution_order) {
        // Check that the layer exists
        if (layers_map.find(layer_name) == layers_map.end()) {
            std::cerr << "ERROR: Layer " << layer_name << " not found!" << std::endl;
            continue; 
        }

        // Get the layer
        LayerContext& ctx = layers_map[layer_name];

        // Print the execution order
        if (debug) printf("\n--- Executing Layer: %s (ID: %d) --- \n", ctx.suffix.c_str(), ctx.id);

        // Get layer information
        std::string doReshape = getCsvElementByName(fileDependencyPath, ctx.suffix.c_str(), 4);


        // Perform chaining and data reorganisation
        if (doReshape == "int32"){

            if (debug) printf("\t %s: ", doReshape.c_str());

            // Get number of input 
            std::string nb_inp_str = getCsvElementByName(fileDependencyPath, ctx.suffix.c_str(), 14);
            int nb_inp = strToInt(nb_inp_str);

            if (debug) printf("%d inputs ", nb_inp);

            // Perform the reshaping
            if (nb_inp >= 2) {
                // Get the names
                std::string name_dep1 = getCsvElementByName(fileDependencyPath, ctx.suffix.c_str(), 15);
                std::string name_dep2 = getCsvElementByName(fileDependencyPath, ctx.suffix.c_str(), 16);
                // Clean
                name_dep2.erase(std::remove(name_dep2.begin(), name_dep2.end(), '\n'), name_dep2.end());
                name_dep2.erase(std::remove(name_dep2.begin(), name_dep2.end(), '\r'), name_dep2.end());
                name_dep2.erase(std::remove(name_dep2.begin(), name_dep2.end(), ' '), name_dep2.end());

                if (debug) printf("(%s, %s) \n", name_dep1.c_str(), name_dep2.c_str());

                // Get the previous layers
                LayerContext& dep1_ctx = layers_map[name_dep1];
                std::vector<int8_t> dep1_out = dep1_ctx.outC;
                LayerContext& dep2_ctx = layers_map[name_dep2];
                std::vector<int8_t> dep2_out = dep2_ctx.outC;

                // Reshape 
                std::vector<int32_t> reshaped_dep1 = convert_vector_type<int32_t>(dep1_out);
                std::vector<int32_t> reshaped_dep2 = convert_vector_type<int32_t>(dep2_out);

                // Chain
                ctx.accX = reshaped_dep1;
                ctx.accY = reshaped_dep2;

                // Write the vector in memory
                VTAMemCopyFromHost(ctx.mem_accX, ctx.accX.data(), ctx.accX.size() * sizeof(int32_t));
                VTAMemCopyFromHost(ctx.mem_accY, ctx.accY.data(), ctx.accY.size() * sizeof(int32_t));
            }
            else if (nb_inp == 1){
                // Get the names
                std::string name_dep = getCsvElementByName(fileDependencyPath, ctx.suffix.c_str(), 15);
                // Clean
                name_dep.erase(std::remove(name_dep.begin(), name_dep.end(), '\n'), name_dep.end());
                name_dep.erase(std::remove(name_dep.begin(), name_dep.end(), '\r'), name_dep.end());
                name_dep.erase(std::remove(name_dep.begin(), name_dep.end(), ' '), name_dep.end());

                if (debug) printf("(%s) \n", name_dep.c_str());

                // Get the previous layers
                LayerContext& dep_ctx = layers_map[name_dep];
                std::vector<int8_t> dep_out = dep_ctx.outC;

                // Reshape 
                std::vector<int32_t> reshaped_dep = convert_vector_type<int32_t>(dep_out);

                // Chain
                ctx.accX = reshaped_dep;

                // Write the vector in memory
                VTAMemCopyFromHost(ctx.mem_accX, ctx.accX.data(), ctx.accX.size() * sizeof(int32_t));
            }
        }
        else if (doReshape == "True"){
            if (debug) printf("\t %s: ", doReshape.c_str());

            // Get number of input 
            std::string nb_inp_str = getCsvElementByName(fileDependencyPath, ctx.suffix.c_str(), 14);
            int nb_inp = strToInt(nb_inp_str);

            if (debug) printf("%d inputs ", nb_inp);

            // Get the names
            std::string name_dep = getCsvElementByName(fileDependencyPath, ctx.suffix.c_str(), 15);
            // Clean
            name_dep.erase(std::remove(name_dep.begin(), name_dep.end(), '\n'), name_dep.end());
            name_dep.erase(std::remove(name_dep.begin(), name_dep.end(), '\r'), name_dep.end());
            name_dep.erase(std::remove(name_dep.begin(), name_dep.end(), ' '), name_dep.end());

            if (debug) printf("(%s) \n", name_dep.c_str());

            // Get the previous layers
            LayerContext& dep_ctx = layers_map[name_dep];
            std::vector<int8_t> dep_out = dep_ctx.outC;

            // Get other information
            // Channel
            std::string tensor_channel_str = getCsvElementByName(fileDependencyPath, ctx.suffix.c_str(), 1);
            int tensor_channel = strToInt(tensor_channel_str);
            // Height
            std::string tensor_height_str = getCsvElementByName(fileDependencyPath, ctx.suffix.c_str(), 2);
            int tensor_height = strToInt(tensor_height_str);
            // Width
            std::string tensor_width_str = getCsvElementByName(fileDependencyPath, ctx.suffix.c_str(), 3);
            int tensor_width = strToInt(tensor_width_str);
            // Kernel
            std::string kh_str = getCsvElementByName(fileDependencyPath, ctx.suffix.c_str(), 5);
            int kh = strToInt(kh_str);
            std::string kw_str = getCsvElementByName(fileDependencyPath, ctx.suffix.c_str(), 6);
            int kw = strToInt(kw_str);
            // Stride
            std::string sh_str = getCsvElementByName(fileDependencyPath, ctx.suffix.c_str(), 7);
            int sh = strToInt(sh_str);
            // std::string sw_str = getCsvElementByName(fileDependencyPath, ctx.suffix.c_str(), 8);
            // int sw = strToInt(sw_str);
            // Padding
            std::string p0_str = getCsvElementByName(fileDependencyPath, ctx.suffix.c_str(), 9);
            int p0 = strToInt(p0_str);
            std::string p1_str = getCsvElementByName(fileDependencyPath, ctx.suffix.c_str(), 10);
            int p1 = strToInt(p1_str);
            std::string p2_str = getCsvElementByName(fileDependencyPath, ctx.suffix.c_str(), 11);
            int p2 = strToInt(p2_str);
            std::string p3_str = getCsvElementByName(fileDependencyPath, ctx.suffix.c_str(), 12);
            int p3 = strToInt(p3_str);

            // Reshape
            std::vector<int8_t> reshaped_result = reshape(
                dep_out, //prev_vector
                block_size, // block_size
                1, // batch_size
                tensor_channel, // tensor_channel
                tensor_height, // tensor_height
                tensor_width, // tensor_width
                {kh,kw}, // kernel_size (pair)
                sh, // stride
                {p0,p1,p2,p3}, // padding (vector)
                true // isSquare
            );
                
            // Give the reshaped result to the input
            ctx.inpA = reshaped_result;
            VTAMemCopyFromHost(ctx.mem_inpA, ctx.inpA.data(), ctx.inpA.size() * sizeof(int8_t));
        }
        
        // Execute the layer
        int flag = VTADeviceRun(vta_device, ctx.phy_add_insn, ctx.insn_buffer.size(), 0);
        
        // Check the execution was successful
        if (flag != 0) {
            std::cerr << "ERROR: Execution failed at layer " << ctx.suffix << std::endl;
            VTADeviceFree(vta_device);
            return EXIT_FAILURE;
        }
        
        // Copy Result Back
        VTAMemCopyToHost(ctx.outC.data(), ctx.mem_outC, ctx.outC.size() * sizeof(int8_t));
    }


    // 6. FREE ALL LAYERS
    // ------------------
    if (debug) {
        std::string profile_json = (*profiler_status)();
        std::cout << "\n--- Profiler Status ---" << std::endl << profile_json << std::endl;
    }

    for (auto& pair : layers_map) {
        LayerContext& ctx = pair.second; // Use reference to modify if needed, though vectors are inside

        // Free Memory
        VTAMemFree(ctx.mem_inpA);
        VTAMemFree(ctx.mem_wgtB);
        VTAMemFree(ctx.mem_accX);
        VTAMemFree(ctx.mem_accY);
        VTAMemFree(ctx.mem_outC);
        VTAMemFree(ctx.mem_uop);
        VTAMemFree(ctx.mem_insn);
    }

    // Free the VTA
    VTADeviceFree(vta_device);


    // 7. COMPARE / CHECK
    // ------------------
    bool isCorrect = true;

    // Get the last name
    std::string last_step = getCsvElementByName(fileDependencyPath, std::to_string(nb_steps - 1), 2);
    // Clean
    last_step.erase(std::remove(last_step.begin(), last_step.end(), '\n'), last_step.end());
    last_step.erase(std::remove(last_step.begin(), last_step.end(), '\r'), last_step.end());
    last_step.erase(std::remove(last_step.begin(), last_step.end(), ' '), last_step.end());

    // Get the layer
    LayerContext& ctx = layers_map[last_step];

    // isCorrect = compare_vector(ctx.outC.data(), ctx.refC.data(), ctx.outC.size());

    if (doPrint || !isCorrect) {
        printf("\n\nRESULT LAYER %d:\n", ctx.id);
        printf("Final result = {");
        print_int8_vector(ctx.outC.data(), ctx.outC.size());
        printf("\n} \n");
    }

    // Return OK or KO
    if (isCorrect) return EXIT_SUCCESS;
    else return EXIT_FAILURE;
}

/****************
    MAIN FUNCTION
*****************/
int main() {
    return fsim_nn();
}