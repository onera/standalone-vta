/***************************
    PRE-PROCESSOR DIRECTIVES
****************************/
#include "simulator_header.h"
#include "external_lib/tvm/packed_func.h"
#include "external_lib/tvm/registry.h"


/********************
    EXECUTE_SIMULATOR
*********************/
int lenet5_implementation() {
    printf("\nExecute lenet5_implementation_simulator:\n");

    // READ THE BINARIES FILES
    // -----------------------

    // Define the current location of main_simulator.cc
    std::filesystem::path currentPath = std::filesystem::current_path();

    // Define the path for the input files
    auto construct_path = [&](const std::string& filename) {
        return (currentPath / ".." / ".." / ".." / "compiler_output" / filename).string();
    };

    // Input is overwritten (MAX size = 784*32 vectors)
    std::string fileInpPath = construct_path("input.bin"); 

    // Five weight files
    std::string fileWgtL1Path = construct_path("weight_L1.bin");
    std::string fileWgtL2Path = construct_path("weight_L2.bin");
    std::string fileWgtL3Path = construct_path("weight_L3.bin");
    std::string fileWgtL4Path = construct_path("weight_L4.bin");
    std::string fileWgtL5Path = construct_path("weight_L5.bin");

    // No accumulator
    // Five UOPs and instructions
    std::string fileUopL1Path = construct_path("uop_L1.bin");
    std::string fileUopL2Path = construct_path("uop_L2.bin");
    std::string fileUopL3Path = construct_path("uop_L3.bin");
    std::string fileUopL4Path = construct_path("uop_L4.bin");
    std::string fileUopL5Path = construct_path("uop_L5.bin");
    std::string fileInsnL1Path = construct_path("instructions_L1.bin");
    std::string fileInsnL2Path = construct_path("instructions_L2.bin");
    std::string fileInsnL3Path = construct_path("instructions_L3.bin");
    std::string fileInsnL4Path = construct_path("instructions_L4.bin");
    std::string fileInsnL5Path = construct_path("instructions_L5.bin");

    // Read input files into vectors
    std::vector<int8_t> inp = read_binary_file<int8_t>(fileInpPath);

    std::vector<int8_t> wgtL1 = read_binary_file<int8_t>(fileWgtL1Path);
    std::vector<int8_t> wgtL2 = read_binary_file<int8_t>(fileWgtL2Path);
    std::vector<int8_t> wgtL3 = read_binary_file<int8_t>(fileWgtL3Path);
    std::vector<int8_t> wgtL4 = read_binary_file<int8_t>(fileWgtL4Path);
    std::vector<int8_t> wgtL5 = read_binary_file<int8_t>(fileWgtL5Path);

    std::vector<uop_t> uopL1 = read_binary_file<uop_t>(fileUopL1Path);
    std::vector<uop_t> uopL2 = read_binary_file<uop_t>(fileUopL2Path);
    std::vector<uop_t> uopL3 = read_binary_file<uop_t>(fileUopL3Path);
    std::vector<uop_t> uopL4 = read_binary_file<uop_t>(fileUopL4Path);
    std::vector<uop_t> uopL5 = read_binary_file<uop_t>(fileUopL5Path);

    std::vector<instruction_t> insnL1 = read_binary_file<instruction_t>(fileInsnL1Path);
    std::vector<instruction_t> insnL2 = read_binary_file<instruction_t>(fileInsnL2Path);
    std::vector<instruction_t> insnL3 = read_binary_file<instruction_t>(fileInsnL3Path);
    std::vector<instruction_t> insnL4 = read_binary_file<instruction_t>(fileInsnL4Path);
    std::vector<instruction_t> insnL5 = read_binary_file<instruction_t>(fileInsnL5Path);

    // Other vectors
    std::vector<int8_t> intermediate_result;
    size_t intermediate_size = 196*16;
    intermediate_result.resize(intermediate_size, 0);

    std::vector<int8_t> reshaped_result;
    size_t reshaped_size = 160*112;
    reshaped_result.resize(reshaped_size, 0);
    
    std::vector<int8_t> out;
    size_t out_size = 16;
    out.resize(out_size, 0);
    

    // ALLOCATE MEMORY SPACE
    // ---------------------
    void* mem_inp = VTAMemAlloc(inp.size() * sizeof(int8_t), 1);

    void* mem_wgtL1 = VTAMemAlloc(wgtL1.size() * sizeof(int8_t), 1);
    void* mem_wgtL2 = VTAMemAlloc(wgtL2.size() * sizeof(int8_t), 1);
    void* mem_wgtL3 = VTAMemAlloc(wgtL3.size() * sizeof(int8_t), 1);
    void* mem_wgtL4 = VTAMemAlloc(wgtL4.size() * sizeof(int8_t), 1);
    void* mem_wgtL5 = VTAMemAlloc(wgtL5.size() * sizeof(int8_t), 1);

    void* mem_out = VTAMemAlloc(out_size * sizeof(int8_t), 1);

    void* mem_uopL1 = VTAMemAlloc(uopL1.size() * sizeof(uop_t), 1);
    void* mem_uopL2 = VTAMemAlloc(uopL2.size() * sizeof(uop_t), 1);
    void* mem_uopL3 = VTAMemAlloc(uopL3.size() * sizeof(uop_t), 1);
    void* mem_uopL4 = VTAMemAlloc(uopL4.size() * sizeof(uop_t), 1);
    void* mem_uopL5 = VTAMemAlloc(uopL5.size() * sizeof(uop_t), 1);

    void* mem_intermediate = VTAMemAlloc(intermediate_size * sizeof(int8_t), 1);

    void* mem_insnL1 = VTAMemAlloc(insnL1.size() * sizeof(instruction_t), 1);
    void* mem_insnL2 = VTAMemAlloc(insnL2.size() * sizeof(instruction_t), 1);
    void* mem_insnL3 = VTAMemAlloc(insnL3.size() * sizeof(instruction_t), 1);
    void* mem_insnL4 = VTAMemAlloc(insnL4.size() * sizeof(instruction_t), 1);
    void* mem_insnL5 = VTAMemAlloc(insnL5.size() * sizeof(instruction_t), 1);

    // Get physical addresses
    vta_phy_addr_t phy_add_insnL1 = VTAMemGetPhyAddr(mem_insnL1);
    vta_phy_addr_t phy_add_insnL2 = VTAMemGetPhyAddr(mem_insnL2);
    vta_phy_addr_t phy_add_insnL3 = VTAMemGetPhyAddr(mem_insnL3);
    vta_phy_addr_t phy_add_insnL4 = VTAMemGetPhyAddr(mem_insnL4);
    vta_phy_addr_t phy_add_insnL5 = VTAMemGetPhyAddr(mem_insnL5);

    vta_phy_addr_t phy_add_inp = VTAMemGetPhyAddr(mem_inp);
    vta_phy_addr_t phy_add_wgtL1 = VTAMemGetPhyAddr(mem_wgtL1);
    vta_phy_addr_t phy_add_wgtL2 = VTAMemGetPhyAddr(mem_wgtL2);
    vta_phy_addr_t phy_add_wgtL3 = VTAMemGetPhyAddr(mem_wgtL3);
    vta_phy_addr_t phy_add_wgtL4 = VTAMemGetPhyAddr(mem_wgtL4);
    vta_phy_addr_t phy_add_wgtL5 = VTAMemGetPhyAddr(mem_wgtL5);
    vta_phy_addr_t phy_add_out = VTAMemGetPhyAddr(mem_out);
    vta_phy_addr_t phy_add_uopL1 = VTAMemGetPhyAddr(mem_uopL1);
    vta_phy_addr_t phy_add_uopL2 = VTAMemGetPhyAddr(mem_uopL2);
    vta_phy_addr_t phy_add_uopL3 = VTAMemGetPhyAddr(mem_uopL3);
    vta_phy_addr_t phy_add_uopL4 = VTAMemGetPhyAddr(mem_uopL4);
    vta_phy_addr_t phy_add_uopL5 = VTAMemGetPhyAddr(mem_uopL5);
    vta_phy_addr_t phy_add_res = VTAMemGetPhyAddr(mem_intermediate);
    printf("\nDEBUG: PHYSICAL (phy) vs LOGIC (logic) ADDRESS: \n"
           " inp = phy:0x%x, logic:0x%x (logic = phy/16) \n"
           " wgtL1 = phy:0x%x, logic:0x%x (logic = phy/256) \n"
           " wgtL2 = phy:0x%x, logic:0x%x (logic = phy/256) \n"
           " wgtL3 = phy:0x%x, logic:0x%x (logic = phy/256) \n"
           " wgtL4 = phy:0x%x, logic:0x%x (logic = phy/256) \n"
           " wgtL5 = phy:0x%x, logic:0x%x (logic = phy/256) \n"
           " out = phy:0x%x, logic:0x%x (logic = phy/16) \n"
           " uopL1 = phy:0x%x, logic:0x%x (logic = phy/4) \n"
           " uopL2 = phy:0x%x, logic:0x%x (logic = phy/4) \n"
           " uopL3 = phy:0x%x, logic:0x%x (logic = phy/4) \n"
           " uopL4 = phy:0x%x, logic:0x%x (logic = phy/4) \n"
           " uopL5 = phy:0x%x, logic:0x%x (logic = phy/4) \n"
           " res = phy:0x%x, logic:0x%x (logic = phy/16) \n\n",
           phy_add_inp, phy_add_inp / 16, 
           phy_add_wgtL1, phy_add_wgtL1 / 256, phy_add_wgtL2, phy_add_wgtL2 / 256, phy_add_wgtL3, phy_add_wgtL3 / 256,
           phy_add_wgtL4, phy_add_wgtL4 / 256, phy_add_wgtL5, phy_add_wgtL5 / 256,
           phy_add_out, phy_add_out / 16, 
           phy_add_uopL1, phy_add_uopL1 / 4, phy_add_uopL2, phy_add_uopL2 / 4, phy_add_uopL3, phy_add_uopL3 / 4,
           phy_add_uopL4, phy_add_uopL4 / 4, phy_add_uopL5, phy_add_uopL5 / 4,
           phy_add_res, phy_add_res / 16);


    // INITIALISE THE DRAM MEMORY
    // --------------------------
      // --- PROFILER SETUP ---
      printf("DEBUG: Setting up profiler...\n");
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
       printf("DEBUG: Profiler functions retrieved.\n");
  
      // Clear any previous profiler statistics
      (*profiler_clear)();
      printf("DEBUG: Profiler cleared.\n");
  
      // Set debug mode (optional)
      // 0: Normal execution
      // 1: Skip execution (only count operations) - useful for performance modeling
      int debug_flag = 0; // Set to 1 to skip actual computation
      (*profiler_debug_mode)(debug_flag);
      printf("DEBUG: Profiler debug mode set to %d.\n", debug_flag);
      // --- END PROFILER SETUP ---
  

    // Copy data to VTA memory
    VTAMemCopyFromHost(mem_inp, inp.data(), inp.size() * sizeof(int8_t));

    VTAMemCopyFromHost(mem_wgtL1, wgtL1.data(), wgtL1.size() * sizeof(int8_t));
    VTAMemCopyFromHost(mem_wgtL2, wgtL2.data(), wgtL2.size() * sizeof(int8_t));
    VTAMemCopyFromHost(mem_wgtL3, wgtL3.data(), wgtL3.size() * sizeof(int8_t));
    VTAMemCopyFromHost(mem_wgtL4, wgtL4.data(), wgtL4.size() * sizeof(int8_t));
    VTAMemCopyFromHost(mem_wgtL5, wgtL5.data(), wgtL5.size() * sizeof(int8_t));

    //VTAMemCopyFromHost(mem_out, out.data(), out_size * sizeof(int8_t)); // Empty
    
    VTAMemCopyFromHost(mem_uopL1, uopL1.data(), uopL1.size() * sizeof(uop_t));
    VTAMemCopyFromHost(mem_uopL2, uopL2.data(), uopL2.size() * sizeof(uop_t));
    VTAMemCopyFromHost(mem_uopL3, uopL3.data(), uopL3.size() * sizeof(uop_t));
    VTAMemCopyFromHost(mem_uopL4, uopL4.data(), uopL4.size() * sizeof(uop_t));
    VTAMemCopyFromHost(mem_uopL5, uopL5.data(), uopL5.size() * sizeof(uop_t));

    //VTAMemCopyFromHost(mem_intermediate, intermediate_result.data(), intermediate_size * sizeof(int8_t)); // Empty

    VTAMemCopyFromHost(mem_insnL1, insnL1.data(), insnL1.size() * sizeof(instruction_t));
    VTAMemCopyFromHost(mem_insnL2, insnL2.data(), insnL2.size() * sizeof(instruction_t));
    VTAMemCopyFromHost(mem_insnL3, insnL3.data(), insnL3.size() * sizeof(instruction_t));
    VTAMemCopyFromHost(mem_insnL4, insnL4.data(), insnL4.size() * sizeof(instruction_t));
    VTAMemCopyFromHost(mem_insnL5, insnL5.data(), insnL5.size() * sizeof(instruction_t));

    // Init VTA device
    VTADeviceHandle vta_device = VTADeviceAlloc();

    // LAYER 1 EXECUTION
    // -----------------
    int execution_flag = VTADeviceRun(vta_device, phy_add_insnL1, insnL1.size(), 0);

    // Reshape result
    VTAMemCopyToHost(intermediate_result.data(), mem_intermediate, intermediate_result.size() * sizeof(int8_t));

    reshaped_result = reshape(
        intermediate_result, //const std::vector<int8_t>& vector,
        1, //int block_col = 1,
        16, //int block_size = 16,
        196, //int out_matrix_height = 196,
        6, //int out_matrix_width = 6,
        1, //int batch_size = 1,
        6, //int out_tensor_channel = 6,
        14, //int out_tensor_height = 14,
        14,//int out_tensor_width = 14,
        {5,5},//std::pair<int, int> kernel_size = {5, 5},
        1,//int stride = 1,
        true);//bool isSquare = true);
    
    VTAMemCopyFromHost(mem_inp, reshaped_result.data(), 112*160 * sizeof(int8_t));


    // LAYER 2 EXECUTION
    // -----------------
    execution_flag = VTADeviceRun(vta_device, phy_add_insnL2, insnL2.size(), 0);

    // Reshape result
    intermediate_result.resize(25*16, 0);
    reshaped_result.resize(25*16, 0);

    VTAMemCopyToHost(intermediate_result.data(), mem_intermediate, intermediate_result.size() * sizeof(int8_t));

    reshaped_result = reshape(
        intermediate_result, //const std::vector<int8_t>& vector,
        1, //int block_col,
        16, //int block_size,
        25, //int out_matrix_height,
        16, //int out_matrix_width,
        1, //int batch_size,
        16, //int out_tensor_channel,
        5, //int out_tensor_height,
        5,//int out_tensor_width,
        {5,5},//std::pair<int, int> kernel_size,
        1,//int stride = 1,
        false);//bool isSquare = true);

    VTAMemCopyFromHost(mem_inp, reshaped_result.data(), reshaped_result.size() * sizeof(int8_t));


    // LAYER 3 EXECUTION
    // -----------------
    execution_flag = VTADeviceRun(vta_device, phy_add_insnL3, insnL3.size(), 0);

    // LAYER 4 EXECUTION
    // -----------------
    execution_flag = VTADeviceRun(vta_device, phy_add_insnL4, insnL4.size(), 0);

    // LAYER 5 EXECUTION
    // -----------------
    execution_flag = VTADeviceRun(vta_device, phy_add_insnL5, insnL5.size(), 0);
    printf("\nThe execution returns: %d \n\t(return 0 if running is successful, 1 if timeout)\n", execution_flag);

    // Copy the final output result
    VTAMemCopyToHost(out.data(), mem_out, out.size() * sizeof(int8_t)); 


    // FREE MEMORY
    // -----------

    // --- PROFILER RESULTS ---
    printf("DEBUG: Retrieving profiler status...\n");
    std::string profile_json = (*profiler_status)(); // Get profiler results as JSON
    std::cout << "\n--- Profiler Status ---" << std::endl;
    std::cout << profile_json << std::endl;
    // --- END PROFILER RESULTS ---
    // Free VTA device
    VTADeviceFree(vta_device);

    // Free VTA memory
    VTAMemFree(mem_inp);

    VTAMemFree(mem_wgtL1);
    VTAMemFree(mem_wgtL2);
    VTAMemFree(mem_wgtL3);
    VTAMemFree(mem_wgtL4);
    VTAMemFree(mem_wgtL5);

    VTAMemFree(mem_out);

    VTAMemFree(mem_uopL1);
    VTAMemFree(mem_uopL2);
    VTAMemFree(mem_uopL3);
    VTAMemFree(mem_uopL4);
    VTAMemFree(mem_uopL5);

    VTAMemFree(mem_intermediate);

    VTAMemFree(mem_insnL1);
    VTAMemFree(mem_insnL2);
    VTAMemFree(mem_insnL3);
    VTAMemFree(mem_insnL4);
    VTAMemFree(mem_insnL5);


    // GET THE RESULT
    // --------------
    // Print results    
    printf("\n\nRESULT:\n");
    print_int8_vector(out.data(), out_size);
    printf("\n\n Execution DONE! \n\n");

    return 0;
}


/****************
    MAIN FUNCTION
*****************/
int main() {
    lenet5_implementation();
    return 0;
}
