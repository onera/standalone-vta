# IMPORT PACKAGES
# ---------------
import os
import sys

import numpy as np
import csv

import config.configuration as conf
import data_definition.data_definition as DF
import dram_allocation.dram_allocation as DA
import matrix_partitioning.matrix_partitioning as MP
import operations_definition.operations_definition as OP

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils.find_project_root import *
from utils.json_parser import *


###############################################


# MAIN FUNCTION
# -------------
def main(operations_dict, vta_config_dict, debug=True):
    # GET CONFIGURATION
    inp_dtype = conf.data_type(vta_config_dict["LOG_INP_WIDTH"])
    wgt_dtype = conf.data_type(vta_config_dict["LOG_WGT_WIDTH"])
    acc_dtype = conf.data_type(vta_config_dict["LOG_ACC_WIDTH"])

    block_size = 2**vta_config_dict["LOG_BLOCK"]

    inp_buffer_size = conf.buffer_size(vta_config_dict["LOG_INP_BUFF_SIZE"], vta_config_dict["LOG_INP_WIDTH"], block_size)
    wgt_buffer_size = conf.buffer_size(vta_config_dict["LOG_WGT_BUFF_SIZE"], vta_config_dict["LOG_WGT_WIDTH"], block_size*block_size)
    acc_buffer_size = conf.buffer_size(vta_config_dict["LOG_ACC_BUFF_SIZE"], vta_config_dict["LOG_ACC_WIDTH"], block_size)
    out_buffer_size = acc_buffer_size

    uop_buffer_size = conf.buffer_size(vta_config_dict["LOG_UOP_BUFF_SIZE"], 5, 1)

    # Others configuration
    random_bound = 4


    # ---------------------------------------------
    # DATA DEFINITION
    A_blocks, A_blocks_col, B_blocks, B_blocks_col, \
        X_blocks, Y_blocks, ALU_blocks, C_blocks, C_init, X_blocks_col, \
        alu_operations, idx_to_store, \
        flag_dict = \
            DF.data_definition(operations_dict, inp_dtype=inp_dtype, wgt_dtype=wgt_dtype, acc_dtype=acc_dtype,
                               block_size=block_size, random_bound=random_bound, debug=debug)


    # ---------------------------------------------
    # DRAM ALLOCATION

    # Force an allocation size for OUT
    forced_allocation_size = sum(matrix.nbytes for matrix in ALU_blocks)
    # Create the object to allocate
    object_list = [("INP", A_blocks),
                   ("WGT", B_blocks),
                   ("ACC", X_blocks),
                   ("ACC_BIS", Y_blocks),
                   ("OUT", C_blocks, forced_allocation_size),
                   ("UOP", [], 4)]

    # Get the offsets
    if "BASE_ADDRESS" in operations_dict:
        base_address = int(operations_dict["BASE_ADDRESS"], base=16)
    else:
        base_address = 0x0000
    if "DRAM_OFFSET" in operations_dict:
        dram_offset = int(operations_dict["DRAM_OFFSET"], base=16)
    else:
        dram_offset = 0x0000


    # Allocate the object
    base_addresses_list, current_dram_addr = \
        DA.dram_allocation(object_list, base_addr=base_address, block_size=block_size, 
                           inp_dtype=inp_dtype, wgt_dtype=wgt_dtype, acc_dtype=acc_dtype,
                           dram_offset=dram_offset, debug=debug)


    # ---------------------------------------------
    # MATRIX PARTITIONING

    # Compute the data for matrix partitioning
    if (flag_dict["doGemm"] == True):
        nb_A = len(A_blocks)
        nb_B = len(B_blocks)
    else:
        nb_A = 0
        nb_B = 0
    nb_X = len(X_blocks)

    # Select a strategy in case of overfitting
    strategy_selector = 1

    # Apply matrix partitioning (check is overfit then applies selected trategy)
    strategy, flag_dict = \
        MP.matrix_partitioning(nb_A=nb_A, A_blocks_col=A_blocks_col, nb_B=nb_B, B_blocks_col=B_blocks_col, 
                               nb_X=nb_X, X_blocks_col=X_blocks_col,
                               inp_buffer_size=inp_buffer_size, wgt_buffer_size=wgt_buffer_size, 
                               acc_buffer_size=acc_buffer_size, out_buffer_size=out_buffer_size,
                               alu_operations=alu_operations, idx_to_store=idx_to_store,
                               flag_dict=flag_dict,
                               strategy_selector=strategy_selector, block_size=block_size,
                               debug=debug)
	

    # ---------------------------------------------
    # OPERATIONS DEFINITION

    insn_buffer, uop_buffer = \
        OP.operations_definition(strategy=strategy, dram_addresses=base_addresses_list,
                                 operations_dict=operations_dict, flag_dict=flag_dict,
                                 block_size=block_size, uop_buffer_size=uop_buffer_size,
                                 A_blocks_col=A_blocks_col, B_blocks_col=B_blocks_col, X_blocks_col=X_blocks_col,
                                 debug=debug)
    
    # Update DRAM allocation
    object_list = [("UOP", uop_buffer),
                   ("INSN", insn_buffer)]
    updated_addr, current_dram_addr = \
        DA.dram_allocation(object_list, base_addr=current_dram_addr-4, block_size=block_size, 
                           inp_dtype=inp_dtype, wgt_dtype=wgt_dtype, acc_dtype=acc_dtype,
                           dram_offset=dram_offset, debug=debug)
    base_addresses_list[-1] = updated_addr[0]
    base_addresses_list.append(updated_addr[1])


    # ---------------------------------------------
    # DATA BINARISATION

    # Get the name of the execution
    if "NAME" in operations_dict:
        name = operations_dict["NAME"]
    else:
        name = ''
    # Setup the output folder (standalone-vta/compiler_output/)
    output_dir = compiler_output_setup()

    # MATRICES
    # Define the complete path of the files
    A_blocks_file_path = filepath_definition(output_dir, 'input'+name+'.bin')
    B_blocks_file_path = filepath_definition(output_dir, 'weight'+name+'.bin')
    X_blocks_file_path = filepath_definition(output_dir, 'accumulator'+name+'.bin')
    Y_blocks_file_path = filepath_definition(output_dir, 'add_accumulator'+name+'.bin')
    C_blocks_file_path = filepath_definition(output_dir, 'expected_out'+name+'.bin')
    C_init_file_path = filepath_definition(output_dir, 'out_init'+name+'.bin')
    ALU_blocks_file_path = filepath_definition(output_dir, 'expected_out_sram'+name+'.bin')

    # Write A_blocks matrix
    with open(A_blocks_file_path, 'wb') as f:
        for block in A_blocks:
            block.tofile(f)
    
    # Write B_blocks matrix (TO TRANSPOSE!)
    with open(B_blocks_file_path, 'wb') as f:
        for block in B_blocks:
            transposed = block.transpose()
            transposed.tofile(f)

    # Write X_blocks matrix
    with open(X_blocks_file_path, 'wb') as f:
        for block in X_blocks:
            block.tofile(f)

    # Write Y_blocks matrix
    with open(Y_blocks_file_path, 'wb') as f:
        for block in Y_blocks:
            block.tofile(f)
    
    # Write C_blocks (expected result)
    with open(C_blocks_file_path, 'wb') as f:
        for block in C_blocks:
            block.tofile(f)
    
    # Write the C_init (init the SRAM buffer for cycle-accurate simulator)
    with open(C_init_file_path, 'wb') as f:
        C_init.tofile(f)
    
    # Write ALU_blocks (expected result before store)
    with open(ALU_blocks_file_path, 'wb') as f:
        for block in ALU_blocks:
            block.tofile(f)


    # DRAM ALLOCATION
    base_addresses_file_path = filepath_definition(output_dir, 'memory_addresses'+name+'.csv')

    with open(base_addresses_file_path, 'w', newline='') as csvfile:
        writer = csv.writer(csvfile)
        for obj_addr in base_addresses_list:
            writer.writerow([obj_addr['type'], obj_addr['physical_base_address'], obj_addr['logical_base_address']])

    
    # OPERATIONS DEFINITION
    insn_file_path = filepath_definition(output_dir, 'instructions'+name+'.bin')
    uop_file_path = filepath_definition(output_dir, 'uop'+name+'.bin')
    with open(insn_file_path, "wb") as f:
        for insn in insn_buffer:
            f.write(insn)
    with open(uop_file_path, "wb") as f:
        for uop in uop_buffer:
            f.write(uop)
            

    # ---------------------------------------------
    # DEBUG

    if (debug):
        # Write output_dir
        print(f"\n\nBinaries successfully written at: {output_dir}\n")

    # ---------------------------------------------
    # RETURN 0

    return 0


