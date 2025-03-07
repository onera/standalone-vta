# IMPORT PACKAGES
# ---------------
import os
import sys
import importlib
import matrix_generator as MG
import matrix_multiplication as MM
import matrix_split as MS
import json_generator as JG
import numpy as np


# MAIN FUNCTION
# -------------
def main(config_file):
    """Function executing the matrix generator. 
       Pass the configuration file in parameter (e.g., `python main_matrix_generator.py user_configuration`)"""
    
    # Import dynamically the configuration file
    config = importlib.import_module(config_file)

    # Create the matrix A and B - int8
    A_matrix = MG.matrix_creation(n_row=config.A_row, n_col=config.A_col, isInitRandom=config.isInitRandom, random_bound=config.random_bound, dtype=np.int8)
    B_matrix = MG.matrix_creation(n_row=config.B_row, n_col=config.B_col, isInitRandom=config.isInitRandom, random_bound=config.random_bound, dtype=np.int8)

    # Create the matrix X (the ACCUMULATOR VALUES) - int32
    X_matrix = MG.matrix_creation(n_row=config.X_row, n_col=config.X_col, isInitRandom=config.isInitRandom, random_bound=config.random_bound, dtype=np.int32)

    # Pad the matrix to make n_row and n_col a multiple of block_size
    A_padded = MG.matrix_padding(matrix=A_matrix, block_size=config.block_size, isWeight=False, isSquare=config.isSquare)
    B_padded = MG.matrix_padding(matrix=B_matrix, block_size=config.block_size, isWeight=True, isSquare=config.isSquare)
    X_padded = MG.matrix_padding(matrix=X_matrix, block_size=config.block_size, isWeight=False, isSquare=config.isSquare)

    # EXPECTED RESULTS (ACC: int16, C: ACC casted into int8)
    if (config.doMultiplyNonPadded): # Compute non-padded matrices
        ACC_matrix, C_matrix = MM.matrix_int8_multiplication(A=A_matrix, B=B_matrix, useClip=config.useClip, useReLU=config.useReLU)

    ACC_padded, C_padded = MM.matrix_int8_multiplication(A=A_padded, B=B_padded, useClip=config.useClip, useReLU=config.useReLU)

    # Split matrix into blocks
    A_blocks, A_blocks_col = MS.matrix_splitting(matrix=A_padded, block_size=config.block_size, isWeight=False, isSquare=config.isSquare)
    B_blocks, B_blocks_col = MS.matrix_splitting(matrix=B_padded, block_size=config.block_size, isWeight=True, isSquare=config.isSquare)
    X_blocks, X_blocks_col = MS.matrix_splitting(matrix=X_padded, block_size=config.block_size, isWeight=False, isSquare=config.isSquare)

    ## Multiply the blocks
    ACC_by_blocks, combinations = MM.block_matrix_multiply(A_blocks, B_blocks, A_blocks_col, B_blocks_col, block_size=config.block_size)
    ACC_reconstructed = MM.reconstruct_matrix(ACC_by_blocks, (A_padded.shape[0], B_padded.shape[1]), block_size=config.block_size)


    # Split the results
    ACC_blocks, ACC_blocks_row = MS.matrix_splitting(matrix=ACC_padded, block_size=config.block_size, isWeight=False, isSquare=config.isSquare)
    C_blocks, C_blocks_row = MS.matrix_splitting(matrix=C_padded, block_size=config.block_size, isWeight=False, isSquare=config.isSquare)

    # Define the output repository
    output_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'compiler_output')
    # Check if the OUTPUT dir exist, else create it
    os.makedirs(output_dir, exist_ok=True)

    # Write binary files
    if (config.doWriteBinaryFile):
        # Define the complete path of the files
        A_blocks_file_path = os.path.join(output_dir, 'input.bin')
        B_blocks_file_path = os.path.join(output_dir, 'weight.bin')
        X_blocks_file_path = os.path.join(output_dir, 'accumulator.bin')
        C_padded_file_path = os.path.join(output_dir, 'expected_out.bin')

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
        
        # Write C_padded (expected result)
        C_padded.tofile(C_padded_file_path)

        # Confirm the binary files generation
        print("Binary files successfully generated.")
    
    # Write JSON files
    if (config.doWriteJSON):
        # Define the complete path of the files
        json_file_path = os.path.join(output_dir, 'generated_for_compute.json')

        # Call the JSON generation function
        JG.generate_json(A_blocks, B_blocks, X_blocks, C_blocks, json_file_path, block_size=config.block_size,)

    # Print the matrices
    if (config.doPrint):
        print("\n INITIAL MATRICES:")
        print(f"A_matrix: ((h, w) = {np.shape(A_matrix)}) \n", A_matrix)
        print(f"\n x \n B_matrix: ((h, w) = {np.shape(B_matrix)}) \n", B_matrix)
        if (config.doMultiplyNonPadded):
            print(f"\n = \n ACC_matrix: ((h, w) = {np.shape(ACC_matrix)}) \n", ACC_matrix)
            print("\n => cast into int8: \n C_matrix: \n", C_matrix)
        print(f"\n\n X_matrix: ((h, w) = {np.shape(X_matrix)}) \n", X_matrix)

        print("\n\n\n PADDED MATRICES:")
        print(f"A_padded: ((h, w) = {np.shape(A_padded)}) \n", A_padded)
        print(f"\n x \n B_padded: ((h, w) = {np.shape(B_padded)}) \n", B_padded)
        print(f"\n = \n ACC_padded: ((h, w) = {np.shape(ACC_padded)}) \n", ACC_padded)
        print("\n => cast into int8: \n C_padded: \n", C_padded)
        print(f"\n\n X_padded: ((h, w) = {np.shape(X_padded)}) \n", X_padded)

        print("\n\n\n SPLITTED MATRICES:")
        i = 0
        print(f"A_blocks: (blocks_col = {A_blocks_col})")
        for block in A_blocks:
            print("\n A", i)
            print(block)
            i = i + 1
        i = 0
        print(f"\n\n B_blocks: (blocks_col = {B_blocks_col})")
        for block in B_blocks:
            print("\n B", i)
            print(block)
            i = i + 1
        i = 0
        print("\n\n Transposed B_blocks:")
        for block in B_blocks:
            print("\n Transposed B", i)
            print(block.transpose())
            i = i + 1
        i = 0
        print("\n\n Resulting ACC_blocks:")
        for block in ACC_blocks:
            print("\n ACC", i)
            print(block)
            i = i + 1
        i = 0
        print(f"\n\n Resulting C_blocks: (blocks_col = {B_blocks_col})")
        for block in C_blocks:
            print("\n C", i)
            print(block)
            i = i + 1

        print("\n\nBlock computation combination:")
        for combination in combinations:
            print(combination)

        i = 0
        print(f"\n\n Resulting X_blocks: (blocks_col = {X_blocks_col})")
        for block in X_blocks:
            print("\n X", i)
            print(block)
            i = i + 1

        print("\n\n\n COMPARISON OF ACC_RECONSTRUCTED AND EXPECTED ACC_PADDED:")
        print("Does ACC_reconstructed == ACC_padded:", np.allclose(ACC_reconstructed, ACC_padded))

    # End of the execution
    return 0


# EXECUTE MAIN FUNCTION
# ---------------------
if __name__ == '__main__':
    # If there is no argument, take user_configuration
    if len(sys.argv) == 1:
        print("WARNING: No argument given, the execution takes user_configuration.py by default!\n\n")
        config_file = "user_configuration"
    # If there is more than one argument, through an error message
    elif len(sys.argv) != 2:
        print("Usage: python main_matrix_generator.py <config_file>")
        sys.exit(1)
    else: # Get the configuration file from the arguments
        config_file = sys.argv[1]
    
    # Execute the main function
    main(config_file)
