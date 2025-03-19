import os
import sys
import numpy as np

import reshape

current_dir = os.path.dirname(os.path.abspath(__file__))
source_dir = os.path.join(current_dir, '../../')
sys.path.insert(0, source_dir)

import matrix_generator as MG
import memory_addresses as MA
import matrix_split as MS
import matrix_multiplication as MM
import average_pooling as AP

def print_intermediate(matrix, isSquare=True, layer="1"):
    res_to_print = MG.matrix_padding(matrix=matrix, block_size=16, isWeight=False, isSquare=isSquare)
    res_to_print, res_col = MS.matrix_splitting(matrix=res_to_print, block_size=16, isWeight=False, isSquare=isSquare)
    print(f"\n{layer}: intermediate result ({res_col} blocks on width)")
    i = 0
    for block in res_to_print:
        print(f"\n {layer} block", i)
        print(block)
        i = i + 1


def main_data():
    # CREATE THE MATRICES
    # -------------------

    # Layer 1
    input_matrix = MG.matrix_creation(n_row=784, n_col=25, isInitRandom=True, random_bound=4, dtype=np.int8, onlyPositive=True) # Must be positive
    weight_L1 = MG.matrix_creation(n_row=25, n_col=6, isInitRandom=True, random_bound=4, dtype=np.int8, onlyPositive=True) # Must be positive

    # Layer 2
    weight_L2 = MG.matrix_creation(n_row=150, n_col=16, isInitRandom=True, random_bound=4, dtype=np.int8, onlyPositive=True) # Must be positive

    # Layer 3
    weight_L3 = MG.matrix_creation(n_row=400, n_col=120, isInitRandom=True, random_bound=4, dtype=np.int8, onlyPositive=True)

    # Layer 4
    weight_L4 = MG.matrix_creation(n_row=120, n_col=84, isInitRandom=True, random_bound=4, dtype=np.int8, onlyPositive=True)

    # Layer 5
    weight_L5 = MG.matrix_creation(n_row=84, n_col=10, isInitRandom=True, random_bound=4, dtype=np.int8, onlyPositive=True)


    # PAD THE MATRICES
    # ----------------

    input_padded = MG.matrix_padding(matrix=input_matrix, block_size=16, isWeight=False, isSquare=True)

    L1_padded = MG.matrix_padding(matrix=weight_L1, block_size=16, isWeight=True, isSquare=True)
    L2_padded = MG.matrix_padding(matrix=weight_L2, block_size=16, isWeight=True, isSquare=True)
    L3_padded = MG.matrix_padding(matrix=weight_L3, block_size=16, isWeight=True, isSquare=True)
    L4_padded = MG.matrix_padding(matrix=weight_L4, block_size=16, isWeight=True, isSquare=True)
    L5_padded = MG.matrix_padding(matrix=weight_L5, block_size=16, isWeight=True, isSquare=True)


    # SPLIT THE MATRICES
    # ------------------

    input_blocks, input_blocks_col = MS.matrix_splitting(matrix=input_padded, block_size=16, isWeight=False, isSquare=True)

    L1_blocks, L1_blocks_col = MS.matrix_splitting(matrix=L1_padded, block_size=16, isWeight=True, isSquare=True)
    L2_blocks, L2_blocks_col = MS.matrix_splitting(matrix=L2_padded, block_size=16, isWeight=True, isSquare=True)
    L3_blocks, L3_blocks_col = MS.matrix_splitting(matrix=L3_padded, block_size=16, isWeight=True, isSquare=True)
    L4_blocks, L4_blocks_col = MS.matrix_splitting(matrix=L4_padded, block_size=16, isWeight=True, isSquare=True)
    L5_blocks, L5_blocks_col = MS.matrix_splitting(matrix=L5_padded, block_size=16, isWeight=True, isSquare=True)


    # WRITE BINARIES
    # --------------

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
    with open(input_file, 'wb') as f:
        for block in input_blocks:
            block.tofile(f)
    with open(L1_file, 'wb') as f:
        for block in L1_blocks:
            transposed = block.transpose()
            transposed.tofile(f)
    with open(L2_file, 'wb') as f:
        for block in L2_blocks:
            transposed = block.transpose()
            transposed.tofile(f)
    with open(L3_file, 'wb') as f:
        for block in L3_blocks:
            transposed = block.transpose()
            transposed.tofile(f)
    with open(L4_file, 'wb') as f:
        for block in L4_blocks:
            transposed = block.transpose()
            transposed.tofile(f)
    with open(L5_file, 'wb') as f:
        for block in L5_blocks:
            transposed = block.transpose()
            transposed.tofile(f)

    
    # COMPUTE REFERENCE COMPUTATION 
    # -----------------------------
    # Input: 
    print_intermediate(input_matrix, isSquare=True, layer="Input")

    # Layer 1: 
    res1, _ = MM.matrix_int8_multiplication(A=input_matrix, B=weight_L1, useClip=False, useReLU=True) # Take ACC result
    res1, _, _ = AP.reference_average_pooling(res1, 2, 2)
    res1 = MM.truncate_to_int8(res1) # Truncate ACC to obtain OUT
    # Print intermediate result
    print_intermediate(res1, isSquare=True, layer="LAYER 1")

    # Reshape L1 -> L2
    res1 = reshape.mat_to_tensor(res1, 1, 6, 14, 14) # (res, batch_size, output_channels, output_height, output_width)
    res1 = reshape.im2row(res1, (5, 5), 1) # (X, kernel_size, stride)
    # Print reshaped result
    print_intermediate(res1, isSquare=True, layer="LAYER 1_reshaped")

    # Layer 2:
    res2, _ = MM.matrix_int8_multiplication(A=res1, B=weight_L2, useClip=False, useReLU=True) # Take ACC result
    res2, _, _ = AP.reference_average_pooling(res2, 2, 2)
    res2 = MM.truncate_to_int8(res2) # Truncate ACC to obtain OUT
    # Print intermediate result
    print_intermediate(res2, isSquare=True, layer="LAYER 2")

    # Reshape L2 -> L3
    res2 = reshape.mat_to_tensor(res2, 1, 16, 5, 5) # (res, batch_size, output_channels, output_height, output_width)
    res2 = reshape.im2row(res2, (5, 5), 1) # (X, kernel_size, stride)
    # Print reshaped result
    print_intermediate(res2, isSquare=False, layer="LAYER 2_reshaped")

    # Layer 3:
    _, res3 = MM.matrix_int8_multiplication(A=res2, B=weight_L3, useClip=False, useReLU=True)
    # Print intermediate result
    print_intermediate(res3, isSquare=False, layer="LAYER 3")

    # Layer 4:
    _, res4 = MM.matrix_int8_multiplication(A=res3, B=weight_L4, useClip=False, useReLU=True)
    # Print intermediate result
    print_intermediate(res4, isSquare=False, layer="LAYER 4")

    # Layer 5:
    _, res5 = MM.matrix_int8_multiplication(A=res4, B=weight_L5, useClip=False, useReLU=False)
    # Print intermediate result
    print_intermediate(res5, isSquare=False, layer="LAYER 5")

    # Print final result
    print(f"\n\nLAYER 5: final result: \n{res5} \n\n")
    

    # RETURN MEMORY ADDRESSES
    # -----------------------
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

    # END
    return 0


if __name__ == '__main__':
    main_data()
    