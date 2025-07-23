# IMPORT PACKAGES
# ---------------
import os
import sys

import numpy as np

import data_definition.matrix_generator as MG
import data_definition.matrix_split as MS
import data_definition.matrix_multiplication as MM
import data_definition.alu_operations as ALU
import data_definition.truncation as TR

###############################################

# MAIN FUNCTION
# -------------
def data_definition(operations_dict, inp_dtype=np.int8, wgt_dtype=np.int8, acc_dtype=np.int32,
                    block_size=16, random_bound=1, debug=True):
    # Check if operations_dict defines matrix operations
    if not "MATRICES" in operations_dict:
        raise Exception(f"ERROR: the operation is not a matrix operations!\n\n")

    # Get the size of the matrices for performing a GeMM
    doGemm = False
    if "INPUT" in operations_dict["MATRICES"][0] \
      and "WEIGHT" in operations_dict["MATRICES"][0]:
        doGemm = True
        A_row, A_col = operations_dict["MATRICES"][0]["INPUT"]
        B_row, B_col = operations_dict["MATRICES"][0]["WEIGHT"]
        C_row, C_col = (A_row, B_col)

        # Check size consistency
        if (A_col != B_row):
            raise Exception(f"ERROR: Matrices not consistent: A_col={A_col} != B_row={B_row}! \n\n")
        
        # Define the values of the elements within the matrices
        if not "INPUT_VALUES" in operations_dict["MATRICES"][0]:
            A_matrix = MG.matrix_creation(n_row=A_row, n_col=A_col, isInitRandom=True, random_bound=random_bound, dtype=inp_dtype)
        else: # TODO: read the INPUT_VALUE (a binary file?)
            pass 
        if not "WEIGHT_VALUES" in operations_dict["MATRICES"][0]:
            B_matrix = MG.matrix_creation(n_row=B_row, n_col=B_col, isInitRandom=True, random_bound=random_bound, dtype=wgt_dtype)
        else: # TODO: read the WEIGHT_VALUE (a binary file?)
            pass
    
    if "ACCUMULATOR" in operations_dict["MATRICES"][0]:
        # Check the consistency or get the dimension
        if (doGemm == True):
            if ((operations_dict["MATRICES"][0]["ACCUMULATOR"][0] != C_row) 
             or (operations_dict["MATRICES"][0]["ACCUMULATOR"][1] != C_col)):
                raise Exception(f"ERROR: Matrices not consistent on ACCUMULATOR: should be [{C_row}, {C_col}]! \n\n")
        else:
            C_row, C_col = operations_dict["MATRICES"][0]["ACCUMULATOR"]
            A_row, A_col = (C_row, block_size)
            B_row, B_col = (block_size, C_col)
            A_matrix = MG.matrix_creation(n_row=A_row, n_col=A_col, isInitRandom=False, dtype=inp_dtype)
            B_matrix = MG.matrix_creation(n_row=B_row, n_col=B_col, isInitRandom=False, dtype=wgt_dtype)

        # Define the values of the elements within the accumulator
        if not "ACCUMULATOR_VALUE" in operations_dict["MATRICES"][0]:
            X_matrix = MG.matrix_creation(n_row=C_row, n_col=C_col, isInitRandom=True, random_bound=random_bound, dtype=acc_dtype)
        else: # TODO: read the ACCUMULATOR_VALUE (a binary file?)  
            pass
    
    else: #not "ACCUMULATOR" in operations_dict["MATRICES"][0]
        # Init the accumulator to 0
        X_matrix = MG.matrix_creation(n_row=C_row, n_col=C_col, isInitRandom=False, dtype=acc_dtype)

    
    # Second ACCUMULATOR input
    if "ADD_ACCUMULATOR" in operations_dict["MATRICES"][0]:
        # Check the consistency
        if ((operations_dict["MATRICES"][0]["ADD_ACCUMULATOR"][0] != C_row) 
        or (operations_dict["MATRICES"][0]["ADD_ACCUMULATOR"][1] != C_col)):
            raise Exception(f"ERROR: Matrices not consistent on ADD_ACCUMULATOR: should be [{C_row}, {C_col}]! \n\n")
        # Create a flag
        doAddMatrix = True
        # Define the value 
        if not "ADD_ACCUMULATOR_VALUE" in operations_dict["MATRICES"][0]:
            Y_matrix = MG.matrix_creation(n_row=C_row, n_col=C_col, isInitRandom=True, random_bound=random_bound, dtype=acc_dtype)
        else: # TODO: read the ACCUMULATOR_VALUE (a binary file?)  
            pass
    else:
        # Create a flag
        doAddMatrix = False
        # Create an empty matrix
        Y_matrix = MG.matrix_creation(n_row=0, n_col=0, isInitRandom=True, random_bound=random_bound, dtype=acc_dtype)

    

    # Initialisation of the output for simulator instantiation
    C_init = MG.matrix_creation(n_row=C_row, n_col=C_col, isInitRandom=False, dtype=inp_dtype)


    # ---------------------------------------------
    # APPLY HARDWARE CONSTRAINTS (pad + split)

    # Check if A is a vector or a matrix (i.e., A_row = 1)
    isSquare = True # TODO: For now, always square
    #isSquare = False if (operations_dict["MATRICES"][0]["INPUT"][0] == 1) else True

    # Pad the matrix to make n_row and n_col a multiple of block_size
    A_padded = MG.matrix_padding(matrix=A_matrix, block_size=block_size, isWeight=False, isSquare=isSquare)
    B_padded = MG.matrix_padding(matrix=B_matrix, block_size=block_size, isWeight=True, isSquare=isSquare)
    X_padded = MG.matrix_padding(matrix=X_matrix, block_size=block_size, isWeight=False, isSquare=isSquare)
    Y_padded = MG.matrix_padding(matrix=Y_matrix, block_size=block_size, isWeight=False, isSquare=isSquare)

    # Split the matrix in submatrix of size (block_size, block_size)
    A_blocks, A_blocks_col = MS.matrix_splitting(matrix=A_padded, block_size=block_size, isWeight=False, isSquare=isSquare)
    B_blocks, B_blocks_col = MS.matrix_splitting(matrix=B_padded, block_size=block_size, isWeight=True, isSquare=isSquare)
    X_blocks, X_blocks_col = MS.matrix_splitting(matrix=X_padded, block_size=block_size, isWeight=False, isSquare=isSquare)
    Y_blocks, _ = MS.matrix_splitting(matrix=Y_padded, block_size=block_size, isWeight=False, isSquare=isSquare)

    # ---------------------------------------------
    # PERFORM MATRIX MULTIPLICATION

    ACC_ref = MM.matrix_multiplication(A_matrix, B_matrix, X_matrix, acc_dtype=acc_dtype)
    ACC_padded_ref = MM.matrix_multiplication(A_padded, B_padded, X_padded, acc_dtype=acc_dtype)
    ACC_blocks_ref, ACC_blocks_col = MS.matrix_splitting(matrix=ACC_padded_ref, block_size=block_size, isWeight=False, isSquare=isSquare)
    _, combinations = MM.block_matrix_multiply(A_blocks, B_blocks, A_blocks_col, B_blocks_col, block_size=block_size)

    # ---------------------------------------------
    # PERFORM ALU OPERATIONS

    # Define the intermediate ALU_matrix
    if (doAddMatrix == True):
        ALU_matrix = X_padded + Y_padded
    else:
        ALU_matrix = ACC_padded_ref.copy()

    # Create the dictionary for the ALU operations
    #   (for ALU vector-vector operation, the source vector can be deleted)
    alu_operations_list, idx_to_store = ALU.create_alu_operations_list(operations_dict=operations_dict, nb_C_blocks=len(ACC_blocks_ref), C_blocks_col=ACC_blocks_col, block_size=block_size)

    # Execute the operations: ["OPS", [DST, SRC]] or ["OPS", [DST, SRC, NB_ITERATION]]
    for alu_ops in alu_operations_list:
        # Check if the operation is unique or iterative
        if (len(alu_ops[1]) == 3): # Iterative: ["OPS", [[first DST idx, step], [first SRC idx, step], NB_ITERATION]]
            for nb in range(0, alu_ops[1][2]):
                # Get the current indexes
                elem_dst = alu_ops[1][0][0] + alu_ops[1][0][1] * nb # 1st idx + step * nb

                 # Check the type of operation (vector-scalar or vector-vector)
                if (alu_ops[0].endswith("_IMM") or alu_ops[0] == "RELU"): # Vector-scalar
                    isIMM = True
                    elem_src = alu_ops[1][1]
                else: # Vector-vector: the index of the second vector can be deleted
                    isIMM = False
                    elem_src = alu_ops[1][1][0] + alu_ops[1][1][1] * nb
                ALU_matrix = ALU.alu_operations(ALU_matrix, alu_operation=alu_ops[0], dst_idx=elem_dst, elem2=elem_src, isIMM=isIMM)

        else: # Unique
             # Check the type of operation (vector-scalar or vector-vector)
            if (alu_ops[0].endswith("_IMM")): # Vector-scalar
                isIMM = True
            else: # Vector-vector: the index of the second vector can be deleted
                isIMM = False
            ALU_matrix = ALU.alu_operations(ALU_matrix, alu_operation=alu_ops[0], dst_idx=alu_ops[1][0], elem2=alu_ops[1][1], isIMM=isIMM)

    # ---------------------------------------------
    # TRUNCATE AND CLEAN OUTPUT

    # Truncate ALU_matrix
    ALU_trunc = TR.truncate(ALU_matrix, inp_dtype)

    # Split ALU_trunc for expected result before store (final output buffer)
    ALU_blocks, C_blocks_col = MS.matrix_splitting(matrix=ALU_trunc, block_size=block_size, isWeight=False, isSquare=isSquare)

    # Remove non-necessary row in ALU to get C
    padding = ACC_padded_ref.shape[0] - C_row
    C_blocks = ALU.delete_matrix_row(ALU_blocks, blocks_col=C_blocks_col, block_size=block_size, idx_to_store=idx_to_store, matrix_height=C_row, padding=padding)

    # ---------------------------------------------
    # DEBUG

    if (debug):
        print("\nINITIAL MATRICES:")
        print(f"A_matrix ({A_matrix.shape}): \n{A_matrix}\n")
        print(f"B_matrix ({B_matrix.shape}): \n{B_matrix}\n")
        print(f"X_matrix ({X_matrix.shape}): \n{X_matrix}\n")

        print("\nPADDED MATRICES:")
        if (doGemm):
            print(f"A_padded ({A_padded.shape}): \n{A_padded}\n")
            print(f"B_padded ({B_padded.shape}): \n{B_padded}\n")
        print(f"X_padded ({X_padded.shape}): \n{X_padded}\n")

        print("\n\nSPLITTED MATRICES:")
        if (doGemm):
            print(f"A_blocks (blocks_col = {A_blocks_col})")
            for i, block in enumerate(A_blocks):
                print("\n A", i)
                print(block)
            print(f"\n\nB_blocks (blocks_col = {B_blocks_col})")
            for i, block in enumerate(B_blocks):
                print("\n B", i)
                print(block)
            print("\n\nTransposed B_blocks:")
            for i, block in enumerate(B_blocks):
                print("\n Transposed B", i)
                print(block.transpose())
        print(f"\n\nX_blocks (blocks_col = {X_blocks_col})")
        for i, block in enumerate(X_blocks):
            print("\n X", i)
            print(block)
        
        if (doAddMatrix):
            print(f"\n\nY_blocks (blocks_col = {X_blocks_col})")
            for i, block in enumerate(Y_blocks):
                print("\n X", i)
                print(block)
        
        if (doGemm):
            print("\n\nACC=A*B+X RESULTING MATRICES:")
            print(f"ACC_ref ({ACC_ref.shape}): \n{ACC_ref}\n")
            print(f"ACC_padded_ref ({ACC_padded_ref.shape}): \n{ACC_padded_ref}\n")
            print(f"\n\nACC_blocks_ref (blocks_col = {ACC_blocks_col})")
            for i, block in enumerate(ACC_blocks_ref):
                print("\n ACC", i)
                print(block)
            print("\n\nACC=A*B+X by blocks COMBINATIONS:")
            for combination in combinations:
                print(combination)
    
        print("\n\nALU OPERATIONS:")
        for alu_ops in alu_operations_list:
            print(f" {alu_ops[0]}: {alu_ops[1]} -> within blocks: {alu_ops[2]}")
        print(f"\nALU_matrix ({ALU_matrix.shape}): \n{ALU_matrix}\n")
        print(f"ALU_blocks truncated (blocks_col = {C_blocks_col})")
        for i, block in enumerate(ALU_blocks):
            print("\n ALU (OUT)", i)
            print(block)

        print("\n\nOUTPUT MATRIX:")
        print(f"C_blocks (blocks_col = {C_blocks_col})")
        for i, block in enumerate(C_blocks):
            print(f"\n C {i} - {block.shape}")
            print(block)
        
        print(f"Tuples to store (if empty, everything is stored): \n {idx_to_store}\n")

    # ---------------------------------------------
    # RETURN 

    return A_blocks, A_blocks_col, B_blocks, B_blocks_col, X_blocks, X_blocks_col, Y_blocks, ALU_blocks, C_blocks, C_blocks_col, C_init, alu_operations_list, idx_to_store, doGemm, doAddMatrix

