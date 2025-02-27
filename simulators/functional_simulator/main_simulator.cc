/***************************
    PRE-PROCESSOR DIRECTIVES
****************************/
#include "simulator_header.h"


/****************
    MAIN FUNCTION
*****************/
int main()
{
    // Execute the simulator (using binary files)
    execute_simulator();
    
    // Return 0 if the program has been successfully executed
    return 0;
}


/********************
    EXECUTE_SIMULATOR
*********************/
/*!
 * \brief Execute simulator using binary files
 */
int execute_simulator(void)
{
    // Print the function name
    printf("\nExecute simulator:\n");

    // Folder location
    // Define the current location of main_simulator.cc
    std::filesystem::path currentPath = std::filesystem::current_path();

    // Define the path for the input files
    std::filesystem::path InpPath = currentPath / "binary_input_files" / "input.bin";
    std::string fileInpPath = InpPath.string();
    std::filesystem::path WgtPath = currentPath / "binary_input_files" / "weight.bin";
    std::string fileWgtPath = WgtPath.string();
    std::filesystem::path AccPath = currentPath / "binary_input_files" / "accumulator.bin";
    std::string fileAccPath = AccPath.string();
    std::filesystem::path UopPath = currentPath / "binary_input_files" / "uop.bin";
    std::string fileUopPath = UopPath.string();
    std::filesystem::path InsnPath = currentPath / "binary_input_files" / "instructions.bin";
    std::string fileInsnPath = InsnPath.string();
    std::filesystem::path ExpectedOutPath = currentPath / "binary_input_files" / "expected_out.bin";
    std::string fileExpectedOutPath = ExpectedOutPath.string();

    // File size variable
    long file_size = 0;
    long out_file_size = 0;

    // DATA DEFINITION
    // ---------------
    // Input (A - INP) -> read the input.bin file (rb to read a binary file)
    FILE * pFileInp;
    pFileInp = fopen(fileInpPath.c_str(), "rb"); 

    // Return an error if the file does not open:
    if (pFileInp == nullptr){
        fclose(pFileInp); // Close the file
        perror("ERROR: program fails at opening the INP binary file"); // Return an error
        return 1;
    }

    // Move to the end of the file 
    fseek(pFileInp, 0, SEEK_END);
    // Return the size of the size by returning the position of the cursor
    file_size = ftell(pFileInp);
    // Come back to the beginning of the file
    fseek(pFileInp, 0, SEEK_SET);

    // Read the file
    int8_t inpA[file_size/sizeof(int8_t)] = {0}; 
    fread(&inpA, sizeof(inpA[0]), sizeof(inpA)/sizeof(inpA[0]), pFileInp); // (ptr, size, count, stream)

    // Close the file
    fclose(pFileInp);
    

    // Weight (B - WGT) -> read the weight.bin file (rb to read a binary file)
    FILE * pFileWgt;
    pFileWgt = fopen(fileWgtPath.c_str(), "rb"); 

    // Return an error if the file does not open:
    if (pFileWgt == nullptr){
        fclose(pFileWgt); // Close the file
        perror("ERROR: program fails at opening the WGT binary file");
        return 1;
    }

    // Move to the end of the file 
    fseek(pFileWgt, 0, SEEK_END);
    // Return the size of the size by returning the position of the cursor
    file_size = ftell(pFileWgt);
    // Come back to the beginning of the file
    fseek(pFileWgt, 0, SEEK_SET);

    // Read the file
    int8_t wgtB[file_size/sizeof(int8_t)] = {0}; 
    fread(&wgtB, sizeof(wgtB[0]), sizeof(wgtB)/sizeof(wgtB[0]), pFileWgt); // (ptr, size, count, stream)

    // Close the file
    fclose(pFileWgt);
    

    // ACCUMULATOR (X - ACC) -> read the accumulator.bin file (rb to read a binary file)
    FILE * pFileAcc;
    pFileAcc = fopen(fileAccPath.c_str(), "rb"); 

    // Return an error if the file does not open:
    if (pFileAcc == nullptr){
        fclose(pFileAcc); // Close the file
        perror("ERROR: program fails at opening the ACC binary file");
        return 1;
    }

    // Move to the end of the file 
    fseek(pFileAcc, 0, SEEK_END);
    // Return the size of the size by returning the position of the cursor
    file_size = ftell(pFileAcc);
    // Come back to the beginning of the file
    fseek(pFileAcc, 0, SEEK_SET);

    // Read the file
    int32_t accX[file_size/sizeof(int32_t)] = {0}; 
    fread(&accX, sizeof(accX[0]), sizeof(accX)/sizeof(accX[0]), pFileAcc); // (ptr, size, count, stream)

    // Close the file
    fclose(pFileAcc);


    // Output (C - OUT)
    FILE * pFileExpectedOut;
    pFileExpectedOut = fopen(fileExpectedOutPath.c_str(), "rb"); 

    // No expected result if the file does not open:
    if (pFileExpectedOut == nullptr){
        // Give the biggest size to the out vector
        out_file_size = 16*256; // 256 vectors of 16 elements maximum (= 4096 elements)
    }
    else { // Take the expected size file
    // Move to the end of the file 
    fseek(pFileExpectedOut, 0, SEEK_END);
    // Return the size of the size by returning the position of the cursor
    out_file_size = ftell(pFileExpectedOut);

    // Close the file
    fclose(pFileExpectedOut);
    }

    // Define the size:
    long out_size = out_file_size/sizeof(int8_t);
    printf("\n\nOut_size = %ld\n\n", out_size);
    int8_t outC[out_size] = {0}; // (16*256 = MAX, else CORE DUMPED)
    init_vector_values(outC, sizeof(outC), false, 0); // (vector, size, random_value, seed)


    // UOP DEFINITION
    // --------------
    // Read the uop.bin file (rb to read a binary file)
    FILE * pFileUop;
    pFileUop = fopen(fileUopPath.c_str(), "rb"); 

    // Return an error if the file does not open:
    if (pFileUop == nullptr){
        fclose(pFileUop); // Close the file
        perror("ERROR: program fails at opening the UOP binary file");
        return 1;
    }

    // Move to the end of the file 
    fseek(pFileUop, 0, SEEK_END);
    // Return the size of the size by returning the position of the cursor
    file_size = ftell(pFileUop);
    // Come back to the beginning of the file
    fseek(pFileUop, 0, SEEK_SET);

    // Read the file
    uop_t uop_buffer[file_size/sizeof(uop_t)] = {0}; 
    fread(&uop_buffer, sizeof(uop_buffer[0]), sizeof(uop_buffer)/sizeof(uop_buffer[0]), pFileUop); // (ptr, size, count, stream)

    // Close the file
    fclose(pFileUop);


    // INSTRUCTION DEFINITION
    // ----------------------
    // Read the instructions.bin file (rb to read a binary file)
    FILE * pFileInsn;
    pFileInsn = fopen(fileInsnPath.c_str(), "rb"); 

    // Return an error if the file does not open:
    if (pFileInsn == nullptr){
        fclose(pFileInsn); // Close the file
        perror("ERROR: program fails at opening the INSN binary file");
        return 1;
    }

    // Move to the end of the file 
    fseek(pFileInsn, 0, SEEK_END);
    // Return the size of the size by returning the position of the cursor
    file_size = ftell(pFileInsn);
    // Come back to the beginning of the file
    fseek(pFileInsn, 0, SEEK_SET);

    // Read the file
    instruction_t insn_buffer[file_size/sizeof(instruction_t)] = {0}; 
    fread(&insn_buffer, sizeof(insn_buffer[0]), sizeof(insn_buffer)/sizeof(insn_buffer[0]), pFileInsn); // (ptr, size, count, stream)

    // Close the file
    fclose(pFileInsn);


    // SIMULATOR EXECUTION
    // -------------------
    // Allocate memory space
    void * mem_inpA = VTAMemAlloc(sizeof(inpA), 1); // (size n Bytes, cached) 
    void * mem_wgtB = VTAMemAlloc(sizeof(wgtB), 1); 
    void * mem_outC = VTAMemAlloc(sizeof(outC), 1); 
    void * mem_uop  = VTAMemAlloc(sizeof(uop_buffer), 1);
    void * mem_accX = VTAMemAlloc(sizeof(accX), 1); 
    void * mem_insn = VTAMemAlloc(sizeof(insn_buffer), 1); // (size n Bytes, cached) 

    // Get the physical address of the allocation (used for INSTRUCTIONS)
    vta_phy_addr_t phy_add_insn = VTAMemGetPhyAddr(mem_insn); // (buffer)
    vta_phy_addr_t phy_add_inpA = VTAMemGetPhyAddr(mem_inpA); // (buffer)
    vta_phy_addr_t phy_add_wgtB = VTAMemGetPhyAddr(mem_wgtB); // (buffer)
    vta_phy_addr_t phy_add_outC = VTAMemGetPhyAddr(mem_outC); // (buffer)
    vta_phy_addr_t phy_add_uop = VTAMemGetPhyAddr(mem_uop); // (buffer)
    vta_phy_addr_t phy_add_accX = VTAMemGetPhyAddr(mem_accX); // (buffer)

    printf("\nDEBUG: VIRTUAL ADDR (PhyAddr / vectorSize) \n\t inpA = 0x%x, wgtB = 0x%x, outC = 0x%x, uop = 0x%x, accX = 0x%x \n\t insn = 0x%x \n", phy_add_inpA/16, phy_add_wgtB/256, phy_add_outC/16, phy_add_uop/4, phy_add_accX/64, phy_add_insn/16);

    // Copy the data from host to allocated memories
    VTAMemCopyFromHost(mem_inpA, &inpA, sizeof(inpA)); // (dst, src, size in Bytes) 
    VTAMemCopyFromHost(mem_wgtB, &wgtB, sizeof(wgtB));
    VTAMemCopyFromHost(mem_accX, &accX, sizeof(accX));
    VTAMemCopyFromHost(mem_outC, &outC, sizeof(outC));
    VTAMemCopyFromHost(mem_uop, &uop_buffer, sizeof(uop_buffer));
    VTAMemCopyFromHost(mem_insn, &insn_buffer, sizeof(insn_buffer)); 

    // Allocate device
    VTADeviceHandle vta_device = VTADeviceAlloc();

    // Run device (0 = success, 1 = timeout) 
    int execution_flag = VTADeviceRun(vta_device, phy_add_insn, sizeof(insn_buffer)/sizeof(insn_buffer[0]), 0); // (device, insn_phy_addr, insn_count, wait_cycles) // > wait_cycles not used!
    printf("\nThe execution returns: %d \n\t(return 0 if running is successful, 1 if timeout)\n", execution_flag);

    // Free device
    VTADeviceFree(vta_device); // (VTADeviceHandle)

    // Return the data to the host (update outC)
    VTAMemCopyToHost(&outC, mem_outC, sizeof(outC)); // (dst, src, size)
    
    // Free memory space
    VTAMemFree(mem_inpA); // (buffer)
    VTAMemFree(mem_wgtB); 
    VTAMemFree(mem_accX); 
    VTAMemFree(mem_outC);
    VTAMemFree(mem_uop);
    VTAMemFree(mem_insn); 


    // GET THE RESULT
    // --------------
    printf("\n\nRESULT:");

    printf("\ninpA = {");
    print_int8_vector(inpA, sizeof(inpA)); // (vector, size)
    printf("\n} \n");

    printf("\nwgtB = {");
    print_int8_vector(wgtB, sizeof(wgtB)); // (vector, size)
    printf("\n} \n\n");

    printf("\naccX = {");
    print_int32_vector(accX, sizeof(accX)); // (vector, size)
    printf("\n} \n\n");

    printf("\noutC = {");
    print_int8_vector(outC, sizeof(outC)); // (vector, size)
    printf("\n} \n\n");


    // END!
    // ----
    // Return no error code
    return 0;
}
