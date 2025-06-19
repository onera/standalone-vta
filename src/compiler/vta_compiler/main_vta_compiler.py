# IMPORT PACKAGES
# ---------------
import os
import sys

import numpy as np

import config.configuration as conf

import data_definition.matrix_generator as MG
import data_definition.matrix_split as MS
import data_definition.matrix_multiplication as MM
import data_definition.alu_operations as ALU
import data_definition.truncation as TR

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
    random_bound = 9

    # ---------------------------------------------
    # INIT MATRICES

    # Check if operations_dict defines matrix operations
    if not "MATRICES" in operations_dict:
        print("ERROR: the operation is not a matrix operations!\n\n")
        return 0

    # Get the size of the matrices
    A_row, A_col = operations_dict["MATRICES"][0]["INPUT"]
    B_row, B_col = operations_dict["MATRICES"][0]["WEIGHT"]
    C_row, C_col = (A_row, B_col)

    # Check size consistency
    if (A_col != B_row):
        raise Exception(f"ERROR: Matrices not consistent: A_col={A_col} != B_row={B_row}! \n\n")
    
    # Define the matrices
    if not "INPUT_VALUE" in operations_dict["MATRICES"][0]:
        A_matrix = MG.matrix_creation(n_row=A_row, n_col=A_col, isInitRandom=True, random_bound=random_bound, dtype=inp_dtype)
    else: # TODO: read the INPUT_VALUE (a binary file?)
        pass 
    if not "WEIGHT_VALUE" in operations_dict["MATRICES"][0]:
        B_matrix = MG.matrix_creation(n_row=B_row, n_col=B_col, isInitRandom=True, random_bound=random_bound, dtype=wgt_dtype)
    else: # TODO: read the WEIGHT_VALUE (a binary file?)
        pass
    if not "ACCUMULATOR" in operations_dict["MATRICES"][0]:
        X_matrix = MG.matrix_creation(n_row=C_row, n_col=C_col, isInitRandom=False, random_bound=random_bound, dtype=acc_dtype)
    else: 
        # Check the size consistency
        if ((operations_dict["MATRICES"][0]["ACCUMULATOR"][0] != C_row) 
           or (operations_dict["MATRICES"][0]["ACCUMULATOR"][1] != C_col)):
            raise Exception(f"ERROR: Matrices not consistent on ACCUMULATOR: should be [{C_row}, {C_col}]! \n\n")
        if not "ACCUMULATOR_VALUE" in operations_dict["MATRICES"][0]:
            X_matrix = MG.matrix_creation(n_row=C_row, n_col=C_col, isInitRandom=True, random_bound=random_bound, dtype=acc_dtype)
        else: # TODO: read the ACCUMULATOR_VALUE (a binary file?)  
            pass

    # ---------------------------------------------
    # APPLY HARDWARE CONSTRAINTS (pad + split)

    # Check if A is a vector or a matrix (i.e., A_row = 1)
    isSquare = False if (operations_dict["MATRICES"][0]["INPUT"][0] == 1) else True

    # Pad the matrix to make n_row and n_col a multiple of block_size
    A_padded = MG.matrix_padding(matrix=A_matrix, block_size=block_size, isWeight=False, isSquare=isSquare)
    B_padded = MG.matrix_padding(matrix=B_matrix, block_size=block_size, isWeight=True, isSquare=isSquare)
    X_padded = MG.matrix_padding(matrix=X_matrix, block_size=block_size, isWeight=False, isSquare=isSquare)

    # Split the matrix in submatrix of size (block_size, block_size)
    A_blocks, A_blocks_col = MS.matrix_splitting(matrix=A_padded, block_size=block_size, isWeight=False, isSquare=isSquare)
    B_blocks, B_blocks_col = MS.matrix_splitting(matrix=B_padded, block_size=block_size, isWeight=True, isSquare=isSquare)
    X_blocks, X_blocks_col = MS.matrix_splitting(matrix=X_padded, block_size=block_size, isWeight=False, isSquare=isSquare)

    # ---------------------------------------------
    # PERFORM MATRIX MULTIPLICATION

    ACC_ref = MM.matrix_multiplication(A_matrix, B_matrix, X_matrix, acc_dtype=acc_dtype)
    ACC_padded_ref = MM.matrix_multiplication(A_padded, B_padded, X_padded, acc_dtype=acc_dtype)
    ACC_blocks_ref, ACC_blocks_col = MS.matrix_splitting(matrix=ACC_padded_ref, block_size=block_size, isWeight=False, isSquare=isSquare)
    _, combinations = MM.block_matrix_multiply(A_blocks, B_blocks, A_blocks_col, B_blocks_col, block_size=block_size)

    # ---------------------------------------------
    # PERFORM ALU OPERATIONS

    # Define the intermediate ALU_matrix
    ALU_matrix = ACC_padded_ref.copy()

    # Create the dictionary for the ALU operations
    if not "ALU" in operations_dict:
        alu_operations_dict = {}
    else:
        alu_operations_dict = operations_dict["ALU"][0]

    # Execute the operations
    for key, value in alu_operations_dict.items():
        isIMM = True if key.endswith("_IMM") else False
        ALU_matrix = ALU.alu_operations(ALU_matrix, alu_operation=key, dst_idx=value[0], elem2=value[1], isIMM=isIMM)

    # ---------------------------------------------
    # TRUNCATE 

    C_matrix = TR.truncate(ALU_matrix, inp_dtype)

    # Split the matrix for binarisation
    C_blocks, C_blocks_col = MS.matrix_splitting(matrix=C_matrix, block_size=block_size, isWeight=False, isSquare=isSquare)
        

    # ---------------------------------------------
    # DEBUG
    if (debug):
        print("\nINITIAL MATRICES:")
        print(f"A_matrix ({A_matrix.shape}): \n{A_matrix}\n")
        print(f"B_matrix ({B_matrix.shape}): \n{B_matrix}\n")
        print(f"X_matrix ({X_matrix.shape}): \n{X_matrix}\n")

        print("\nPADDED MATRICES:")
        print(f"A_padded ({A_padded.shape}): \n{A_padded}\n")
        print(f"B_padded ({B_padded.shape}): \n{B_padded}\n")
        print(f"X_padded ({X_padded.shape}): \n{X_padded}\n")

        print("\n\nSPLITTED MATRICES:")
        i = 0
        print(f"A_blocks (blocks_col = {A_blocks_col})")
        for block in A_blocks:
            print("\n A", i)
            print(block)
            i = i + 1
        i = 0
        print(f"\n\nB_blocks (blocks_col = {B_blocks_col})")
        for block in B_blocks:
            print("\n B", i)
            print(block)
            i = i + 1
        i = 0
        print("\n\nTransposed B_blocks:")
        for block in B_blocks:
            print("\n Transposed B", i)
            print(block.transpose())
            i = i + 1
        i = 0
        print(f"\n\nX_blocks (blocks_col = {X_blocks_col})")
        for block in X_blocks:
            print("\n X", i)
            print(block)
            i = i + 1
        
        print("\n\nACC=A*B+X RESULTING MATRICES:")
        print(f"ACC_ref ({ACC_ref.shape}): \n{ACC_ref}\n")
        print(f"ACC_padded_ref ({ACC_padded_ref.shape}): \n{ACC_padded_ref}\n")
        print(f"\n\nACC_blocks_ref (blocks_col = {ACC_blocks_col})")
        i = 0
        for block in ACC_blocks_ref:
            print("\n ACC", i)
            print(block)
            i = i + 1
        print("\n\nACC=A*B+X by blocks COMBINATIONS:")
        for combination in combinations:
            print(combination)
    
        print("\n\nALU OPERATIONS:")
        for key, value in alu_operations_dict.items():
            print(f" {key}: {value}")
        print(f"\nALU_matrix ({ALU_matrix.shape}): \n{ALU_matrix}\n")


        print("\n\nOUTPUT MATRIX:")
        i = 0
        print(f"C_blocks (blocks_col = {C_blocks_col})")
        for block in C_blocks:
            print("\n C", i)
            print(block)
            i = i + 1

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
    # If there is no argument, take "config/template.json" and "config/vta_config.json"
    if len(sys.argv) == 1:
        print("WARNING: No argument given, the execution takes default values!\n\n")
        operations_file = "config/template.json"
        vta_config_file = "config/vta_config.json"
    # If there is only one argument, 
    elif len(sys.argv) == 2:
        print("WARNING: No vta configuration given, the execution takes default values!\n\n")
        operations_file = sys.argv[1]
        vta_config_file = "config/vta_config.json"
    # If there are two argument, 
    elif len(sys.argv) == 3:
        operations_file = sys.argv[1]
        vta_config_file = sys.argv[2]
    else: # Through an error
        print("python main_vta_compiler.py <path_operations>.json <vta_config>.json")
        sys.exit(1)

    # Parse the JSON files
    operations_dict = parse_json_to_dict(operations_file)
    vta_config_dict = parse_json_to_dict(vta_config_file)

    # Execute the main function
    main(operations_dict, vta_config_dict)
