import os
import sys
import numpy as np

current_dir = os.path.dirname(os.path.abspath(__file__))
source_dir = os.path.join(current_dir, '../../')
sys.path.insert(0, source_dir)

import matrix_generator as MG
import memory_addresses as MA


def main_data():
    # CREATE THE MATRICES

    # Layer 1
    input_matrix = MG.matrix_creation(n_row=784, n_col=25, isInitRandom=True, random_bound=4, dtype=np.int8)
    #intermediate_matrix = MG.matrix_creation(n_row=196, n_col=16, isInitRandom=True, random_bound=4, dtype=np.int8) # Not used
    weight_L1 = MG.matrix_creation(n_row=25, n_col=6, isInitRandom=True, random_bound=4, dtype=np.int8)

    # Layer 2
    weight_L2 = MG.matrix_creation(n_row=150, n_col=16, isInitRandom=True, random_bound=4, dtype=np.int8)

    # Layer 3
    weight_L3 = MG.matrix_creation(n_row=400, n_col=120, isInitRandom=True, random_bound=4, dtype=np.int8)

    # Layer 4
    weight_L4 = MG.matrix_creation(n_row=120, n_col=84, isInitRandom=True, random_bound=4, dtype=np.int8)

    # Layer 5
    weight_L5 = MG.matrix_creation(n_row=84, n_col=10, isInitRandom=True, random_bound=4, dtype=np.int8)
    #output_matrix = MG.matrix_creation(n_row=1, n_col=10, isInitRandom=False, random_bound=0, dtype=np.int8) # Not used


    # PAD THE MATRICES

    input_padded = MG.matrix_padding(matrix=input_matrix, block_size=16, isWeight=False, isSquare=True)
    #intermediate_padded = MG.matrix_padding(matrix=intermediate_matrix, block_size=16, isWeight=False, isSquare=True) # Not used

    L1_padded = MG.matrix_padding(matrix=weight_L1, block_size=16, isWeight=True, isSquare=True)
    L2_padded = MG.matrix_padding(matrix=weight_L2, block_size=16, isWeight=True, isSquare=True)
    L3_padded = MG.matrix_padding(matrix=weight_L3, block_size=16, isWeight=True, isSquare=True)
    L4_padded = MG.matrix_padding(matrix=weight_L4, block_size=16, isWeight=True, isSquare=True)
    L5_padded = MG.matrix_padding(matrix=weight_L5, block_size=16, isWeight=True, isSquare=True)

    #output_padded = MG.matrix_padding(matrix=output_matrix, block_size=16, isWeight=False, isSquare=False) # not used


    # WRITE BINARIES

    # Define the output repository
    output_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))), 'compiler_output')
    # Check if the OUTPUT dir exist, else create it
    os.makedirs(output_dir, exist_ok=True)
    print(output_dir)

    # Define the filename
    input_file = os.path.join(output_dir, 'input.bin')
    #intermediate_file = os.path.join(output_dir, 'intermediate.bin')
    L1_file = os.path.join(output_dir, 'weight_L1.bin')
    L2_file = os.path.join(output_dir, 'weight_L2.bin')
    L3_file = os.path.join(output_dir, 'weight_L3.bin')
    L4_file = os.path.join(output_dir, 'weight_L4.bin')
    L5_file = os.path.join(output_dir, 'weight_L5.bin')

    # Write 
    input_padded.tofile(input_file)
    L1_padded.tofile(L1_file)
    L2_padded.tofile(L2_file)
    L3_padded.tofile(L3_file)
    L4_padded.tofile(L4_file)
    L5_padded.tofile(L5_file)

    # RETURN MEMORY ADDRESSES

    object_info = [
        (input_padded.size, 16), # Input
        (L1_padded.size, 256), # Weight
        (L2_padded.size, 256),
        (L3_padded.size, 256),
        (L4_padded.size, 256),
        (L5_padded.size, 256),
        (16, 16), # Output
        (32, 4), # UOP L1
        (32, 4), # UOP L2
        (32, 4), # UOP L3
        (32, 4), # UOP L4
        (32, 4), # UOP L5
        (208, 16) # INTERMEDIATE RESULT
    ]

    addresses = MA.memory_base_address(object_info)

    for add in addresses:
        print(add)


if __name__ == '__main__':
    main_data()
    