import os
import sys
import numpy as np

import reshape_torch as reshape
from lenet5_reference import QuantizedLeNet5

# Find project root
def find_project_root(anchor='.git'):
    """
    Find the project root (i.e., where the '.git/' belongs).
    This function is used to write within a folder with absolute path, therefore avoiding issues when a script is moved.
    """
    path = os.path.abspath(__file__)
    current_dir = os.path.dirname(path)
    while True:
        if os.path.exists(os.path.join(current_dir, anchor)):
            if current_dir not in sys.path:
                sys.path.insert(0, current_dir)
            return current_dir
        parent_dir = os.path.dirname(current_dir)
        if parent_dir == current_dir:
            raise FileNotFoundError(f"Error: '{anchor}' not found.")
        current_dir = parent_dir


def main_data(output_dir="compiler_output/"):

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

    # Convert into matrix
    input_matrix = reshape.im2row(input_tensor, (5, 5), 1) # (X, kernel_size, stride)
    weight_L1 = reshape.ker2col(L1_tensor)
    weight_L2 = reshape.ker2col(L2_tensor)
    weight_L3 = reshape.ker2col(L3_tensor)
    weight_L4 = reshape.ker2col(L4_tensor)
    weight_L5 = reshape.ker2col(L5_tensor)

    
    # COMPUTE REFERENCE COMPUTATION 
    # -----------------------------
    # Initialise the model with the weights
    lenet5_model = QuantizedLeNet5(L1_tensor, L2_tensor, L3_tensor, L4_tensor, L5_tensor)

    # Disable gradients for all parameters (inference mode only)
    for param in lenet5_model.parameters():
        param.requires_grad = False
    # Set the model to evaluation mode
    lenet5_model.eval()

    # Initialise the input
    output_tensor, intermediate_outputs = lenet5_model(input_tensor)

    # GET THE OUTPUTS
    # ---------------
    # Final
    final_matrix = output_tensor.numpy()
    final_padded = MG.matrix_padding(matrix=final_matrix, block_size=16, isWeight=False, isSquare=True)
    final_blocks, _ = MS.matrix_splitting(matrix=final_padded, block_size=16, isWeight=False, isSquare=True)
    print(f"Final final_matrix: \n{final_matrix}\n\n")



    # WRITE BINARIES
    # --------------

    # Check if the OUTPUT dir exist, else create it
    os.makedirs(output_dir, exist_ok=True)

    # Define the filename
    input_file = os.path.join(output_dir, 'inp_L1.bin')
    # Intermediate_file = os.path.join(output_dir, 'intermediate.bin')
    L1_file = os.path.join(output_dir, 'wgt_L1.bin')
    L2_file = os.path.join(output_dir, 'wgt_L2.bin')
    L3_file = os.path.join(output_dir, 'wgt_L3.bin')
    L4_file = os.path.join(output_dir, 'wgt_L4.bin')
    L5_file = os.path.join(output_dir, 'wgt_L5.bin')
    # Final expected output
    final_output = os.path.join(output_dir, 'final.bin')
    

    # Hardware-agnostic matrices
    with open(input_file, 'wb') as f:
        input_matrix.tofile(f)
    with open(L1_file, 'wb') as f:
        weight_L1.tofile(f)
    with open(L2_file, 'wb') as f:
        weight_L2.tofile(f)
    with open(L3_file, 'wb') as f:
        weight_L3.tofile(f)
    with open(L4_file, 'wb') as f:
        weight_L4.tofile(f)
    with open(L5_file, 'wb') as f:
        weight_L5.tofile(f)
    with open(final_output, 'wb') as f:
        for block in final_blocks:
            block.tofile(f)


    # END
    return 0


if __name__ == '__main__':
    # Find project root
    current_dir = find_project_root()
    # Import the compiler
    import src.compiler.vta_compiler.data_definition.matrix_generator as MG
    import src.compiler.vta_compiler.data_definition.matrix_split as MS

    # Define the repository for the binaries
    output_dir = os.path.join(current_dir, 'compiler_output')
    main_data(output_dir)
    