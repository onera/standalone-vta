/***************************
    PRE-PROCESSOR DIRECTIVES
****************************/
#include "../include/simulator_header.h"

// Define the data type
using inp_dtype = int32_t;
using wgt_dtype = int32_t;
using acc_dtype = int32_t;

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
    std::vector<int8_t> res; // Result
    std::vector<float> value; // Float values

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
    // Get the number of steps / nodes
    int nb_steps = strToInt(get_csv_value(dependency_map, "nb_steps", 1));

    // Get the number of VTA IRs
    int nb_vta_ir = strToInt(get_csv_value(layers_name_map, "nb_vta_ir", 1));

    // Get the debug flag (print option)
    std::string debug_str = get_csv_value(layers_name_map, "nb_vta_ir", 2);
    bool debug = (debug_str == "True");

    if (debug) printf("\n\nThere are %d steps, %d are executed by the VTA! \n", nb_steps, nb_vta_ir);

    // Map to store layers by name
    std::unordered_map<std::string, LayerContext> layers_map;
    layers_map.reserve(nb_steps); // Each node has a map

    // List to keep the default load order
    std::vector<std::string> loaded_layer_names;
    loaded_layer_names.reserve(nb_vta_ir); // Only VTA nodes


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
        std::string fileWgtPath = construct_path("weight" + ctx.suffix + ".bin");
        std::string fileAccPath = construct_path("accumulator" + ctx.suffix + ".bin");
        std::string fileAddAccPath = construct_path("add_accumulator" + ctx.suffix + ".bin");
        std::string fileUopPath = construct_path("uop" + ctx.suffix + ".bin");
        std::string fileInsnPath = construct_path("instructions" + ctx.suffix + ".bin");


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
        std::vector<inp_dtype> raw_inpA; 
        if (A_row <= 0 || A_col <= 0) ctx.inpA = raw_inpA;
        else ctx.inpA = data_formatting(raw_inpA, A_row, A_col, block_size, true);

        // Weight B
        ctx.wgtB = read_binary_file<wgt_dtype>(fileWgtPath);

        // Acc X
        std::vector<acc_dtype> raw_accX = read_binary_file<acc_dtype>(fileAccPath);
        if (X_row <= 0 || X_col <= 0) ctx.accX = raw_accX;
        else ctx.accX = data_formatting(raw_accX, X_row, X_col, block_size, true);

        // Acc Y
        std::vector<acc_dtype> raw_accY = read_binary_file<acc_dtype>(fileAddAccPath);
        if (Y_row <= 0 || Y_col <= 0) ctx.accY = raw_accY;
        else ctx.accY = data_formatting(raw_accY, Y_row, Y_col, block_size, true);

        // Output C (buffer space)
        std::vector<inp_dtype> raw_outC;
        if (C_row <= 0 || C_col <= 0) ctx.outC = raw_outC;
        else ctx.outC = data_formatting(raw_outC, C_row, C_col, block_size, out_square);

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
        ctx.mem_uop  = VTAMemAlloc(ctx.uop_buffer.size() * sizeof(uop_t), 1);
        ctx.mem_insn = VTAMemAlloc(ctx.insn_buffer.size() * sizeof(instruction_t), 1);

        // Get physical address for instructions
        ctx.phy_add_insn = VTAMemGetPhyAddr(ctx.mem_insn);
        

        // F. WRITE THE DATA IN VIRTUAL DRAM
        // ---
        VTAMemCopyFromHost(ctx.mem_inpA, ctx.inpA.data(), ctx.inpA.size() * sizeof(inp_dtype));
        VTAMemCopyFromHost(ctx.mem_wgtB, ctx.wgtB.data(), ctx.wgtB.size() * sizeof(wgt_dtype));
        VTAMemCopyFromHost(ctx.mem_accX, ctx.accX.data(), ctx.accX.size() * sizeof(acc_dtype));
        VTAMemCopyFromHost(ctx.mem_accY, ctx.accY.data(), ctx.accY.size() * sizeof(acc_dtype));
        VTAMemCopyFromHost(ctx.mem_outC, ctx.outC.data(), ctx.outC.size() * sizeof(inp_dtype));
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
    std::vector<int8_t> input_nn = read_binary_file<int8_t>(fileInputNNPath);

    // Get the information about the input
    int input_nn_height = strToInt(get_csv_value(dependency_map, "image", 1));
    int input_nn_width = strToInt(get_csv_value(dependency_map, "image", 2));

    // Format the input
    input_nn = data_formatting(input_nn, input_nn_height, input_nn_width, block_size, true);


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

    // Define the execution order
    std::vector<std::string> execution_order;
    execution_order.reserve(nb_steps); 

    for (int i = 0; i < nb_steps; ++i) {
        // Get the name
        std::string layer_to_execute = get_csv_value(dependency_map, std::to_string(i), 2);
       
        // CHECK: Does this layer exist in the map?
        if (layers_map.find(layer_to_execute) == layers_map.end()) {
            // Create a new node
            LayerContext ctx;
            
            // Set basic info
            ctx.id = i; 
            ctx.suffix = layer_to_execute;

            // Insert into the map
            layers_map[layer_to_execute] = ctx;

            if (debug) printf("   -> Auto-created context for CPU layer: %s\n", layer_to_execute.c_str());
        }

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
        // Processor
        std::string processor = get_csv_value(dependency_map, ctx.suffix.c_str(), 1);
        // Reshape
        std::string reshape_info = get_csv_value(dependency_map, ctx.suffix.c_str(), 2);

        if (debug) printf("\t On %s with reshape %s \n", processor.c_str(), reshape_info.c_str());

        // Offsets (A, B, C)
        int offsetA = strToInt(get_csv_value(dependency_map, ctx.suffix.c_str(), 3));
        int offsetB = strToInt(get_csv_value(dependency_map, ctx.suffix.c_str(), 5));
        int offsetU = strToInt(get_csv_value(dependency_map, ctx.suffix.c_str(), 7));
        int offsetV = strToInt(get_csv_value(dependency_map, ctx.suffix.c_str(), 9));
        int offsetC = strToInt(get_csv_value(dependency_map, ctx.suffix.c_str(), 25));

        // Scale (A, B, C)
        float scaleA = strToFloat(get_csv_value(dependency_map, ctx.suffix.c_str(), 4));
        float scaleB = strToFloat(get_csv_value(dependency_map, ctx.suffix.c_str(), 6));
        float scaleU = strToFloat(get_csv_value(dependency_map, ctx.suffix.c_str(), 8));
        float scaleV = strToFloat(get_csv_value(dependency_map, ctx.suffix.c_str(), 10));
        float scaleC = strToFloat(get_csv_value(dependency_map, ctx.suffix.c_str(), 26));
        // Rescaling factor (Sa*Sb/Sc)
        float scale = strToFloat(get_csv_value(dependency_map, ctx.suffix.c_str(), 27));

        // INPUT tensor shape
        int tensor_channel = strToInt(get_csv_value(dependency_map, ctx.suffix.c_str(), 11));
        int tensor_height = strToInt(get_csv_value(dependency_map, ctx.suffix.c_str(), 12));
        int tensor_width = strToInt(get_csv_value(dependency_map, ctx.suffix.c_str(), 13));

        // OUTPUT tensor shape
        int out_tensor_channel = strToInt(get_csv_value(dependency_map, ctx.suffix.c_str(), 22));
        int out_tensor_height = strToInt(get_csv_value(dependency_map, ctx.suffix.c_str(), 23));
        int out_tensor_width = strToInt(get_csv_value(dependency_map, ctx.suffix.c_str(), 24));

        // Kernel
        int kh = strToInt(get_csv_value(dependency_map, ctx.suffix.c_str(), 14));
        int kw = strToInt(get_csv_value(dependency_map, ctx.suffix.c_str(), 15));

        // Stride
        int sh = strToInt(get_csv_value(dependency_map, ctx.suffix.c_str(), 16));
        // int sw = strToInt(get_csv_value(dependency_map, ctx.suffix.c_str(), 17));

        // Padding
        int p0 = strToInt(get_csv_value(dependency_map, ctx.suffix.c_str(), 18));
        int p1 = strToInt(get_csv_value(dependency_map, ctx.suffix.c_str(), 19));
        int p2 = strToInt(get_csv_value(dependency_map, ctx.suffix.c_str(), 20));
        int p3 = strToInt(get_csv_value(dependency_map, ctx.suffix.c_str(), 21));

        // Nb of inputs
        int nb_inp = strToInt(get_csv_value(dependency_map, ctx.suffix.c_str(), 29));

        if (debug) printf("\t %d inputs: ", nb_inp);

        if (nb_inp < 1 || nb_inp > 4) {
            std::cerr << "ERROR: Too many inputs for layer " << ctx.suffix << std::endl;
            return EXIT_FAILURE;
        }

        // Inputs
        // ---
        std::string name_dep, name_dep2, name_dep3, name_dep4;
        
        name_dep = get_csv_value(dependency_map, ctx.suffix.c_str(), 30);
        if (debug) printf("%s", name_dep.c_str());
        if (nb_inp == 2){
            name_dep2 = get_csv_value(dependency_map, ctx.suffix.c_str(), 31);
            if (debug) printf(", %s", name_dep2.c_str());
        } 
        else if (nb_inp == 3){
            name_dep2 = get_csv_value(dependency_map, ctx.suffix.c_str(), 31);
            if (debug) printf(", %s", name_dep2.c_str());
            name_dep3 = get_csv_value(dependency_map, ctx.suffix.c_str(), 32);
            if (debug) printf(", %s", name_dep3.c_str());
        } 
        else if (nb_inp == 4){
            name_dep2 = get_csv_value(dependency_map, ctx.suffix.c_str(), 31);
            if (debug) printf(", %s", name_dep2.c_str());
            name_dep3 = get_csv_value(dependency_map, ctx.suffix.c_str(), 32);
            if (debug) printf(", %s", name_dep3.c_str());
            name_dep4 = get_csv_value(dependency_map, ctx.suffix.c_str(), 33);
            if (debug) printf(", %s", name_dep4.c_str());
        } 
        if (debug) printf("\n");


        // C. RE-ORGANISE THE DATA
        // ---
        // Perform chaining and data reorganisation
        if (reshape_info == "int32"){
            // If there is a single input
            if (nb_inp == 1){
                // Get the previous layer
                std::vector<int8_t> dep_out;
                if (name_dep == "image"){
                    dep_out = input_nn;
                }
                else{
                    LayerContext& dep_ctx = layers_map[name_dep];
                    dep_out = dep_ctx.res;
                }

                // Rescale
                std::vector<acc_dtype> reshaped_dep = convert_vector_type<acc_dtype>(dep_out);

                // Offset 
                if (offsetA != 0){
                    reshaped_dep = subtract_offset(reshaped_dep, offsetA);
                }
                // Check if any padding is required (p0=Top, p1=Left, p2=Bottom, p3=Right)
                if (p0 > 0 || p1 > 0 || p2 > 0 || p3 > 0) {
                    if (debug) printf("\t -> Applying int32 padding: T=%d, L=%d, B=%d, R=%d\n", p0, p1, p2, p3);

                    reshaped_dep = pad_matrix(
                        reshaped_dep, // input_data
                        tensor_channel, // tensor_channel
                        tensor_height, // tensor_height
                        tensor_width, // tensor_width
                        block_size, // block_size
                        {p0, p1, p2, p3},// padding_vec
                        -128 // pad_value
                    );
                }

                // Chain
                ctx.accX = reshaped_dep;

                // Write the vector in memory
                if (ctx.mem_accX != nullptr) VTAMemCopyFromHost(ctx.mem_accX, ctx.accX.data(), ctx.accX.size() * sizeof(acc_dtype));
            }

            // There are two inputs
            else if (nb_inp == 2) {
                // Get the previous layers
                LayerContext& dep_ctx = layers_map[name_dep];
                std::vector<int8_t> dep_out = dep_ctx.res;

                LayerContext& dep2_ctx = layers_map[name_dep2];
                std::vector<int8_t> dep2_out = dep2_ctx.res;

                // Convert in int 32
                std::vector<acc_dtype> reshaped_dep1 = convert_vector_type<acc_dtype>(dep_out);
                std::vector<acc_dtype> reshaped_dep2 = convert_vector_type<acc_dtype>(dep2_out);

                // Offset 
                if (offsetA != 0){
                    reshaped_dep1 = subtract_offset(reshaped_dep1, offsetA);
                }

                if (offsetB != 0){
                    reshaped_dep2 = subtract_offset(reshaped_dep2, offsetB);
                }


                // PAD
                if (p0 > 0 || p1 > 0 || p2 > 0 || p3 > 0) {
                    if (debug) printf("\t -> Applying int32 padding: T=%d, L=%d, B=%d, R=%d\n", p0, p1, p2, p3);

                    reshaped_dep1 = pad_matrix(
                        reshaped_dep1, // input_data
                        tensor_channel, // tensor_channel
                        tensor_height, // tensor_height
                        tensor_width, // tensor_width
                        block_size, // block_size
                        {p0, p1, p2, p3},// padding_vec
                        -128 // pad_value
                    );

                    reshaped_dep2 = pad_matrix(
                        reshaped_dep2, // input_data
                        tensor_channel, // tensor_channel
                        tensor_height, // tensor_height
                        tensor_width, // tensor_width
                        block_size, // block_size
                        {p0, p1, p2, p3},// padding_vec
                        -128 // pad_value
                    );
                }

                // Chain
                ctx.accX = reshaped_dep1;
                ctx.accY = reshaped_dep2;

                // Write the vector in memory
                if (ctx.mem_accX != nullptr) VTAMemCopyFromHost(ctx.mem_accX, ctx.accX.data(), ctx.accX.size() * sizeof(acc_dtype));
                if (ctx.mem_accY != nullptr) VTAMemCopyFromHost(ctx.mem_accY, ctx.accY.data(), ctx.accY.size() * sizeof(acc_dtype));
            }
        }

        else if (reshape_info == "im2row"){
            // Get the previous layers
            std::vector<int8_t> dep_out;
            if (name_dep == "image"){
                dep_out = input_nn;
            }
            else{
                LayerContext& dep_ctx = layers_map[name_dep];
                dep_out = dep_ctx.res;
            }

            // Rescale
            std::vector<inp_dtype> rescaled_dep = convert_vector_type<inp_dtype>(dep_out);

            // Reshape
            ctx.inpA  = reshape(
                rescaled_dep, // prev_vector 
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
            VTAMemCopyFromHost(ctx.mem_inpA, ctx.inpA.data(), ctx.inpA.size() * sizeof(inp_dtype));
        }


        // D. EXECUTE THE VTA OR THE CPU
        // ---
        if (processor == "vta"){
            // Execute the layer
            int flag = VTADeviceRun(vta_device, ctx.phy_add_insn, ctx.insn_buffer.size(), 0);
            
            // Check the execution was successful
            if (flag != 0) {
                std::cerr << "ERROR: Execution failed at layer " << ctx.suffix << std::endl;
                VTADeviceFree(vta_device);
                return EXIT_FAILURE;
            }
        
            // Copy Result Back
            VTAMemCopyToHost(ctx.outC.data(), ctx.mem_outC, ctx.outC.size() * sizeof(inp_dtype));
        }
        // ELSE CPU OPERATIONS
        else if (processor == "qadd") {
            if (debug) printf("\t -> Processing QAdd (CPU)\n");

            // Sanity checks
            if (ctx.accX.size() != ctx.accY.size()) {
                std::cerr << "ERROR: QAdd input mismatch size (accX: " 
                          << ctx.accX.size() << ", accY: " << ctx.accY.size() << ")" << std::endl;
                return EXIT_FAILURE;
            }
            else if (scaleC == 0.0f) { 
                std::cerr << "ERROR: ScaleC is zero for QAdd layer" << std::endl;
                return EXIT_FAILURE;
            }

            // Set the output size
            ctx.outC.resize(ctx.accX.size());

            // Perform the addition
            for (size_t k = 0; k < ctx.accX.size(); ++k) {
                // out = (Sa/Sc)*X + (Sb/Sc)*Y
                // -> Computation decomposed to have semantic equivalence in floatting point
                float valX = (float)ctx.accX[k] * scaleA;
                float valY = (float)ctx.accY[k] * scaleB;
                float val = (valX + valY) / scaleC;
                // Round
                ctx.outC[k] = (inp_dtype)std::nearbyint(val); // round vs nearbyint
            }

            // Fix scale to 1.0
            scale = 1.0;
        }
        // CONCATENATION
        else if (processor == "concat") {
            // Define the layers
            LayerContext& dep_ctx = layers_map[name_dep];
            LayerContext& dep2_ctx = layers_map[name_dep2];
            LayerContext& dep3_ctx = layers_map[name_dep3];
            LayerContext& dep4_ctx = layers_map[name_dep4];

            // Get the previous layers
            std::vector<acc_dtype> dep_out, dep2_out, dep3_out, dep4_out;

            // The variables
            std::vector<std::vector<acc_dtype>> concat_inp;
            std::vector<std::vector<int>> concat_shapes;
            std::vector<float> concat_scales;
            std::vector<int32_t> concat_zps;

            // Define the shape
            std::vector<int> shape = {1, tensor_channel, tensor_height, tensor_width};


            // Get the previous layers
            dep_out = convert_vector_type<acc_dtype>(dep_ctx.res);
            dep2_out = convert_vector_type<acc_dtype>(dep2_ctx.res);
            if (nb_inp == 2){
                concat_inp = {dep_out, dep2_out};
                concat_shapes = {shape, shape};
                concat_scales = {scaleA, scaleB};
                concat_zps = {offsetA, offsetB};
            }
            else if (nb_inp == 3){
                dep3_out = convert_vector_type<acc_dtype>(dep3_ctx.res);

                concat_inp = {dep_out, dep2_out, dep3_out};
                concat_shapes = {shape, shape, shape};
                concat_scales = {scaleA, scaleB, scaleU};
                concat_zps = {offsetA, offsetB, offsetU};
            }
            else if (nb_inp == 4){
                dep3_out = convert_vector_type<acc_dtype>(dep3_ctx.res);
                dep4_out = convert_vector_type<acc_dtype>(dep4_ctx.res);

                concat_inp = {dep_out, dep2_out, dep3_out, dep4_out};
                concat_shapes = {shape, shape, shape, shape};
                concat_scales = {scaleA, scaleB, scaleU, scaleV};
                concat_zps = {offsetA, offsetB, offsetU, offsetV};
            }

            // Perform the concatenation
            ctx.outC = qlinear_concat<acc_dtype>(
                concat_inp, // Inputs
                concat_shapes, // Shapes
                concat_scales, // input_scales
                concat_zps, // input_zps
                scaleC, // output_scale
                offsetC, // output_zp
                1, // axis
                block_size// block_size
            );

            // Fix scale to 1.0
            scale = 1.0;
            offsetC = 0;
        }
        // DEQUANTISE
        else if (processor == "dequant") {
            if (debug) printf("\t -> Processing DequantizeLinear (CPU)\n");

            // Get the previous layer
            std::vector<int8_t> dep_out;
            if (name_dep == "image"){
                dep_out = input_nn;
            }
            else{
                LayerContext& dep_ctx = layers_map[name_dep];
                dep_out = dep_ctx.res;
            }

            // Rescale
            std::vector<inp_dtype> rescaled_dep = convert_vector_type<inp_dtype>(dep_out);
            
            // Dequantise
            std::vector<float> float_res = dequantize_linear(rescaled_dep, scaleA, offsetA);

            // Save the result
            ctx.value = float_res;
            
        }
        // QUANTISE
        else if (processor == "quant") {
            if (debug) printf("\t -> Processing QuantizeLinear (CPU)\n");

            // Define the layers
            LayerContext& dep_ctx = layers_map[name_dep];

            // Get the previou layer
            std::vector<float> float_res = dep_ctx.value;
            
            // Quantise
            std::vector<acc_dtype> int_res = quantize_linear(float_res, scaleA, offsetA);

            // Save the result
            ctx.outC = int_res;

            // Fix scale to 1.0
            scale = 1.0;
            offsetC = 0;
            
        }
        // CONVTRANSPOSE
        else if (processor == "convtranspose") {
            if (debug) printf("\t -> Processing ConvTranspose (CPU)\n");

            // Get the binaries
            std::string fileCTWgtPath = construct_path("weight" + ctx.suffix + ".bin");
            std::string fileCTAccPath = construct_path("accumulator" + ctx.suffix + ".bin");

            // Read 
            std::vector<float> CTwgt = read_binary_file<float>(fileCTWgtPath);
            std::vector<float> CTacc = read_binary_file<float>(fileCTAccPath);

            // Define the layers
            LayerContext& dep_ctx = layers_map[name_dep];

            // Get the previou layer
            std::vector<float> float_dep_out = dep_ctx.value;
            
            // ConvTranspose
            // Inputs: Vector -> Reconstruct Tensor (using input dims) -> Conv -> Flatten
            std::vector<float> float_res = conv_transpose(
                float_dep_out, 
                CTwgt, CTacc, 
                1, 
                tensor_channel, tensor_height, tensor_width, // Input Dims
                out_tensor_channel, out_tensor_height, out_tensor_width, // Output Dims
                kh, kw, sh, 
                {p0, p1, p2, p3}, 
                block_size
            );

            // Save the result
            ctx.value = float_res;
            
        }
        else { 
            NULL;
        }


        // E. RESCALE THE RESULT
        // ---

        // Perform the rescaling
        if ((processor != "dequant") && (processor != "convtranspose")){
            if (debug) printf("\nRescaling: \n\t rescaling factor=%.18lf and offset=%d \n", scale, offsetC);

            ctx.res = rescaling(
                ctx.outC, // vector (int32)
                scale, // rescale_factor (float)
                offsetC // offset
            );
        }
    }


    // 6. FREE ALL LAYERS
    // ------------------
    if (debug) {
        std::string profile_json = (*profiler_status)();
        std::cout << "\n--- Profiler Status ---" << std::endl << profile_json << std::endl;
    }

    for (const std::string& layer_name : loaded_layer_names) {
        LayerContext& ctx = layers_map[layer_name]; 

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
        print_vector(ctx.res.data(), ctx.res.size());
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