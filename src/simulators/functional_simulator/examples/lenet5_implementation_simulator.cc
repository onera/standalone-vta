/***************************
    PRE-PROCESSOR DIRECTIVES
****************************/
#include "../include/simulator_header.h"
#include "../external_lib/tvm/packed_func.h"
#include "../external_lib/tvm/registry.h"


/********************
    EXECUTE_SIMULATOR
*********************/
int lenet5_implementation() {

    // READ THE BINARIES FILES
    // -----------------------

    // Define the current location of main_simulator.cc
    std::filesystem::path currentPath = std::filesystem::current_path();

    // Define the path for the input files
    auto construct_path = [&](const std::string& filename) {
        return (currentPath / ".." / ".." / ".." / "compiler_output" / filename).string();
    };

    // LAYER 1
    // Define the path
    std::string fileInpL1Path = construct_path("input_L1.bin");
    std::string fileWgtL1Path = construct_path("weight_L1.bin");
    std::string fileAccL1Path = construct_path("accumulator_L1.bin");
    std::string fileAddAccL1Path = construct_path("add_accumulator_L1.bin");
    std::string fileUopL1Path = construct_path("uop_L1.bin");
    std::string fileInsnL1Path = construct_path("instructions_L1.bin");
    std::string fileExpectedOutL1Path = construct_path("expected_out_L1.bin");
    std::string fileExpectedOutSramL1Path = construct_path("expected_out_sram_L1.bin");
    // Read binaries
    std::vector<int8_t> inpA_L1 = read_binary_file<int8_t>(fileInpL1Path);
    std::vector<int8_t> wgtB_L1 = read_binary_file<int8_t>(fileWgtL1Path);
    std::vector<int32_t> accX_L1 = read_binary_file<int32_t>(fileAccL1Path);
    std::vector<int32_t> accY_L1 = read_binary_file<int32_t>(fileAddAccL1Path);
    std::vector<uop_t> uop_buffer_L1 = read_binary_file<uop_t>(fileUopL1Path);
    std::vector<instruction_t> insn_buffer_L1 = read_binary_file<instruction_t>(fileInsnL1Path);
    std::vector<int8_t> expected_out_L1 = read_binary_file<int8_t>(fileExpectedOutL1Path);
    // Handle the output file differently
    std::vector<int8_t> expected_out_sram_L1 = read_binary_file<int8_t>(fileExpectedOutSramL1Path);
    std::vector<int8_t> outC_L1;
    size_t outC_L1_size = expected_out_sram_L1.size(); 
    outC_L1.resize(outC_L1_size);

    // LAYER 2
    std::string fileInpL2Path = construct_path("input_L2.bin");
    std::string fileWgtL2Path = construct_path("weight_L2.bin");
    std::string fileAccL2Path = construct_path("accumulator_L2.bin");
    std::string fileAddAccL2Path = construct_path("add_accumulator_L2.bin");
    std::string fileUopL2Path = construct_path("uop_L2.bin");
    std::string fileInsnL2Path = construct_path("instructions_L2.bin");
    std::string fileExpectedOutL2Path = construct_path("expected_out_L2.bin");
    std::string fileExpectedOutSramL2Path = construct_path("expected_out_sram_L2.bin");
    // Read binaries
    std::vector<int8_t> inpA_L2 = read_binary_file<int8_t>(fileInpL2Path);
    std::vector<int8_t> wgtB_L2 = read_binary_file<int8_t>(fileWgtL2Path);
    std::vector<int32_t> accX_L2 = read_binary_file<int32_t>(fileAccL2Path);
    std::vector<int32_t> accY_L2 = read_binary_file<int32_t>(fileAddAccL2Path);
    std::vector<uop_t> uop_buffer_L2 = read_binary_file<uop_t>(fileUopL2Path);
    std::vector<instruction_t> insn_buffer_L2 = read_binary_file<instruction_t>(fileInsnL2Path);
    std::vector<int8_t> expected_out_L2 = read_binary_file<int8_t>(fileExpectedOutL2Path);
    // Handle the output file differently
    std::vector<int8_t> expected_out_sram_L2 = read_binary_file<int8_t>(fileExpectedOutSramL2Path);
    std::vector<int8_t> outC_L2;
    size_t outC_L2_size = expected_out_sram_L2.size(); 
    outC_L2.resize(outC_L2_size);

    // LAYER 3
    std::string fileInpL3Path = construct_path("input_L3.bin");
    std::string fileWgtL3Path = construct_path("weight_L3.bin");
    std::string fileAccL3Path = construct_path("accumulator_L3.bin");
    std::string fileAddAccL3Path = construct_path("add_accumulator_L3.bin");
    std::string fileUopL3Path = construct_path("uop_L3.bin");
    std::string fileInsnL3Path = construct_path("instructions_L3.bin");
    std::string fileExpectedOutL3Path = construct_path("expected_out_L3.bin");
    std::string fileExpectedOutSramL3Path = construct_path("expected_out_sram_L3.bin");
    // Read binaries
    std::vector<int8_t> inpA_L3 = read_binary_file<int8_t>(fileInpL3Path);
    std::vector<int8_t> wgtB_L3 = read_binary_file<int8_t>(fileWgtL3Path);
    std::vector<int32_t> accX_L3 = read_binary_file<int32_t>(fileAccL3Path);
    std::vector<int32_t> accY_L3 = read_binary_file<int32_t>(fileAddAccL3Path);
    std::vector<uop_t> uop_buffer_L3 = read_binary_file<uop_t>(fileUopL3Path);
    std::vector<instruction_t> insn_buffer_L3 = read_binary_file<instruction_t>(fileInsnL3Path);
    std::vector<int8_t> expected_out_L3 = read_binary_file<int8_t>(fileExpectedOutL3Path);
    // Handle the output file differently
    std::vector<int8_t> expected_out_sram_L3 = read_binary_file<int8_t>(fileExpectedOutSramL3Path);
    std::vector<int8_t> outC_L3;
    size_t outC_L3_size = expected_out_sram_L3.size(); 
    outC_L3.resize(outC_L3_size);

    // LAYER 4
    std::string fileInpL4Path = construct_path("input_L4.bin");
    std::string fileWgtL4Path = construct_path("weight_L4.bin");
    std::string fileAccL4Path = construct_path("accumulator_L4.bin");
    std::string fileAddAccL4Path = construct_path("add_accumulator_L4.bin");
    std::string fileUopL4Path = construct_path("uop_L4.bin");
    std::string fileInsnL4Path = construct_path("instructions_L4.bin");
    std::string fileExpectedOutL4Path = construct_path("expected_out_L4.bin");
    std::string fileExpectedOutSramL4Path = construct_path("expected_out_sram_L4.bin");
    // Read binaries
    std::vector<int8_t> inpA_L4 = read_binary_file<int8_t>(fileInpL4Path);
    std::vector<int8_t> wgtB_L4 = read_binary_file<int8_t>(fileWgtL4Path);
    std::vector<int32_t> accX_L4 = read_binary_file<int32_t>(fileAccL4Path);
    std::vector<int32_t> accY_L4 = read_binary_file<int32_t>(fileAddAccL4Path);
    std::vector<uop_t> uop_buffer_L4 = read_binary_file<uop_t>(fileUopL4Path);
    std::vector<instruction_t> insn_buffer_L4 = read_binary_file<instruction_t>(fileInsnL4Path);
    std::vector<int8_t> expected_out_L4 = read_binary_file<int8_t>(fileExpectedOutL4Path);
    // Handle the output file differently
    std::vector<int8_t> expected_out_sram_L4 = read_binary_file<int8_t>(fileExpectedOutSramL4Path);
    std::vector<int8_t> outC_L4;
    size_t outC_L4_size = expected_out_sram_L4.size(); 
    outC_L4.resize(outC_L4_size);

    // LAYER 5
    std::string fileInpL5Path = construct_path("input_L5.bin");
    std::string fileWgtL5Path = construct_path("weight_L5.bin");
    std::string fileAccL5Path = construct_path("accumulator_L5.bin");
    std::string fileAddAccL5Path = construct_path("add_accumulator_L5.bin");
    std::string fileUopL5Path = construct_path("uop_L5.bin");
    std::string fileInsnL5Path = construct_path("instructions_L5.bin");
    std::string fileExpectedOutL5Path = construct_path("expected_out_L5.bin");
    std::string fileExpectedOutSramL5Path = construct_path("expected_out_sram_L5.bin");
    // Read binaries
    std::vector<int8_t> inpA_L5 = read_binary_file<int8_t>(fileInpL5Path);
    std::vector<int8_t> wgtB_L5 = read_binary_file<int8_t>(fileWgtL5Path);
    std::vector<int32_t> accX_L5 = read_binary_file<int32_t>(fileAccL5Path);
    std::vector<int32_t> accY_L5 = read_binary_file<int32_t>(fileAddAccL5Path);
    std::vector<uop_t> uop_buffer_L5 = read_binary_file<uop_t>(fileUopL5Path);
    std::vector<instruction_t> insn_buffer_L5 = read_binary_file<instruction_t>(fileInsnL5Path);
    std::vector<int8_t> expected_out_L5 = read_binary_file<int8_t>(fileExpectedOutL5Path);
    // Handle the output file differently
    std::vector<int8_t> expected_out_sram_L5 = read_binary_file<int8_t>(fileExpectedOutSramL5Path);
    std::vector<int8_t> outC_L5;
    size_t outC_L5_size = expected_out_sram_L5.size(); 
    outC_L5.resize(outC_L5_size);


    // Expected result
    std::string fileExpectedPath = construct_path("final.bin");
    std::vector<int8_t> final_expected = read_binary_file<int8_t>(fileExpectedPath);
    


    // ALLOCATE MEMORY SPACE
    // ---------------------

    // LAYER 1
    void* mem_inpA_L1 = VTAMemAlloc(inpA_L1.size() * sizeof(int8_t), 1);
    void* mem_wgtB_L1 = VTAMemAlloc(wgtB_L1.size() * sizeof(int8_t), 1);
    void* mem_accX_L1 = VTAMemAlloc(accX_L1.size() * sizeof(int32_t), 1);
    void* mem_accY_L1 = VTAMemAlloc(accY_L1.size() * sizeof(int32_t), 1);
    void* mem_outC_L1 = VTAMemAlloc(outC_L1_size * sizeof(int8_t), 1);
    void* mem_uop_L1 = VTAMemAlloc(uop_buffer_L1.size() * sizeof(uop_t), 1);
    void* mem_insn_L1 = VTAMemAlloc(insn_buffer_L1.size() * sizeof(instruction_t), 1);
    // Get physical address for INSN
    vta_phy_addr_t phy_add_insn_L1 = VTAMemGetPhyAddr(mem_insn_L1);

    // LAYER 2
    void* mem_inpA_L2 = VTAMemAlloc(inpA_L2.size() * sizeof(int8_t), 1);
    void* mem_wgtB_L2 = VTAMemAlloc(wgtB_L2.size() * sizeof(int8_t), 1);
    void* mem_accX_L2 = VTAMemAlloc(accX_L2.size() * sizeof(int32_t), 1);
    void* mem_accY_L2 = VTAMemAlloc(accY_L2.size() * sizeof(int32_t), 1);
    void* mem_outC_L2 = VTAMemAlloc(outC_L2_size * sizeof(int8_t), 1);
    void* mem_uop_L2 = VTAMemAlloc(uop_buffer_L2.size() * sizeof(uop_t), 1);
    void* mem_insn_L2 = VTAMemAlloc(insn_buffer_L2.size() * sizeof(instruction_t), 1);
    // Get physical address for INSN
    vta_phy_addr_t phy_add_insn_L2 = VTAMemGetPhyAddr(mem_insn_L2);

    // LAYER 3
    void* mem_inpA_L3 = VTAMemAlloc(inpA_L3.size() * sizeof(int8_t), 1);
    void* mem_wgtB_L3 = VTAMemAlloc(wgtB_L3.size() * sizeof(int8_t), 1);
    void* mem_accX_L3 = VTAMemAlloc(accX_L3.size() * sizeof(int32_t), 1);
    void* mem_accY_L3 = VTAMemAlloc(accY_L3.size() * sizeof(int32_t), 1);
    void* mem_outC_L3 = VTAMemAlloc(outC_L3_size * sizeof(int8_t), 1);
    void* mem_uop_L3 = VTAMemAlloc(uop_buffer_L3.size() * sizeof(uop_t), 1);
    void* mem_insn_L3 = VTAMemAlloc(insn_buffer_L3.size() * sizeof(instruction_t), 1);
    // Get physical address for INSN
    vta_phy_addr_t phy_add_insn_L3 = VTAMemGetPhyAddr(mem_insn_L3);

    // LAYER 4
    void* mem_inpA_L4 = VTAMemAlloc(inpA_L4.size() * sizeof(int8_t), 1);
    void* mem_wgtB_L4 = VTAMemAlloc(wgtB_L4.size() * sizeof(int8_t), 1);
    void* mem_accX_L4 = VTAMemAlloc(accX_L4.size() * sizeof(int32_t), 1);
    void* mem_accY_L4 = VTAMemAlloc(accY_L4.size() * sizeof(int32_t), 1);
    void* mem_outC_L4 = VTAMemAlloc(outC_L4_size * sizeof(int8_t), 1);
    void* mem_uop_L4 = VTAMemAlloc(uop_buffer_L4.size() * sizeof(uop_t), 1);
    void* mem_insn_L4 = VTAMemAlloc(insn_buffer_L4.size() * sizeof(instruction_t), 1);
    // Get physical address for INSN
    vta_phy_addr_t phy_add_insn_L4 = VTAMemGetPhyAddr(mem_insn_L4);

    // LAYER 5
    void* mem_inpA_L5 = VTAMemAlloc(inpA_L5.size() * sizeof(int8_t), 1);
    void* mem_wgtB_L5 = VTAMemAlloc(wgtB_L5.size() * sizeof(int8_t), 1);
    void* mem_accX_L5 = VTAMemAlloc(accX_L5.size() * sizeof(int32_t), 1);
    void* mem_accY_L5 = VTAMemAlloc(accY_L5.size() * sizeof(int32_t), 1);
    void* mem_outC_L5 = VTAMemAlloc(outC_L5_size * sizeof(int8_t), 1);
    void* mem_uop_L5 = VTAMemAlloc(uop_buffer_L5.size() * sizeof(uop_t), 1);
    void* mem_insn_L5 = VTAMemAlloc(insn_buffer_L5.size() * sizeof(instruction_t), 1);
    // Get physical address for INSN
    vta_phy_addr_t phy_add_insn_L5 = VTAMemGetPhyAddr(mem_insn_L5);


    // INITIALISE THE DRAM MEMORY
    // --------------------------

    // LAYER 1
    VTAMemCopyFromHost(mem_inpA_L1, inpA_L1.data(), inpA_L1.size() * sizeof(int8_t));
    VTAMemCopyFromHost(mem_wgtB_L1, wgtB_L1.data(), wgtB_L1.size() * sizeof(int8_t));
    VTAMemCopyFromHost(mem_accX_L1, accX_L1.data(), accX_L1.size() * sizeof(int32_t));
    VTAMemCopyFromHost(mem_accY_L1, accY_L1.data(), accY_L1.size() * sizeof(int32_t));
    VTAMemCopyFromHost(mem_outC_L1, outC_L1.data(), outC_L1_size * sizeof(int8_t)); 
    VTAMemCopyFromHost(mem_uop_L1, uop_buffer_L1.data(), uop_buffer_L1.size() * sizeof(uop_t));
    VTAMemCopyFromHost(mem_insn_L1, insn_buffer_L1.data(), insn_buffer_L1.size() * sizeof(instruction_t));

    // LAYER 2
    VTAMemCopyFromHost(mem_inpA_L2, inpA_L2.data(), inpA_L2.size() * sizeof(int8_t));
    VTAMemCopyFromHost(mem_wgtB_L2, wgtB_L2.data(), wgtB_L2.size() * sizeof(int8_t));
    VTAMemCopyFromHost(mem_accX_L2, accX_L2.data(), accX_L2.size() * sizeof(int32_t));
    VTAMemCopyFromHost(mem_accY_L2, accY_L2.data(), accY_L2.size() * sizeof(int32_t));
    VTAMemCopyFromHost(mem_outC_L2, outC_L2.data(), outC_L2_size * sizeof(int8_t)); 
    VTAMemCopyFromHost(mem_uop_L2, uop_buffer_L2.data(), uop_buffer_L2.size() * sizeof(uop_t));
    VTAMemCopyFromHost(mem_insn_L2, insn_buffer_L2.data(), insn_buffer_L2.size() * sizeof(instruction_t));

    // LAYER 3
    VTAMemCopyFromHost(mem_inpA_L3, inpA_L3.data(), inpA_L3.size() * sizeof(int8_t));
    VTAMemCopyFromHost(mem_wgtB_L3, wgtB_L3.data(), wgtB_L3.size() * sizeof(int8_t));
    VTAMemCopyFromHost(mem_accX_L3, accX_L3.data(), accX_L3.size() * sizeof(int32_t));
    VTAMemCopyFromHost(mem_accY_L3, accY_L3.data(), accY_L3.size() * sizeof(int32_t));
    VTAMemCopyFromHost(mem_outC_L3, outC_L3.data(), outC_L3_size * sizeof(int8_t)); 
    VTAMemCopyFromHost(mem_uop_L3, uop_buffer_L3.data(), uop_buffer_L3.size() * sizeof(uop_t));
    VTAMemCopyFromHost(mem_insn_L3, insn_buffer_L3.data(), insn_buffer_L3.size() * sizeof(instruction_t));

    // LAYER 4
    VTAMemCopyFromHost(mem_inpA_L4, inpA_L4.data(), inpA_L4.size() * sizeof(int8_t));
    VTAMemCopyFromHost(mem_wgtB_L4, wgtB_L4.data(), wgtB_L4.size() * sizeof(int8_t));
    VTAMemCopyFromHost(mem_accX_L4, accX_L4.data(), accX_L4.size() * sizeof(int32_t));
    VTAMemCopyFromHost(mem_accY_L4, accY_L4.data(), accY_L4.size() * sizeof(int32_t));
    VTAMemCopyFromHost(mem_outC_L4, outC_L4.data(), outC_L4_size * sizeof(int8_t)); 
    VTAMemCopyFromHost(mem_uop_L4, uop_buffer_L4.data(), uop_buffer_L4.size() * sizeof(uop_t));
    VTAMemCopyFromHost(mem_insn_L4, insn_buffer_L4.data(), insn_buffer_L4.size() * sizeof(instruction_t));

    // LAYER 5
    VTAMemCopyFromHost(mem_inpA_L5, inpA_L5.data(), inpA_L5.size() * sizeof(int8_t));
    VTAMemCopyFromHost(mem_wgtB_L5, wgtB_L5.data(), wgtB_L5.size() * sizeof(int8_t));
    VTAMemCopyFromHost(mem_accX_L5, accX_L5.data(), accX_L5.size() * sizeof(int32_t));
    VTAMemCopyFromHost(mem_accY_L5, accY_L5.data(), accY_L5.size() * sizeof(int32_t));
    VTAMemCopyFromHost(mem_outC_L5, outC_L5.data(), outC_L5_size * sizeof(int8_t)); 
    VTAMemCopyFromHost(mem_uop_L5, uop_buffer_L5.data(), uop_buffer_L5.size() * sizeof(uop_t));
    VTAMemCopyFromHost(mem_insn_L5, insn_buffer_L5.data(), insn_buffer_L5.size() * sizeof(instruction_t));


    // LAYER EXECUTION
    // ---------------
    // Allocate VTA device
    VTADeviceHandle vta_device = VTADeviceAlloc();
    int execution_flag;


    // EXECUTE LAYER 1
    execution_flag = VTADeviceRun(vta_device, phy_add_insn_L1, insn_buffer_L1.size(), 0);

    // Copy result back
    VTAMemCopyToHost(outC_L1.data(), mem_outC_L1, outC_L1_size * sizeof(int8_t)); 

    // RESHAPE
    inpA_L2 = reshape(
        outC_L1, //const std::vector<int8_t>& vector,
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

    VTAMemCopyFromHost(mem_inpA_L2, inpA_L2.data(), 112*160 * sizeof(int8_t));


    // EXECUTE LAYER 2
    execution_flag = VTADeviceRun(vta_device, phy_add_insn_L2, insn_buffer_L2.size(), 0);

    // Copy result back
    VTAMemCopyToHost(outC_L2.data(), mem_outC_L2, outC_L2_size * sizeof(int8_t)); 

    // RESHAPE
    inpA_L3 = reshape(
        outC_L2, //const std::vector<int8_t>& vector,
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
        true);//bool isSquare = true);

    VTAMemCopyFromHost(mem_inpA_L3, inpA_L3.data(), 25*16*16 * sizeof(int8_t));


    // EXECUTE LAYER 3
    execution_flag = VTADeviceRun(vta_device, phy_add_insn_L3, insn_buffer_L3.size(), 0);

    // Copy result back
    VTAMemCopyToHost(outC_L3.data(), mem_outC_L3, outC_L3_size * sizeof(int8_t)); 

    // RESHAPE
    // Not here (specific case)
    inpA_L4 = outC_L3;

    VTAMemCopyFromHost(mem_inpA_L4, inpA_L4.data(), 128*16 * sizeof(int8_t));


    // EXECUTE LAYER 4
    execution_flag = VTADeviceRun(vta_device, phy_add_insn_L4, insn_buffer_L4.size(), 0);

    // Copy result back
    VTAMemCopyToHost(outC_L4.data(), mem_outC_L4, outC_L4_size * sizeof(int8_t)); 

    // RESHAPE
    // Not here (specific case)
    inpA_L5 = outC_L4;

    VTAMemCopyFromHost(mem_inpA_L5, inpA_L5.data(), outC_L4_size * sizeof(int8_t));


    // EXECUTE LAYER 5
    execution_flag = VTADeviceRun(vta_device, phy_add_insn_L5, insn_buffer_L5.size(), 0);

    // Copy result back
    VTAMemCopyToHost(outC_L5.data(), mem_outC_L5, outC_L5_size * sizeof(int8_t)); 



    // FREE MEMORY
    // -----------

    // Free VTA device
    VTADeviceFree(vta_device);

    // Free LAYER 1
    VTAMemFree(mem_inpA_L1);
    VTAMemFree(mem_wgtB_L1);
    VTAMemFree(mem_accX_L1);
    VTAMemFree(mem_accY_L1);
    VTAMemFree(mem_outC_L1);
    VTAMemFree(mem_uop_L1);
    VTAMemFree(mem_insn_L1);

    // Free LAYER 2
    VTAMemFree(mem_inpA_L2);
    VTAMemFree(mem_wgtB_L2);
    VTAMemFree(mem_accX_L2);
    VTAMemFree(mem_accY_L2);
    VTAMemFree(mem_outC_L2);
    VTAMemFree(mem_uop_L2);
    VTAMemFree(mem_insn_L2);

    // Free LAYER 3
    VTAMemFree(mem_inpA_L3);
    VTAMemFree(mem_wgtB_L3);
    VTAMemFree(mem_accX_L3);
    VTAMemFree(mem_accY_L3);
    VTAMemFree(mem_outC_L3);
    VTAMemFree(mem_uop_L3);
    VTAMemFree(mem_insn_L3);

    // Free LAYER 4
    VTAMemFree(mem_inpA_L4);
    VTAMemFree(mem_wgtB_L4);
    VTAMemFree(mem_accX_L4);
    VTAMemFree(mem_accY_L4);
    VTAMemFree(mem_outC_L4);
    VTAMemFree(mem_uop_L4);
    VTAMemFree(mem_insn_L4);

    // Free LAYER 5
    VTAMemFree(mem_inpA_L5);
    VTAMemFree(mem_wgtB_L5);
    VTAMemFree(mem_accX_L5);
    VTAMemFree(mem_accY_L5);
    VTAMemFree(mem_outC_L5);
    VTAMemFree(mem_uop_L5);
    VTAMemFree(mem_insn_L5);


    // The program has failed
    if (execution_flag != 0)
    {
        return EXIT_FAILURE;
    }


    // GET THE RESULT
    // --------------
    printf("\n\n Final result= {");
    print_int8_vector(outC_L5.data(), outC_L5.size()); // Use the actual size
    printf("\n} \n\n");

    bool isCorrect = true;
    isCorrect = compare_vector(outC_L5.data(), final_expected.data(), final_expected.size());
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
    return lenet5_implementation();
}
