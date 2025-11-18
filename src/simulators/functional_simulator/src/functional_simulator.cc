/***************************
    PRE-PROCESSOR DIRECTIVES
****************************/
#include "../include/simulator_header.h"
#include "../external_lib/tvm/packed_func.h"
#include "../external_lib/tvm/registry.h"


/********************
    EXECUTE_SIMULATOR
*********************/
int execute_simulator(bool debug) {

    // Define the current location of main_simulator.cc
    std::filesystem::path currentPath = std::filesystem::current_path();

    // Define the path for the input files
    auto construct_path = [&](const std::string& filename) {
        return (currentPath / ".." / ".." / ".." / "compiler_output" / filename).string();
    };

    // READ THE METADATA FILE
    // ----------------------
    std::string fileMetadataPath = construct_path("metadata.csv");

    // Get the metadata
    // Block size
    std::string block_size_str = getCsvElementByName(fileMetadataPath, "BS", 1);
    int block_size = strToInt(block_size_str);

    // A
    std::string A_row_str = getCsvElementByName(fileMetadataPath, "A", 1);
    int A_row = strToInt(A_row_str);
    std::string A_col_str = getCsvElementByName(fileMetadataPath, "A", 2);
    int A_col = strToInt(A_col_str);

    // X
    std::string X_row_str = getCsvElementByName(fileMetadataPath, "X", 1);
    int X_row = strToInt(X_row_str);
    std::string X_col_str = getCsvElementByName(fileMetadataPath, "X", 2);
    int X_col = strToInt(X_col_str);

    // Y
    std::string Y_row_str = getCsvElementByName(fileMetadataPath, "Y", 1);
    int Y_row = strToInt(Y_row_str);
    std::string Y_col_str = getCsvElementByName(fileMetadataPath, "Y", 2);
    int Y_col = strToInt(Y_col_str);

    // C
    std::string C_row_str = getCsvElementByName(fileMetadataPath, "C", 1);
    int C_row = strToInt(C_row_str);
    std::string C_col_str = getCsvElementByName(fileMetadataPath, "C", 2);
    int C_col = strToInt(C_col_str);

    
    // READ THE BINARIES FILES
    // -----------------------
    std::string fileInpPath = construct_path("input.bin");
    std::string fileWgtPath = construct_path("weight.bin");
    std::string fileAccPath = construct_path("accumulator.bin");
    std::string fileAddAccPath = construct_path("add_accumulator.bin");
    std::string fileOutPath = construct_path("output.bin");
    std::string fileRefPath = construct_path("reference.bin");
    std::string fileUopPath = construct_path("uop.bin");
    std::string fileInsnPath = construct_path("instructions.bin");

    // Read input files into vectors
    // A
    // std::vector<int8_t> inpA = read_binary_file<int8_t>(fileInpPath);
    std::vector<int8_t> raw_inpA = read_binary_file<int8_t>(fileInpPath);
    std::vector<int8_t> inpA;
    if (A_row <= 0 || A_col <= 0 ) 
    { 
        inpA = raw_inpA;
    }
    else 
    {
        inpA = data_formatting(raw_inpA, A_row, A_col, block_size, true);
    }
    
    // B
    std::vector<int8_t> wgtB = read_binary_file<int8_t>(fileWgtPath);

    // X
    // std::vector<int32_t> accX = read_binary_file<int32_t>(fileAccPath);
    std::vector<int32_t> raw_accX = read_binary_file<int32_t>(fileAccPath);
    std::vector<int32_t> accX;
    if (X_row <= 0 || X_col <= 0 ) 
    { 
        accX = raw_accX;
    }
    else 
    {
        accX = data_formatting(raw_accX, X_row, X_col, block_size, true);
    }

    // Y
    // std::vector<int32_t> accY = read_binary_file<int32_t>(fileAddAccPath);
    std::vector<int32_t> raw_accY = read_binary_file<int32_t>(fileAddAccPath);
    std::vector<int32_t> accY;
    if (Y_row <= 0 || Y_col <= 0 ) 
    { 
        accY = raw_accY;
    }
    else 
    {
        accY = data_formatting(raw_accY, Y_row, Y_col, block_size, true);
    }

    // C
    std::vector<int8_t> outC = read_binary_file<int8_t>(fileOutPath);
    // REFERENCE C
    std::vector<int8_t> raw_refC = read_binary_file<int8_t>(fileRefPath);
    std::vector<int8_t> refC;
    if (C_row <= 0 || C_col <= 0 ) 
    { 
        refC = raw_refC;
    }
    else 
    {
        refC = data_formatting(raw_refC, C_row, C_col, block_size, true); //TODO: manage the isSquare
    }

    // INSN + UOP
    std::vector<uop_t> uop_buffer = read_binary_file<uop_t>(fileUopPath);
    std::vector<instruction_t> insn_buffer = read_binary_file<instruction_t>(fileInsnPath);


    // ALLOCATE MEMORY SPACE
    // ---------------------

    // Memory allocation using VTA functions
    if (debug == true)
    {
        printf("\n\nDEBUG: Allocation space:\n"
            "\t INP: %lu Bytes (= %lu vectors) \n"
            "\t WGT: %lu Bytes (= %lu vectors) \n"
            "\t OUT: %lu Bytes (= %lu vectors) \n",
            inpA.size() * sizeof(int8_t), inpA.size() * sizeof(int8_t) / 16,
            wgtB.size() * sizeof(int8_t), wgtB.size() * sizeof(int8_t) / 256,
            outC.size() * sizeof(int8_t), outC.size() * sizeof(int8_t) / 16);
    }
           
    void* mem_inpA = VTAMemAlloc(inpA.size() * sizeof(int8_t), 1);
    void* mem_wgtB = VTAMemAlloc(wgtB.size() * sizeof(int8_t), 1);
    void* mem_accX = VTAMemAlloc(accX.size() * sizeof(int32_t), 1);
    void* mem_accY = VTAMemAlloc(accY.size() * sizeof(int32_t), 1);
    void* mem_outC = VTAMemAlloc(outC.size() * sizeof(int8_t), 1);
    void* mem_uop = VTAMemAlloc(uop_buffer.size() * sizeof(uop_t), 1);
    void* mem_insn = VTAMemAlloc(insn_buffer.size() * sizeof(instruction_t), 1);

    // Get physical addresses
    vta_phy_addr_t phy_add_insn = VTAMemGetPhyAddr(mem_insn);
    vta_phy_addr_t phy_add_inpA = VTAMemGetPhyAddr(mem_inpA);
    vta_phy_addr_t phy_add_wgtB = VTAMemGetPhyAddr(mem_wgtB);
    vta_phy_addr_t phy_add_outC = VTAMemGetPhyAddr(mem_outC);
    vta_phy_addr_t phy_add_uop = VTAMemGetPhyAddr(mem_uop);
    vta_phy_addr_t phy_add_accX = VTAMemGetPhyAddr(mem_accX);
    vta_phy_addr_t phy_add_accY = VTAMemGetPhyAddr(mem_accY);

    if (debug == true)
    {
        printf("\nDEBUG: PHYSICAL (phy) vs LOGIC (logic) ADDRESS: \n"
            " inpA = phy:0x%x, logic:0x%x (logic = phy/16) \n"
            " wgtB = phy:0x%x, logic:0x%x (logic = phy/256) \n"
            " accX = phy:0x%x, logic:0x%x (logic = phy/64) \n"
            " accY = phy:0x%x, logic:0x%x (logic = phy/64) \n"
            " outC = phy:0x%x, logic:0x%x (logic = phy/16) \n"
            " uop = phy:0x%x, logic:0x%x (logic = phy/4) \n"
            " insn = phy:0x%x, logic:0x%x (logic = phy/16) \n\n",
            phy_add_inpA, phy_add_inpA / 16, phy_add_wgtB, phy_add_wgtB / 256,
            phy_add_accX, phy_add_accX / 64, phy_add_accY, phy_add_accY / 64,
            phy_add_outC, phy_add_outC / 16, 
            phy_add_uop, phy_add_uop / 4, phy_add_insn, phy_add_insn / 16);
    }


    // INITIALISE THE DRAM MEMORY
    // --------------------------

    // --- PROFILER SETUP ---
    // Get PackedFunc pointers from the TVM registry
    const tvm::runtime::PackedFunc* profiler_clear = tvm::runtime::Registry::Get("vta.simulator.profiler_clear");
    const tvm::runtime::PackedFunc* profiler_status = tvm::runtime::Registry::Get("vta.simulator.profiler_status");
    const tvm::runtime::PackedFunc* profiler_debug_mode = tvm::runtime::Registry::Get("vta.simulator.profiler_debug_mode");

    // Check if the functions were found
    if (!profiler_clear || !profiler_status || !profiler_debug_mode) {
        std::cerr << "ERROR: Could not find profiler functions in the TVM registry. "
                << "Ensure TVM runtime is initialized and VTA simulator modules are loaded." << std::endl;
        return -1;
    }

    // Clear any previous profiler statistics
    (*profiler_clear)();

    // Set debug mode (optional)
    // 0: Normal execution
    // 1: Skip execution (only count operations) - useful for performance modeling
    int debug_flag = 0; // Set to 1 to skip actual computation
    (*profiler_debug_mode)(debug_flag);
    if (debug == true){
        printf("DEBUG: Profiler debug mode set to %d.\n", debug_flag);
    }
    // --- END PROFILER SETUP ---
  

    // Copy data to VTA memory
    VTAMemCopyFromHost(mem_inpA, inpA.data(), inpA.size() * sizeof(int8_t));
    VTAMemCopyFromHost(mem_wgtB, wgtB.data(), wgtB.size() * sizeof(int8_t));
    VTAMemCopyFromHost(mem_accX, accX.data(), accX.size() * sizeof(int32_t));
    VTAMemCopyFromHost(mem_accY, accY.data(), accY.size() * sizeof(int32_t));
    VTAMemCopyFromHost(mem_outC, outC.data(), outC.size() * sizeof(int8_t)); 
    VTAMemCopyFromHost(mem_uop, uop_buffer.data(), uop_buffer.size() * sizeof(uop_t));
    VTAMemCopyFromHost(mem_insn, insn_buffer.data(), insn_buffer.size() * sizeof(instruction_t));


    // LAYER EXECUTION
    // ---------------
    // Run VTA device
    VTADeviceHandle vta_device = VTADeviceAlloc();
    int execution_flag = VTADeviceRun(vta_device, phy_add_insn, insn_buffer.size(), 0);

    // Copy result back
    VTAMemCopyToHost(inpA.data(), mem_inpA, inpA.size() * sizeof(int8_t));
    VTAMemCopyToHost(wgtB.data(), mem_wgtB, wgtB.size() * sizeof(int8_t));
    VTAMemCopyToHost(outC.data(), mem_outC, outC.size() * sizeof(int8_t)); 


    // FREE MEMORY
    // -----------

    // --- PROFILER RESULTS ---
    if (debug==true)
    {
        std::string profile_json = (*profiler_status)(); // Get profiler results as JSON
        std::cout << "\n--- Profiler Status ---" << std::endl;
        std::cout << profile_json << std::endl;
    }
    // --- END PROFILER RESULTS ---

    // Free VTA device
    VTADeviceFree(vta_device);

    // Free DRAM
    VTAMemFree(mem_inpA);
    VTAMemFree(mem_wgtB);
    VTAMemFree(mem_outC);
    VTAMemFree(mem_uop);
    VTAMemFree(mem_accX);
    VTAMemFree(mem_accY);
    VTAMemFree(mem_insn);

    // The program has failed
    if (execution_flag != 0)
    {
        return EXIT_FAILURE;
    }


    // GET THE RESULT
    // --------------
    // Print results
    if (debug == true)
    {
        printf("\n\nRESULT:\n");

        printf("inpA = {");
        print_int8_vector(inpA.data(), inpA.size());
        printf("\n} \n");

        printf("wgtB = {");
        print_int8_vector(wgtB.data(), wgtB.size());
        printf("\n} \n\n");

        printf("accX = {");
        print_int32_vector(accX.data(), accX.size());
        printf("\n} \n\n");

        printf("accY = {");
        print_int32_vector(accY.data(), accY.size());
        printf("\n} \n\n");

        printf("refC = {");
        print_int8_vector(refC.data(), refC.size());
        printf("\n} \n\n");
    }

    printf("\n\n Final result= {");
    print_int8_vector(outC.data(), outC.size()); // Use the actual size
    printf("\n} \n\n");


    bool isCorrect = true;
    isCorrect = compare_vector(outC.data(), refC.data(), outC.size());
    if (isCorrect)
    {
        return EXIT_SUCCESS;
    }
    else
    {
        return EXIT_FAILURE;
    }
}


/****************
    MAIN FUNCTION
*****************/
int main() {
    return execute_simulator(DEBUG_SIM);
}
