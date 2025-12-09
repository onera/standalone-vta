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
    
    // Buffers (Host side)
    std::vector<int8_t> inpA, wgtB, res;
    std::vector<int32_t> outC, accX, accY;
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

    // 0. DEFINE GLOBAL FILE PATHES
    // ----------------------------
    // Layer name with base info
    std::string fileLayerNamePath = construct_path("layers_name.csv");
    CsvMap layers_name_map = load_csv_to_map(fileLayerNamePath);

    // Dependency file
    std::string fileDependencyPath = construct_path("dependency.csv");
    CsvMap dependency_map = load_csv_to_map(fileDependencyPath);

    // Input file
    std::string fileInputNNPath = construct_path("input_nn.bin");

    // Output file
    std::string fileFinalOutputPath = construct_path("final_output.bin");


    // 1. GET NUMBER OF LAYERS AND THE DEBUG FLAG
    // ------------------------------------------
    // Get the number of VTA IRs
    int nb_vta_ir = strToInt(get_csv_value(layers_name_map, "nb_vta_ir", 1));

    // Get the debug flag (print option)
    std::string debug_str = get_csv_value(layers_name_map, "nb_vta_ir", 2);
    bool debug = (debug_str == "True");

    if (debug) printf("Found %d layers to execute.\n", nb_vta_ir);

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

        // A. GET SUFFIX OF THE CURRENT LAYER
        // ---
        ctx.suffix = get_csv_value(layers_name_map, std::to_string(i), 1);
        
        if (debug) printf("\n--- Loading Layer %d (Suffix: %s) ---\n", i, ctx.suffix.c_str());


        // B. LOAD LAYER-RELATED FILES
        // ----
        // Layer general information (create a MAP)
        std::string fileMetadataPath = construct_path("metadata" + ctx.suffix + ".csv");
        CsvMap metadata_map = load_csv_to_map(fileMetadataPath);

        // Binaries
        std::string fileInpPath = construct_path("input" + ctx.suffix + ".bin");
        std::string fileWgtPath = construct_path("weight" + ctx.suffix + ".bin");
        std::string fileAccPath = construct_path("accumulator" + ctx.suffix + ".bin");
        std::string fileAddAccPath = construct_path("add_accumulator" + ctx.suffix + ".bin");
        std::string fileOutPath = construct_path("output" + ctx.suffix + ".bin");
        std::string fileUopPath = construct_path("uop" + ctx.suffix + ".bin");
        std::string fileInsnPath = construct_path("instructions" + ctx.suffix + ".bin");


        // C. READ METADATA INFO
        // ---
        // Block size and square
        block_size = strToInt(get_csv_value(metadata_map, "BS", 2));
        // std::string out_square_str = get_csv_value(metadata_map, "BS", 1);
        // bool out_square = (out_square_str == "True");

        // Dimensions
        int A_row = strToInt(get_csv_value(metadata_map, "A", 1));
        int A_col = strToInt(get_csv_value(metadata_map, "A", 2));
        int X_row = strToInt(get_csv_value(metadata_map, "X", 1));
        int X_col = strToInt(get_csv_value(metadata_map, "X", 2));
        int Y_row = strToInt(get_csv_value(metadata_map, "Y", 1));
        int Y_col = strToInt(get_csv_value(metadata_map, "Y", 2));

        
        // D. READ AND SHAPE THE DATA
        // ---
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
        ctx.outC = read_binary_file<int32_t>(fileOutPath);

        // Instructions & UOPs
        ctx.uop_buffer = read_binary_file<uop_t>(fileUopPath);
        ctx.insn_buffer = read_binary_file<instruction_t>(fileInsnPath);


        // E. ALLOCATE VTA MEMORY (virtual DRAM)
        // ---
        ctx.mem_inpA = VTAMemAlloc(ctx.inpA.size() * sizeof(int8_t), 1);
        ctx.mem_wgtB = VTAMemAlloc(ctx.wgtB.size() * sizeof(int8_t), 1);
        ctx.mem_accX = VTAMemAlloc(ctx.accX.size() * sizeof(int32_t), 1);
        ctx.mem_accY = VTAMemAlloc(ctx.accY.size() * sizeof(int32_t), 1);
        ctx.mem_outC = VTAMemAlloc(ctx.outC.size() * sizeof(int32_t), 1);
        ctx.mem_uop  = VTAMemAlloc(ctx.uop_buffer.size() * sizeof(uop_t), 1);
        ctx.mem_insn = VTAMemAlloc(ctx.insn_buffer.size() * sizeof(instruction_t), 1);

        // Get physical address for instructions
        ctx.phy_add_insn = VTAMemGetPhyAddr(ctx.mem_insn);
        

        // F. WRITE THE DATA IN VIRTUAL DRAM
        // ---
        VTAMemCopyFromHost(ctx.mem_inpA, ctx.inpA.data(), ctx.inpA.size() * sizeof(int8_t));
        VTAMemCopyFromHost(ctx.mem_wgtB, ctx.wgtB.data(), ctx.wgtB.size() * sizeof(int8_t));
        VTAMemCopyFromHost(ctx.mem_accX, ctx.accX.data(), ctx.accX.size() * sizeof(int32_t));
        VTAMemCopyFromHost(ctx.mem_accY, ctx.accY.data(), ctx.accY.size() * sizeof(int32_t));
        VTAMemCopyFromHost(ctx.mem_outC, ctx.outC.data(), ctx.outC.size() * sizeof(int32_t));
        VTAMemCopyFromHost(ctx.mem_uop,  ctx.uop_buffer.data(), ctx.uop_buffer.size() * sizeof(uop_t));
        VTAMemCopyFromHost(ctx.mem_insn, ctx.insn_buffer.data(), ctx.insn_buffer.size() * sizeof(instruction_t));


        // G. STOCK THE LAYER IN THE MAP AND PUSH
        // ---
        // Stock in the map
        layers_map[ctx.suffix] = ctx;
        // Keep the load order
        loaded_layer_names.push_back(ctx.suffix);
    }

    // H. READ THE INPUT
    // ---
    // std::vector<int8_t> input_nn = read_binary_file<int8_t>(fileInputNNPath);

    // // Get the information about the input
    // int input_nn_height = strToInt(get_csv_value(dependency_map, "image", 1));
    // int input_nn_width = strToInt(get_csv_value(dependency_map, "image", 2));

    // // TODO: TO FIX -> Warning: Input vector was larger than target matrix (65536x32). Input data has been truncated. \n terminate called after throwing an instance of 'tvm::runtime::InternalError'
    // // // Format the input
    // // input_nn = data_formatting(input_nn, input_nn_height, input_nn_width, block_size, true);


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

    
    // 4. DEFINE THE EXECUTION ORDER AND LAYER INFO
    // --------------------------------------------
    // Get the number of steps
    int nb_steps = strToInt(get_csv_value(dependency_map, "nb_steps", 1));

    if (debug) printf("\n\nThere are %d steps: \n", nb_steps);

    // Define the execution order
    std::vector<std::string> execution_order;
    execution_order.reserve(nb_steps); 

    for (int i = 0; i < nb_steps; ++i) {
        // Get the name
       std::string layer_to_execute = get_csv_value(dependency_map, std::to_string(i), 2);

       // Add to the execution order
       execution_order.push_back(layer_to_execute);
    }



    // 5. EXECUTE ALL LAYERS (in execution_order)
    // ---------------------
    // Allocate the VTA device
    VTADeviceHandle vta_device = VTADeviceAlloc();

    // Iterate over the execution order
    for (const std::string& layer_name : execution_order) {
        // Check that the layer exists
        if (layers_map.find(layer_name) == layers_map.end()) {
            std::cerr << "ERROR: Layer " << layer_name << " not found!" << std::endl;
            continue; 
        }


        // A. GET THE CURRENT LAYER TO EXECUTE
        // ---
        // The layer to execute
        LayerContext& ctx = layers_map[layer_name];

        if (debug) printf("\n--- Executing Layer: %s (ID: %d) --- \n", ctx.suffix.c_str(), ctx.id);


        // B. GET THE LAYER INFORMATION
        // ---
        // Reshape
        std::string reshape_info = get_csv_value(dependency_map, ctx.suffix.c_str(), 1);

        if (debug) printf("\t Reshape to perform: %s \n", reshape_info.c_str());

        // Offsets (A, B, C)
        int offsetA = strToInt(get_csv_value(dependency_map, ctx.suffix.c_str(), 2));
        int offsetB = strToInt(get_csv_value(dependency_map, ctx.suffix.c_str(), 3));
        // Out
        int offsetC = strToInt(get_csv_value(dependency_map, ctx.suffix.c_str(), 19));

        // INPUT tensor shape
        int tensor_channel = strToInt(get_csv_value(dependency_map, ctx.suffix.c_str(), 4));
        int tensor_height = strToInt(get_csv_value(dependency_map, ctx.suffix.c_str(), 5));
        int tensor_width = strToInt(get_csv_value(dependency_map, ctx.suffix.c_str(), 6));

        // // OUTPUT tensor shape
        // int out_tensor_channel = strToInt(get_csv_value(dependency_map, ctx.suffix.c_str(), 15));
        // int out_tensor_height = strToInt(get_csv_value(dependency_map, ctx.suffix.c_str(), 16));
        // int out_tensor_width = strToInt(get_csv_value(dependency_map, ctx.suffix.c_str(), 17));

        // Kernel
        int kh = strToInt(get_csv_value(dependency_map, ctx.suffix.c_str(), 7));
        int kw = strToInt(get_csv_value(dependency_map, ctx.suffix.c_str(), 8));

        // Stride
        int sh = strToInt(get_csv_value(dependency_map, ctx.suffix.c_str(), 9));
        // int sw = strToInt(get_csv_value(dependency_map, ctx.suffix.c_str(), 10));

        // Padding
        int p0 = strToInt(get_csv_value(dependency_map, ctx.suffix.c_str(), 11));
        int p1 = strToInt(get_csv_value(dependency_map, ctx.suffix.c_str(), 12));
        int p2 = strToInt(get_csv_value(dependency_map, ctx.suffix.c_str(), 13));
        int p3 = strToInt(get_csv_value(dependency_map, ctx.suffix.c_str(), 14));

        // Rescaling factor
        float scale = strToFloat(get_csv_value(dependency_map, ctx.suffix.c_str(), 18));

        // Nb of inputs
        int nb_inp = strToInt(get_csv_value(dependency_map, ctx.suffix.c_str(), 21));

        if (debug) printf("\t %d inputs: ", nb_inp);

        if (nb_inp < 1 || nb_inp > 2) {
            std::cerr << "ERROR: To many inputs for layer " << ctx.suffix << std::endl;
            return EXIT_FAILURE;
        }

        // Inputs
        // ---
        std::string name_dep = get_csv_value(dependency_map, ctx.suffix.c_str(), 22);
        if (debug) printf("%s", name_dep);
        std::string name_dep2;
        if (nb_inp == 2){
            name_dep2 = get_csv_value(dependency_map, ctx.suffix.c_str(), 23);
            if (debug) printf(", %s", name_dep2);
        } 
        if (debug) printf("\n");

        // // Get previous layer
        // // TODO: THROUGH CORE DUMP (bug to fix)
        // // if (name_dep == "image"){
        // //     dep_out = input_nn;
        // //     if (nb_inp != 1) {
        // //         std::cerr << "ERROR: Expect only a single input " << std::endl;
        // //         return EXIT_FAILURE;
        // //     }
        // // }
        // // else {
        // //     // We get the address of the previous layer
        // //     dep_ctx = &layers_map[name_dep];
        // //     dep_out = dep_ctx->res; 
        // //     if (nb_inp == 2) {
        // //         dep2_ctx = &layers_map[name_dep2];
        // //         dep2_out = dep2_ctx->res;
        // //     }
        // // }


        // C. RE-ORGANISE THE DATA
        // ---
        // Perform chaining and data reorganisation
        if (reshape_info == "int32"){
            // If there is a single input
            if (nb_inp == 1){
                // Get the previous layer
                LayerContext& dep_ctx = layers_map[name_dep];
                std::vector<int8_t> dep_out = dep_ctx.res;

                // Offset + Reshape 
                if (offsetA != 0){
                    dep_out = subtract_offset(dep_out, offsetA);
                }
                std::vector<int32_t> reshaped_dep = convert_vector_type<int32_t>(dep_out);

                // Chain
                ctx.accX = reshaped_dep;

                // Write the vector in memory
                VTAMemCopyFromHost(ctx.mem_accX, ctx.accX.data(), ctx.accX.size() * sizeof(int32_t));
            }

            // There are two inputs
            else if (nb_inp == 2) {
                // Get the previous layers
                LayerContext& dep_ctx = layers_map[name_dep];
                std::vector<int8_t> dep_out = dep_ctx.res;

                LayerContext& dep2_ctx = layers_map[name_dep2];
                std::vector<int8_t> dep2_out = dep2_ctx.res;

                // Offset + reshape 
                if (offsetA != 0){
                    dep_out = subtract_offset(dep_out, offsetA);
                }
                std::vector<int32_t> reshaped_dep1 = convert_vector_type<int32_t>(dep_out);

                if (offsetB != 0){
                    dep2_out = subtract_offset(dep2_out, offsetB);
                }
                std::vector<int32_t> reshaped_dep2 = convert_vector_type<int32_t>(dep2_out);

                // Chain
                ctx.accX = reshaped_dep1;
                ctx.accY = reshaped_dep2;

                // Write the vector in memory
                VTAMemCopyFromHost(ctx.mem_accX, ctx.accX.data(), ctx.accX.size() * sizeof(int32_t));
                VTAMemCopyFromHost(ctx.mem_accY, ctx.accY.data(), ctx.accY.size() * sizeof(int32_t));
            }
        }

        else if (reshape_info == "im2row"){
            // Get the previous layers
            LayerContext& dep_ctx = layers_map[name_dep];
            std::vector<int8_t> dep_out = dep_ctx.res;

            // Reshape
            ctx.inpA  = reshape(
                dep_out, // prev_vector (int32_t)
                block_size, // block_size
                1, // batch_size
                tensor_channel, // tensor_channel
                tensor_height, // tensor_height
                tensor_width, // tensor_width
                {kh,kw}, // kernel_size (pair)
                sh, // stride
                {p0,p1,p2,p3}, // padding (vector)
                true, // isSquare
                offsetA // offset
            );
                
            // Copy the data
            VTAMemCopyFromHost(ctx.mem_inpA, ctx.inpA.data(), ctx.inpA.size() * sizeof(int8_t));
        }


        // D. EXECUTE THE VTA
        // ---
        // Execute the layer
        int flag = VTADeviceRun(vta_device, ctx.phy_add_insn, ctx.insn_buffer.size(), 0);
        
        // Check the execution was successful
        if (flag != 0) {
            std::cerr << "ERROR: Execution failed at layer " << ctx.suffix << std::endl;
            VTADeviceFree(vta_device);
            return EXIT_FAILURE;
        }
        

        // E. GET THE RESULT BACK
        // ---
        // Copy Result Back
        VTAMemCopyToHost(ctx.outC.data(), ctx.mem_outC, ctx.outC.size() * sizeof(int32_t));


        // F. RESCALE THE RESULT
        // ---
        if (debug) printf("\nRescaling: \n\t rescaling factor=%f and offset=%d \n", scale, offsetC);

        // Perform the rescaling
        ctx.res = rescaling(
            ctx.outC, // vector (int32)
            scale, // rescale_factor (float)
            offsetC // offset
        );

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


    // 7. WRITE RESULT IN BINARY
    // -------------------------
    // Get information about the output
    // Name
    std::string output_name = get_csv_value(dependency_map, "output", 1);
    // Output tensor shape
    int tensor_channel = strToInt(get_csv_value(dependency_map, "output", 2));
    int tensor_height = strToInt(get_csv_value(dependency_map, "output", 3));
    int tensor_width = strToInt(get_csv_value(dependency_map, "output", 4));

    // Get the layer
    LayerContext& ctx = layers_map[output_name];

    // Print if requested
    if (doPrint) {
        printf("\n\nRESULT LAYER %d:\n", ctx.id);
        printf("Final result = {");
        print_int8_vector(ctx.res.data(), ctx.res.size());
        printf("\n} \n");
    }

    // Write result
    output_tensor(
        ctx.res, // output vector
        block_size, // block_size
        1, // batch_size
        tensor_channel, // tensor_channel
        tensor_height, // tensor_height
        tensor_width, // tensor_width
        fileFinalOutputPath // filepath
    );

    // Return OK
    return EXIT_SUCCESS;
}

/****************
    MAIN FUNCTION
*****************/
int main() {
    return fsim_nn();
}