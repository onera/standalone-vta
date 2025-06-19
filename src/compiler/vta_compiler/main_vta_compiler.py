# IMPORT PACKAGES
# ---------------
import os
import sys

import numpy as np

import config.configuration as conf
import data_definition.data_definition as DF

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
    inp_block_buffer_size = int( inp_buffer_size / block_size )
    acc_block_buffer_size = int( acc_buffer_size / block_size )

    # Others configuration
    random_bound = 4

    # ---------------------------------------------
    # DATA DEFINITION

    A_blocks, B_blocks, X_blocks, ALU_blocks, C_blocks, combinations = DF.data_definition(operations_dict, inp_dtype=inp_dtype, wgt_dtype=wgt_dtype, acc_dtype=acc_dtype,
                    block_size=block_size, random_bound=random_bound, debug=debug)


    # ---------------------------------------------
    # DATA BINARISATION

    # Setup the output folder (standalone-vta/compiler_output/)
    output_dir = compiler_output_setup()


    # Define the complete path of the files
    A_blocks_file_path = filepath_definition(output_dir, 'input.bin')
    B_blocks_file_path = filepath_definition(output_dir, 'weight.bin')
    X_blocks_file_path = filepath_definition(output_dir, 'accumulator.bin')
    C_blocks_file_path = filepath_definition(output_dir, 'expected_out.bin')

    # Write A_block matrix
    with open(A_blocks_file_path, 'wb') as f:
        for block in A_blocks:
            block.tofile(f)
    
    # Write B_block matrix (TO TRANSPOSE!)
    with open(B_blocks_file_path, 'wb') as f:
        for block in B_blocks:
            transposed = block.transpose()
            transposed.tofile(f)

    # Write X_block matrix
    with open(X_blocks_file_path, 'wb') as f:
        for block in X_blocks:
            block.tofile(f)
    
    # Write C_blocks (expected result)
    with open(C_blocks_file_path, 'wb') as f:
        for block in C_blocks:
            block.tofile(f)

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
        operations_file = "config/template.json"
        vta_config_file = "config/vta_config.json"
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
