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

    # Get the matrices
    matrices = operations_dict["MATRICES"][0]
    

    # INIT
    # ---
    # Matrix names
    input_name = ''
    weight_name = ''
    acc_name = ''
    acc_bis_name = ''

    # Flags (GeMM, Add 2 matrices, other ALU operations)
    doGemm = False
    doMulConstant = False
    doAcc = False

    doAddMatrix = False

    doAlu = False


    # GET THE OPERATIONS
    # ---
    # Check if there is a GEMM (and if it is a MUL with a constant)
    if "GEMM" in operations_dict:
        doGemm = True
        mul_constant = 0

        # Get the name of the matrix
        input_name = operations_dict['GEMM'][0]
        weight_name_value = operations_dict['GEMM'][1]

        # Check if the weight is a constant (int) or a matrix (str name)
        if isinstance(weight_name_value, str):
            weight_name = weight_name_value
            # Check if there is an accumulator
            if len(operations_dict['GEMM']) == 3:
                doAcc = True
                acc_name = operations_dict['GEMM'][2]
        else:
            doMulConstant = True
            mul_constant = weight_name_value

    # Check if there is ALU operations to perform
    alu_operations = []
    if "ALU" in operations_dict:
        # Get the operation and the number of operations
        alu_operations = operations_dict["ALU"]
        nb_alu = len(alu_operations)

        # Check if it is an ADD between two matrices
        if "ADD_ACC" in alu_operations[0]:
            doAddMatrix = True
            doAlu = False
            doAcc = True

            if nb_alu > 1:
                raise Exception(f"ERROR: there are {nb_alu} operations while only one can be performed ('ADD_ACC')!\n\n")
            if doGemm == True:
                raise Exception(f"ERROR: 'ADD_ACC' operations cannot follow GeMM operations!\n\n")
            
            # Get the operations and the name of the matrices
            acc_bis_ops = alu_operations[0]
            acc_name, acc_bis_name = acc_bis_ops[1]
        
        # Else, define the name of the ACC matrix
        else:
            doAlu = True
            if doGemm == False:
                doAcc = True
                acc_name = next( name for name in matrices.keys() if not name.endswith("_VALUES") )
    
    # If no operations, there is a problem
    if doGemm == False and doAlu == False and doAddMatrix == False:
        raise Exception(f"ERROR: No operations!\n\n")   


    # DEFINE THE MATRICES
    # ---
    if (doGemm == True):
        # Input matrix
        A_row, A_col = matrices[input_name]
        # Define the values of the elements within the matrices
        if not (input_name+"_VALUES") in matrices:
            A_matrix = MG.matrix_creation(n_row=A_row, n_col=A_col, isInitRandom=True, random_bound=random_bound, dtype=inp_dtype)
        else: # TODO: read the INPUT_VALUES
            pass 

        # Weight matrix
        if (doMulConstant == True):
            B_matrix = MG.matrix_diagonal(diag_value=mul_constant, block_size=block_size, dtype=wgt_dtype)
        else:
            B_row, B_col = matrices[weight_name]
            # Check dimension consistency
            if (A_col != B_row):
                raise Exception(f"ERROR: Matrices not consistent: A_col={A_col} != B_row={B_row}! \n\n")

            if not (weight_name+"_VALUES") in matrices:
                B_matrix = MG.matrix_creation(n_row=B_row, n_col=B_col, isInitRandom=True, random_bound=random_bound, dtype=wgt_dtype)
            else: # TODO: read the WEIGHT_VALUES
                pass
    else: # doGemm == False
        A_matrix = MG.matrix_creation(n_row=0, n_col=0, isInitRandom=False, random_bound=0, dtype=inp_dtype)
        B_matrix = MG.matrix_creation(n_row=0, n_col=0, isInitRandom=False, random_bound=0, dtype=wgt_dtype)
        
    # Accumulator matrix
    if (doAcc == True):
        X_row, X_col = matrices[acc_name]
        # Check dimension consistency
        if (doGemm == True and X_row != A_row):
            raise Exception(f"ERROR: Matrices not consistent: X_row={X_row} != A_row={A_row}! \n\n")
        if (doGemm == True and X_col != B_col):
            raise Exception(f"ERROR: Matrices not consistent: X_col={X_col} != B_col={B_col}! \n\n")

        if not (acc_name+"_VALUES") in matrices:
            X_matrix = MG.matrix_creation(n_row=X_row, n_col=X_col, isInitRandom=True, random_bound=random_bound, dtype=acc_dtype)
        else: # TODO: read the binary values
            pass
    else: # Else set X to 0
        if (doMulConstant == True):
            X_row, X_col = (A_row, A_col)
        else:
            X_row, X_col = (A_row, B_col)
        X_matrix = MG.matrix_creation(n_row=X_row, n_col=X_col, isInitRandom=False, random_bound=0, dtype=acc_dtype)

    # ACC_BIS matrix
    if (doAddMatrix):
        Y_row, Y_col = matrices[acc_bis_name]
        # Check dimension consistency
        if (Y_row != X_row):
            raise Exception(f"ERROR: Matrices not consistent: Y_row={Y_row} != X_row={X_row}! \n\n")
        if (Y_col != X_col):
            raise Exception(f"ERROR: Matrices not consistent: Y_col={Y_col} != X_col={X_col}! \n\n")

        if not (acc_bis_name+"_VALUES") in matrices:
            Y_matrix = MG.matrix_creation(n_row=Y_row, n_col=Y_col, isInitRandom=True, random_bound=random_bound, dtype=acc_dtype)
        else: # TODO: read the binary values
            pass
    else: # doAddMatrix == False
        Y_matrix = MG.matrix_creation(n_row=0, n_col=0, isInitRandom=False, random_bound=0, dtype=acc_dtype)

    # Output matrix (init to 0)
    C_row, C_col = (X_row, X_col)
    C_init = MG.matrix_creation(n_row=C_row, n_col=C_col, isInitRandom=False, random_bound=0, dtype=inp_dtype)



    # ---------------------------------------------
    # APPLY HARDWARE CONSTRAINTS
    #   => Padding: Pad the matrix to make n_row and n_col a multiple of block_size
    #   => Splitting: Split the matrix in submatrix of size (block_size, block_size)

    # Check if A is a vector or a matrix (i.e., A_row = 1)
    isSquare = True # TODO: For now, always square
    #isSquare = False if (operations_dict["MATRICES"][0]["INPUT"][0] == 1) else True

    # PADDING
    A_padded = MG.matrix_padding(matrix=A_matrix, block_size=block_size, isWeight=False, isSquare=isSquare)
    B_padded = MG.matrix_padding(matrix=B_matrix, block_size=block_size, isWeight=True, isSquare=isSquare)
    X_padded = MG.matrix_padding(matrix=X_matrix, block_size=block_size, isWeight=False, isSquare=isSquare)
    Y_padded = MG.matrix_padding(matrix=Y_matrix, block_size=block_size, isWeight=False, isSquare=isSquare)

    # SPLITTING
    A_blocks, A_blocks_col = MS.matrix_splitting(matrix=A_padded, block_size=block_size, isWeight=False, isSquare=isSquare)
    B_blocks, B_blocks_col = MS.matrix_splitting(matrix=B_padded, block_size=block_size, isWeight=True, isSquare=isSquare)
    X_blocks, X_blocks_col = MS.matrix_splitting(matrix=X_padded, block_size=block_size, isWeight=False, isSquare=isSquare)
    Y_blocks, _ = MS.matrix_splitting(matrix=Y_padded, block_size=block_size, isWeight=False, isSquare=isSquare)



    # ---------------------------------------------
    # PERFORM MATRIX MULTIPLICATION

    if (doGemm == True):
        # Perform the reference computation
        if (doMulConstant == True):
            #ACC_ref = MM.matrix_multiplication(A_matrix, B_matrix, X_matrix, acc_dtype=acc_dtype)
            ACC_padded_ref = MM.matrix_multiplication(A_padded, mul_constant, X_padded, acc_dtype=acc_dtype)
        else:
            #ACC_ref = MM.matrix_multiplication(A_matrix, B_matrix, X_matrix, acc_dtype=acc_dtype)
            ACC_padded_ref = MM.matrix_multiplication(A_padded, B_padded, X_padded, acc_dtype=acc_dtype)
        # Copy the ref to keep a trace of the GeMM execution
        ALU_matrix = ACC_padded_ref.copy()

        # Split to obtain a result similar to the VTA output
        ACC_blocks_ref, ACC_blocks_col = MS.matrix_splitting(matrix=ACC_padded_ref, block_size=block_size, isWeight=False, isSquare=isSquare)
        if (doMulConstant == False):
            _, combinations = MM.block_matrix_multiply(A_blocks, B_blocks, A_blocks_col, B_blocks_col, block_size=block_size)

    # ---------------------------------------------
    # PERFORM ALU OPERATIONS

    # Define the intermediate ALU_matrix
    elif (doAddMatrix == True):
        ALU_matrix = X_padded + Y_padded

    else: # doGemm == False and doAddMatrix == False
        ALU_matrix = X_padded

    
    # Perform other ALU operations
    idx_to_store = []
    if (doAlu == True and doAddMatrix == False):
        ALU_matrix, alu_operations, idx_to_store = ALU.alu_operations(matrix=ALU_matrix, alu_operations=alu_operations, block_size=block_size)



    # ---------------------------------------------
    # TRUNCATE AND CLEAN OUTPUT

    # Truncate ALU_matrix
    ALU_trunc = TR.truncate(ALU_matrix, inp_dtype)

    # Split ALU_trunc for expected result before store (final output buffer)
    ALU_blocks, _ = MS.matrix_splitting(matrix=ALU_trunc, block_size=block_size, isWeight=False, isSquare=isSquare)

    # Remove non-necessary row in ALU to get C
    padding = ALU_matrix.shape[0] - C_row
    C_blocks = ALU.delete_matrix_row(ALU_blocks, blocks_col=X_blocks_col, block_size=block_size, idx_to_store=idx_to_store, matrix_height=C_row, padding=padding)



    # ---------------------------------------------
    # DEBUG

    if (debug):
        print("\nINITIAL MATRICES:")
        print(f"A_matrix ({A_matrix.shape}): \n{A_matrix}\n")
        if (doMulConstant):
            print(f"B constant: \n{mul_constant}\n")
        else:
            print(f"B_matrix ({B_matrix.shape}): \n{B_matrix}\n")
        print(f"X_matrix ({X_matrix.shape}): \n{X_matrix}\n")
        print(f"Y_matrix ({Y_matrix.shape}): \n{Y_matrix}\n")


        print("\nPADDED MATRICES:")
        if (doGemm):
            print(f"A_padded ({A_padded.shape}): \n{A_padded}\n")
            print(f"B_padded ({B_padded.shape}): \n{B_padded}\n")
        print(f"X_padded ({X_padded.shape}): \n{X_padded}\n")
        if (doAddMatrix):
            print(f"Y_padded ({Y_padded.shape}): \n{Y_padded}\n")


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
                print("\n Y", i)
                print(block)
        
        if (doGemm):
            print("\n\nACC=A*B+X RESULTING MATRICES:")
            #print(f"ACC_ref ({ACC_ref.shape}): \n{ACC_ref}\n")
            print(f"ACC_padded_ref ({ACC_padded_ref.shape}): \n{ACC_padded_ref}\n")
            print(f"\n\nACC_blocks_ref (blocks_col = {ACC_blocks_col})")
            for i, block in enumerate(ACC_blocks_ref):
                print("\n ACC", i)
                print(block)

            if (doMulConstant == False):
                print("\n\nACC=A*B+X by blocks COMBINATIONS:")
                for combination in combinations:
                    print(combination)
    
        print("\n\nALU OPERATIONS:")
        if (doAddMatrix):
            print(f" {acc_bis_ops[0]}: {acc_bis_ops[1]}")
        elif (doAlu):
            for alu_ops in alu_operations:
                print(f" {alu_ops[0]}: {alu_ops[1]} -> within blocks: {alu_ops[2]}")
        
        if (doAddMatrix or doAlu):
            print(f"\nALU_matrix ({ALU_matrix.shape}): \n{ALU_matrix}\n")
            print(f"ALU_blocks truncated (blocks_col = {X_blocks_col})")
            for i, block in enumerate(ALU_blocks):
                print("\n ALU (OUT)", i)
                print(block)


        print("\n\nOUTPUT MATRIX:")
        print(f"C_blocks (blocks_col = {X_blocks_col})")
        for i, block in enumerate(C_blocks):
            print(f"\n C {i} - {block.shape}")
            print(block)
        
        print(f"Tuples to store (if empty, everything is stored): \n {idx_to_store}\n")

    # ---------------------------------------------
    # RETURN 

    # Gather the flag in a dictionnary
    flag_dict = {
        "doGemm": doGemm,
        "doMulConstant": doMulConstant,
        "doAcc": doAcc,
        "doAddMatrix": doAddMatrix,
        "doAlu": doAlu
    }

    return A_blocks, A_blocks_col, B_blocks, B_blocks_col, \
           X_blocks, Y_blocks, ALU_blocks, C_blocks, C_init, X_blocks_col, \
           alu_operations, idx_to_store, \
           flag_dict

