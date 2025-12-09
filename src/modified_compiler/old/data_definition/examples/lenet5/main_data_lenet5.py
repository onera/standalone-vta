import os
import sys
import numpy as np

import reshape_numpy as reshape
#from lenet5_reference import QuantizedLeNet5

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
    print(f"\n{layer}: intermediate result (shape = {matrix.shape}, {res_col} blocks on width)")
    i = 0
    for block in res_to_print:
        print(f"\n {layer} block", i)
        print(block)
        i = i + 1


def main_data(isInputTensor=False, doExhaustivePrint=False, debug_reshape=False):
    if (isInputTensor):
        # CREATE THE TENSORS
        # ------------------
        # Input
        input_tensor = np.random.randint(0, 4, size=(1, 1, 32, 32), dtype=np.int8)
        # Weights
        L1_tensor = np.random.randint(0, 4, size=(6, 1, 5, 5), dtype=np.int8)
        L2_tensor = np.random.randint(0, 4, size=(16, 6, 5, 5), dtype=np.int8)
        L3_tensor = np.random.randint(0, 4, size=(120, 16, 5, 5), dtype=np.int8)
        L4_tensor = np.random.randint(0, 4, size=(84, 120, 1, 1), dtype=np.int8)
        L5_tensor = np.random.randint(0, 4, size=(10, 84, 1, 1), dtype=np.int8)

        # Print the tensors
        if (doExhaustivePrint):
            print(f"Input tensor ({input_tensor.shape}): \n{input_tensor} \n")
            print(f"Weight L1 tensor ({L1_tensor.shape}): \n{L1_tensor} \n")
            print(f"Weight L2 tensor ({L2_tensor.shape}): \n{L2_tensor} \n")
            print(f"Weight L3 tensor ({L3_tensor.shape}): \n{L3_tensor} \n")
            print(f"Weight L4 tensor ({L4_tensor.shape}): \n{L4_tensor} \n")
            print(f"Weight L5 tensor ({L5_tensor.shape}): \n{L5_tensor} \n\n")

        # Convert into matrix
        input_matrix = reshape.im2row(input_tensor, (5, 5), 1) # (X, kernel_size, stride)
        weight_L1 = reshape.ker2col(L1_tensor)
        weight_L2 = reshape.ker2col(L2_tensor)
        weight_L3 = reshape.ker2col(L3_tensor)
        weight_L4 = reshape.ker2col(L4_tensor)
        weight_L5 = reshape.ker2col(L5_tensor)

        # Print the resulting matrix
        if (doExhaustivePrint):
            print(f"Input im2row matrix ({input_matrix.shape}):")
            print_intermediate(input_matrix, isSquare=True, layer="IM2ROW")
            print(f"\nWeight L1 ker2col matrix ({weight_L1.shape}):")
            print_intermediate(weight_L1, isSquare=True, layer="L1 KER2COL")
            print(f"\nWeight L2 ker2col matrix ({weight_L2.shape}):")
            print_intermediate(weight_L2, isSquare=True, layer="L2 KER2COL")
            print(f"\nWeight L3 ker2col matrix ({weight_L3.shape}):")
            print_intermediate(weight_L3, isSquare=True, layer="L3 KER2COL")
            print(f"\nWeight L4 ker2col matrix ({weight_L4.shape}):")
            print_intermediate(weight_L4, isSquare=True, layer="L4 KER2COL")
            print(f"\nWeight L5 ker2col matrix ({weight_L5.shape}):")
            print_intermediate(weight_L5, isSquare=True, layer="L5 KER2COL")

    else:
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

    
    # COMPUTE REFERENCE COMPUTATION (matrix domain)
    # -----------------------------
    # Layer 1: 
    conv1, _ = MM.matrix_int8_multiplication(A=input_matrix, B=weight_L1, useClip=False, useReLU=True) # Take ACC result
    L1_ACC, _, _ = AP.reference_average_pooling(conv1, 2, 2)
    res1 = MM.truncate_to_int8(L1_ACC) # Truncate ACC to obtain OUT
    
    # Creating out_init_L1
    _, res1_init = MM.matrix_int8_multiplication(A=input_padded, B=L1_padded, useClip=False, useReLU=True)
    C_empty_L1 = MG.matrix_creation(n_row=res1_init.shape[0], n_col=res1_init.shape[1], isInitRandom=False, dtype=np.int8) # empty OUT

    # Creating expected_out_sram for L1
    L1_pooled, _, _ = AP.avg_pool_sram(conv1, 2, 2)
    L1_out_sram = MG.matrix_padding(L1_pooled, 16, False, True)
    L1_pooled_sram = MM.truncate_to_int8(L1_out_sram)
    C_blocks_sram, _ = MS.matrix_splitting(L1_pooled_sram, 16, False, True)
    
    # Reshape L1 -> L2
    res1_reshaped = reshape.mat_to_tensor(res1, 1, 6, 14, 14) # (res, batch_size, output_channels, output_height, output_width)
    res1_reshaped = reshape.im2row(res1_reshaped, (5, 5), 1) # (X, kernel_size, stride)  


    # Layer 2:
    conv2, _ = MM.matrix_int8_multiplication(A=res1_reshaped, B=weight_L2, useClip=False, useReLU=True) # Take ACC result
    L2_ACC, _, _ = AP.reference_average_pooling(conv2, 2, 2)
    res2 = MM.truncate_to_int8(L2_ACC) # Truncate ACC to obtain OUT
    
    # Creating out_init_L2
    res1_padded = MG.matrix_padding(matrix=res1_reshaped, block_size=16, isWeight=False, isSquare=True)
    _, res2_init = MM.matrix_int8_multiplication(A=res1_padded, B=L2_padded, useClip=False, useReLU=True)
    C_empty_L2 = MG.matrix_creation(n_row=res2_init.shape[0], n_col=res2_init.shape[1], isInitRandom=False, dtype=np.int8) # empty OUT
    
    # Creating expected_out_sram for L2
    L2_pooled, _, _ = AP.avg_pool_sram(conv2, 2, 2)
    L2_out_sram = MG.matrix_padding(L2_pooled, 16, False, True)
    L2_pooled_sram = MM.truncate_to_int8(L2_out_sram)
    C_blocks_sram_L2, _ = MS.matrix_splitting(L2_pooled_sram, 16, False, True)

    # Reshape L2 -> L3
    res2_reshaped = reshape.mat_to_tensor(res2, 1, 16, 5, 5) # (res, batch_size, output_channels, output_height, output_width)
    res2_reshaped = reshape.im2row(res2_reshaped, (5, 5), 1) # (X, kernel_size, stride)


    # Layer 3:
    conv3, res3 = MM.matrix_int8_multiplication(A=res2_reshaped, B=weight_L3, useClip=False, useReLU=True) 
    
    # Creating out_init_L3
    res3_init = MG.matrix_padding(res3, 16, False, False)
    C_empty_L3 = MG.matrix_creation(n_row=res3_init.shape[0], n_col=res3_init.shape[1], isInitRandom=False, dtype=np.int8) # empty OUT

    # Creating expected_out_sram for L2
    

    # Layer 4:
    L4_ACC, res4 = MM.matrix_int8_multiplication(A=res3, B=weight_L4, useClip=False, useReLU=True)
    
    # Creating out_init_L4
    res4_init = MG.matrix_padding(res4, 16, False, False)
    C_empty_L4 = MG.matrix_creation(n_row=res4_init.shape[0], n_col=res4_init.shape[1], isInitRandom=False, dtype=np.int8) # empty OUT
    

    # Layer 5:
    L5_ACC, res5 = MM.matrix_int8_multiplication(A=res4, B=weight_L5, useClip=False, useReLU=False)
    
    # Creating out_init_L5
    res5_init = MG.matrix_padding(res5, 16, False, False)
    C_empty_L5 = MG.matrix_creation(n_row=res5_init.shape[0], n_col=res5_init.shape[1], isInitRandom=False, dtype=np.int8) # empty OUT
    

    # Print the results
    if (doExhaustivePrint):
        print_intermediate(input_matrix, isSquare=True, layer="Input")

        print_intermediate(conv1, isSquare=True, layer="CONV 1")
        print_intermediate(L1_ACC, isSquare=True, layer="L1_ACC (pool)")
        print_intermediate(res1, isSquare=True, layer="LAYER 1 (int8 out)")
        print_intermediate(res1_reshaped, isSquare=True, layer="LAYER 1_reshaped")

        print_intermediate(conv2, isSquare=True, layer="CONV 2")
        print_intermediate(L2_ACC, isSquare=True, layer="L2_ACC (pool)")
        print_intermediate(res2, isSquare=True, layer="LAYER 2 (int8 out)")
        print_intermediate(res2_reshaped, isSquare=False, layer="LAYER 2_reshaped")

        print_intermediate(conv3, isSquare=False, layer="CONV 3")
        print_intermediate(res3, isSquare=False, layer="LAYER 3 (int8 out)")

        print_intermediate(L4_ACC, isSquare=False, layer="L4_ACC (dense)")
        print_intermediate(res4, isSquare=False, layer="LAYER 4 (int8 out)")

        print_intermediate(L5_ACC, isSquare=False, layer="L5_ACC (dense)")
        print_intermediate(res5, isSquare=False, layer="LAYER 5 (int8 out)")

    # Print final result
    print(f"\nFinal result: \n{res5} \n\n")

    
    # # COMPUTE REFERENCE COMPUTATION (tensor domain)
    # # -----------------------------
    # if (isInputTensor):
    #     print("TENSOR EXECUTION")
    #     # Initialise the model with the weights
    #     lenet5_model = QuantizedLeNet5(L1_tensor, L2_tensor, L3_tensor, L4_tensor, L5_tensor)

    #     # Disable gradients for all parameters (inference mode only)
    #     for param in lenet5_model.parameters():
    #         param.requires_grad = False
    #     # Set the model to evaluation mode
    #     lenet5_model.eval()

    #     # Initialise the input
    #     output_tensor, intermediate_outputs = lenet5_model(input_tensor)

    #     # Print the results
    #     if (doExhaustivePrint):
    #         for layer_name, output in intermediate_outputs.items():
    #             print(f"\n{layer_name} output shape: {output.shape}")
    #             print(f"{layer_name} output data type: {output.dtype}")
    #             print(f"{layer_name} output: \n{output}\n")
    #     # Print the final result
    #     print(f"Final output tensor: \n{output_tensor}\n\n")


    # WRITE BINARIES
    # --------------

    # Define the output repository
    output_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))))), 'compiler_output')
    # Check if the OUTPUT dir exist, else create it
    os.makedirs(output_dir, exist_ok=True)

    # Define the filename
    input_file = os.path.join(output_dir, 'input.bin')
    #intermediate_file = os.path.join(output_dir, 'intermediate.bin')
    L1_file = os.path.join(output_dir, 'weight_L1.bin')
    L2_file = os.path.join(output_dir, 'weight_L2.bin')
    L3_file = os.path.join(output_dir, 'weight_L3.bin')
    L4_file = os.path.join(output_dir, 'weight_L4.bin')
    L5_file = os.path.join(output_dir, 'weight_L5.bin')
    
    out_init_L1_file = os.path.join(output_dir, 'out_init_L1.bin')
    out_init_L2_file = os.path.join(output_dir, 'out_init_L2.bin')
    out_init_L3_file = os.path.join(output_dir, 'out_init_L3.bin')
    out_init_L4_file = os.path.join(output_dir, 'out_init_L4.bin')
    out_init_L5_file = os.path.join(output_dir, 'out_init_L5.bin')
    
    
    # > TEMPO FILES FOR UNITTESTS
    if (debug_reshape):
        outL1_file = os.path.join(output_dir, 'outL1.bin')
        outL1_sram = os.path.join(output_dir, 'outL1_sram.bin')
        inpL2_file = os.path.join(output_dir, 'inpL2.bin')
        outL2_file = os.path.join(output_dir, 'outL2.bin')
        outL2_sram = os.path.join(output_dir, 'outL2_sram.bin')
        inpL3_file = os.path.join(output_dir, 'inpL3.bin')
        
        outL3_file = os.path.join(output_dir, 'outL3.bin')
        outL4_file = os.path.join(output_dir, 'outL4.bin')
        outL5_file = os.path.join(output_dir, 'outL5.bin')
    # <<<

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
            
    # Write the empty OUT files
    C_empty_L1.tofile(out_init_L1_file)
    C_empty_L2.tofile(out_init_L2_file)
    C_empty_L3.tofile(out_init_L3_file)
    C_empty_L4.tofile(out_init_L4_file)
    C_empty_L5.tofile(out_init_L5_file)

    
    # > TEMPO FILES FOR UNITTESTS
    if (debug_reshape):
        # Pad
        outL1 = MG.matrix_padding(matrix=res1, block_size=16, isWeight=False, isSquare=True)
        inpL2 = MG.matrix_padding(matrix=res1_reshaped, block_size=16, isWeight=False, isSquare=True)
        outL2 = MG.matrix_padding(matrix=res2, block_size=16, isWeight=False, isSquare=True)
        inpL3 = MG.matrix_padding(matrix=res2_reshaped, block_size=16, isWeight=False, isSquare=False)
        # Split
        outL1_blocks, _ = MS.matrix_splitting(matrix=outL1, block_size=16, isWeight=False, isSquare=True)
        inpL2_blocks, _ = MS.matrix_splitting(matrix=inpL2, block_size=16, isWeight=False, isSquare=True)
        outL2_blocks, _ = MS.matrix_splitting(matrix=outL2, block_size=16, isWeight=False, isSquare=True)
        inpL3_blocks, _ = MS.matrix_splitting(matrix=inpL3, block_size=16, isWeight=False, isSquare=False)
        
        outL3_blocks, _ = MS.matrix_splitting(matrix=res3_init, block_size=16, isWeight=False, isSquare=False)
        outL4_blocks, _ = MS.matrix_splitting(matrix=res4_init, block_size=16, isWeight=False, isSquare=False)
        outL5_blocks, _ = MS.matrix_splitting(matrix=res5_init, block_size=16, isWeight=False, isSquare=False)

        with open(outL1_file, 'wb') as f:
            for block in outL1_blocks:
                block.tofile(f)
        with open(outL1_sram, 'wb') as f:
            for block in C_blocks_sram:
                block.tofile(f)
        with open(inpL2_file, 'wb') as f:
            for block in inpL2_blocks:
                block.tofile(f)
        with open(outL2_file, 'wb') as f:
            for block in outL2_blocks:
                block.tofile(f)
        with open(outL2_sram, 'wb') as f:
            for block in C_blocks_sram_L2:
                block.tofile(f)
        with open(inpL3_file, 'wb') as f:
            for block in inpL3_blocks:
                block.tofile(f)
                
        with open(outL3_file, 'wb') as f:
            for block in outL3_blocks:
                block.tofile(f)
        with open(outL4_file, 'wb') as f:
            for block in outL4_blocks:
                block.tofile(f)
        with open(outL5_file, 'wb') as f:
            for block in outL5_blocks:
                block.tofile(f)
    # <<<

    

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
    main_data(isInputTensor=True, doExhaustivePrint=True, debug_reshape=True)
    