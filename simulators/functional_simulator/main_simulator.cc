/***************************
    PRE-PROCESSOR DIRECTIVES
****************************/
#include "simulator_header.h"


/********************
    EXECUTE_SIMULATOR
*********************/
int execute_simulator() {
    printf("\nExecute simulator:\n");

    // Define the current location of main_simulator.cc
    std::filesystem::path currentPath = std::filesystem::current_path();

    // Define the path for the input files
    auto construct_path = [&](const std::string& filename) {
        return (currentPath / ".." / ".." / "compiler_output" / filename).string();
    };

    std::string fileInpPath = construct_path("input.bin");
    std::string fileWgtPath = construct_path("weight.bin");
    std::string fileAccPath = construct_path("accumulator.bin");
    std::string fileUopPath = construct_path("uop.bin");
    std::string fileInsnPath = construct_path("instructions.bin");
    std::string fileExpectedOutPath = construct_path("expected_out.bin");

    // Read input files into vectors
    std::vector<int8_t> inpA = read_binary_file<int8_t>(fileInpPath);
    std::vector<int8_t> wgtB = read_binary_file<int8_t>(fileWgtPath);
    std::vector<int32_t> accX = read_binary_file<int32_t>(fileAccPath);
    std::vector<uop_t> uop_buffer = read_binary_file<uop_t>(fileUopPath);
    std::vector<instruction_t> insn_buffer = read_binary_file<instruction_t>(fileInsnPath);

   // Handle the output file differently
    std::vector<int8_t> outC;
    size_t outC_size = 0; // Keep track of the actual size

    std::ifstream expectedOutFile(fileExpectedOutPath, std::ios::binary);
    if (!expectedOutFile.is_open()) {
        std::cerr << "Warning: Could not open expected_out.bin, initializing outC with a default size.\n";
        outC_size = 16 * 256; // Initialize with a maximum size
        outC.resize(outC_size, 0); // Initialize with a maximum size
    } else {
        expectedOutFile.seekg(0, std::ios::end);
        std::streamsize fileSize = expectedOutFile.tellg();
        expectedOutFile.seekg(0, std::ios::beg);

        if (fileSize == -1) {
            std::cerr << "ERROR: Could not determine file size for expected_out.bin.\n";
            outC_size = 16 * 256;
            outC.resize(outC_size, 0);
        } else {
            outC_size = static_cast<size_t>(fileSize) / sizeof(int8_t);
            outC.resize(outC_size);
        }
        expectedOutFile.close();
    }

    // Memory allocation using VTA functions
    printf("\n\nDEBUG: Allocation space:\n"
           "\t INP: %lu Bytes (= %lu vectors) \n"
           "\t WGT: %lu Bytes (= %lu vectors) \n"
           "\t OUT: %lu Bytes (= %lu vectors) \n",
           inpA.size() * sizeof(int8_t), inpA.size() * sizeof(int8_t) / 16,
           wgtB.size() * sizeof(int8_t), wgtB.size() * sizeof(int8_t) / 256,
           outC_size * sizeof(int8_t), outC_size * sizeof(int8_t) / 16);
    void* mem_inpA = VTAMemAlloc(inpA.size() * sizeof(int8_t), 1);
    void* mem_wgtB = VTAMemAlloc(wgtB.size() * sizeof(int8_t), 1);
    void* mem_outC = VTAMemAlloc(outC_size * sizeof(int8_t), 1);
    void* mem_uop = VTAMemAlloc(uop_buffer.size() * sizeof(uop_t), 1);
    void* mem_accX = VTAMemAlloc(accX.size() * sizeof(int32_t), 1);
    void* mem_insn = VTAMemAlloc(insn_buffer.size() * sizeof(instruction_t), 1);

    // Get physical addresses
    vta_phy_addr_t phy_add_insn = VTAMemGetPhyAddr(mem_insn);
    vta_phy_addr_t phy_add_inpA = VTAMemGetPhyAddr(mem_inpA);
    vta_phy_addr_t phy_add_wgtB = VTAMemGetPhyAddr(mem_wgtB);
    vta_phy_addr_t phy_add_outC = VTAMemGetPhyAddr(mem_outC);
    vta_phy_addr_t phy_add_uop = VTAMemGetPhyAddr(mem_uop);
    vta_phy_addr_t phy_add_accX = VTAMemGetPhyAddr(mem_accX);

    printf("\nDEBUG: PHYSICAL (phy) vs LOGIC (logic) ADDRESS: \n"
           " inpA = phy:0x%x, logic:0x%x (logic = phy/16) \n"
           " wgtB = phy:0x%x, logic:0x%x (logic = phy/256) \n"
           " outC = phy:0x%x, logic:0x%x (logic = phy/16) \n"
           " uop = phy:0x%x, logic:0x%x (logic = phy/4) \n"
           " accX = phy:0x%x, logic:0x%x (logic = phy/64) \n"
           " insn = phy:0x%x, logic:0x%x (logic = phy/16) \n\n",
           phy_add_inpA, phy_add_inpA / 16, phy_add_wgtB, phy_add_wgtB / 256,
           phy_add_outC, phy_add_outC / 16, phy_add_uop, phy_add_uop / 4,
           phy_add_accX, phy_add_accX / 64, phy_add_insn, phy_add_insn / 16);

    // Copy data to VTA memory
    VTAMemCopyFromHost(mem_inpA, inpA.data(), inpA.size() * sizeof(int8_t));
    VTAMemCopyFromHost(mem_wgtB, wgtB.data(), wgtB.size() * sizeof(int8_t));
    VTAMemCopyFromHost(mem_outC, outC.data(), outC_size * sizeof(int8_t)); 
    VTAMemCopyFromHost(mem_uop, uop_buffer.data(), uop_buffer.size() * sizeof(uop_t));
    VTAMemCopyFromHost(mem_accX, accX.data(), accX.size() * sizeof(int32_t));
    VTAMemCopyFromHost(mem_insn, insn_buffer.data(), insn_buffer.size() * sizeof(instruction_t));

    // Run VTA device
    VTADeviceHandle vta_device = VTADeviceAlloc();
    int execution_flag = VTADeviceRun(vta_device, phy_add_insn, insn_buffer.size(), 0);
    printf("\nThe execution returns: %d \n\t(return 0 if running is successful, 1 if timeout)\n", execution_flag);
    VTADeviceFree(vta_device);

    // Copy result back
    VTAMemCopyToHost(inpA.data(), mem_inpA, inpA.size() * sizeof(int8_t));
    VTAMemCopyToHost(wgtB.data(), mem_wgtB, wgtB.size() * sizeof(int8_t));
    VTAMemCopyToHost(outC.data(), mem_outC, outC_size * sizeof(int8_t)); 

    // Free memory
    VTAMemFree(mem_inpA);
    VTAMemFree(mem_wgtB);
    VTAMemFree(mem_outC);
    VTAMemFree(mem_uop);
    VTAMemFree(mem_accX);
    VTAMemFree(mem_insn);

    // Print results
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

    printf("outC = {");
    print_int8_vector(outC.data(), outC_size); // Use the actual size
    printf("\n} \n\n");

    return 0;
}


/****************
    MAIN FUNCTION
*****************/
int main() {
    execute_simulator();
    return 0;
}