###############################################


# EXECUTE MAIN FUNCTION
# ---------------------
if __name__ == "__main__": 
    """
    To execute: 
        > python main_vta_compiler.py <path_operations>.json <vta_config>.json
    
    1st argument define the operation to perform.
    2nd argument define the hardware configuration.
    """
    debug = True

    # If there is no argument, take "config/template.json" and "config/vta_config.json"
    if len(sys.argv) == 1:
        print("WARNING: No argument given, the execution takes default values!\n\n")
        operations_file = "../../../examples/matrix_operations/matrix_16x16.json"
        vta_config_file = "../../../config/vta_config.json"
    # If there is only one argument 
    elif len(sys.argv) == 2:
        print("WARNING: No vta configuration given, the execution takes default values!\n\n")
        operations_file = sys.argv[1]
        vta_config_file = "config/vta_config.json"
    # If there are two arguments
    elif len(sys.argv) == 3:
        operations_file = sys.argv[1]
        vta_config_file = sys.argv[2]
    # If there are three arguments
    elif len(sys.argv) == 4:
        operations_file = sys.argv[1]
        vta_config_file = sys.argv[2]
        debug = False if (sys.argv[3] == "False") else True
    else: # Through an error
        print("python main_vta_compiler.py <path_operations>.json <vta_config>.json")
        sys.exit(1)

    # Parse the JSON files
    operations_dict = parse_json_to_dict(operations_file)
    vta_config_dict = parse_json_to_dict(vta_config_file)

    # Execute the main function
    main(operations_dict, vta_config_dict, debug=debug)
