# IMPORT PACKAGES
# ---------------
import os
import sys

import onnx
from onnx import helper, TensorProto, numpy_helper
import onnxruntime as ort
import numpy as np

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils.find_project_root import *
from utils.read_csv import *

# Import the custom numpy implementation
from utils.numpy_implementation import *


###############################################


# MAIN FUNCTION
# -------------
def reference_onnx(model_path, mode="ort", debug=False):
    # READ DEPENDENCY FILE (metadata)
    # ---
    output_dir = compiler_output_setup()
    file_dep_path = filepath_definition(output_dir, 'dependency.csv')
    dep_dict = load_csv_to_dict(file_dep_path)

    # The first layer
    first_layer_name = dep_dict['0'][2]

    # The input tensor attributes
    attributes = dep_dict[first_layer_name]
    shape = [1, int( attributes[11] ), int( attributes[12] ), int( attributes[13] ) ]
    offset = int( attributes[3] )
    kernel = ( int(attributes[14]), int(attributes[15]) )
    stride = ( int(attributes[16]), int(attributes[17]) )
    padding = ( int(attributes[18]), int(attributes[19]), int(attributes[20]), int(attributes[21]) )

    # GENERATE INPUT DATA
    # ---
    # Data type
    dtype = np.int8

    # Generate Random Integer Input ([-128,0[)
    low_bound = -128
    high_bound = 127 # Exclusive
    
    # Create random tensor matching the input shape from CSV
    input_data = np.random.randint(low_bound, high_bound, size=shape).astype(dtype)
    
    # Initialize output container
    output_data = None


    # INFERENCE EXECUTION BASED ON MODE
    # ---
    print(f"Running inference in mode: {mode}")

    if mode == "numpy":
        # 1. NUMPY IMPLEMENTATION
        # -----------------------
        numpy_engine = NumPyReferenceEngine(model_path)
        
        # Get the input name from the graph structure
        # (Assuming single input for this specific implementation)
        real_input_name = numpy_engine.graph.input[0].name
        
        # Run inference
        output_data = numpy_engine.run(real_input_name, input_data)

    elif mode == "ort" or mode == "compare":
        # 2. ONNX RUNTIME (ORT)
        # ---------------------
        # Create Inference Session
        session = ort.InferenceSession(model_path)
        
        # Get Input Metadata generically
        input_name = session.get_inputs()[0].name
        input_shape = session.get_inputs()[0].shape
        input_type = session.get_inputs()[0].type
        output_nodes = session.get_outputs()

        # Check the shape consistency between CSV and ONNX
        if (input_shape != shape):
            raise Exception(f"\nERROR: We get shape={shape} when the expected is {input_shape}! \n\n")

        # INFERENCE
        outputs = session.run(None, {input_name: input_data})
        
        # Get the first output
        output_data = outputs[0]

        # 3. COMPARE MODE
        # ---------------
        if mode == "compare":
            # Compare ORT result (output_data) with NumPy implementation
            # This function prints the differences to the console
            compare_numpy_vs_ort(model_path, input_data, output_data)

    else:
        raise ValueError(f"Unknown mode: {mode}. Expected 'ort', 'numpy', or 'compare'.")


    # MANAGE DATA (simulation input and reference)
    # ---
    # Flatten the input
    matrix = flatten_conv_output(input_data.astype(dtype))
    matrix = matrix.astype(dtype)

    # Flatten the output
    flat_out = flatten_conv_output(output_data)


    # WRITE BINARIES
    # ---
    # Set the paths
    file_inp_path = filepath_definition(output_dir, 'input_nn.bin')
    file_ref_path = filepath_definition(output_dir, 'reference.bin')


    # Write the result
    with open(file_inp_path, 'wb') as f:
        matrix.tofile(f)
    with open(file_ref_path, 'wb') as f:
        output_data.tofile(f) 


    # DEBUG
    # ---
    if (debug):
        # Configure numpy to print EVERYTHING (no truncation)
        np.set_printoptions(threshold=sys.maxsize, linewidth=200)
        
        if mode != "numpy":
             print(f"Input Name: {input_name}")
             print(f"Input Shape: {input_shape}")
             print(f"Input Type: {input_type}")

        print(f"\nFirst layer: {first_layer_name}")
        print(f"\t offset={offset}, kernel={kernel}, stride={stride}, padding={padding} \n")
        
        if mode != "numpy":
            print(f"\n{len(output_nodes)} outputs found:")
            for i, output_node in enumerate(output_nodes):
                print(f"\nOutput #{i} :")
                print(f"\t Name  : {output_node.name}")
                print(f"\t Shape : {output_node.shape}")
                print(f"\t Type  : {output_node.type}")
                print(f"\t Data  : \n{outputs[i]}")

        print("\n\n" + "-"*50)
        print("\nInput:")
        print(input_data)
        print(f"\n\t | \n\t | \n\t V \n {mode.upper()} inference \n\t | \n\t | \n\t V")
        print("\nOutput:")
        print(output_data)

        print("\n\n" + "-"*50)
        print("\n\nMATRICES:")
        print("\nInput:")
        print(matrix)
        print("\n\t | \n\t | \n\t V")
        print("\nOutput:")
        print(flat_out)

        # Reset print options
        np.set_printoptions(threshold=1000)


###############################################

# IM2ROW
# ------
def im2row(X, dtype=np.int8, kernel_size=(1,1), stride=(1,1), padding=(0,0,0,0)):
    """
    Converts an input tensor X into a matrix (im2row).
    
    Arguments:
    X -- Input tensor of shape (batch_size, input_channels, input_height, input_width)
    kernel_size -- Filter size (height, width)
    stride -- Convolution stride (height, width)
    padding -- Padding (top, left, bottom, right)
    
    Returns:
    A matrix of shape (batch_size, output_height * output_width * input_channels, kernel_height * kernel_width)
    """
    # Get the attributes
    kernel_height, kernel_width = kernel_size
    stride_height, stride_width = stride
    pad_top, pad_left, pad_bottom, pad_right = padding

    # Apply a zero-padding
    X_padded = np.pad(X, (
        (0, 0),                     # Batch
        (0, 0),                     # Channels
        (pad_top, pad_bottom),      # Hauteur
        (pad_left, pad_right)       # Largeur
    ), mode='constant', constant_values=0)

    # Get the padded tensor dimension
    batch_size, input_channels, input_height, input_width = X_padded.shape

    
    # Calculate the output dimensions
    output_height = (input_height - kernel_height) // stride_height + 1
    output_width = (input_width - kernel_width) // stride_width + 1
    
    # Initial output matrix
    rows = batch_size * output_height * output_width
    cols = input_channels * kernel_height * kernel_width
    result = np.zeros((rows, cols), dtype=dtype)
    
    # Fill the matrix with patches
    row_idx = 0
    for b in range(batch_size):
        for i in range(0, input_height - kernel_height + 1, stride_height):
            for j in range(0, input_width - kernel_width + 1, stride_width):
                # Extract the patch
                patch = X_padded[b, :, i:i+kernel_height, j:j+kernel_width]
                result[row_idx] = patch.flatten()
                row_idx += 1
                
    return result

# FLATTEN
# -------
def flatten_conv_output(Y):
    """
    Flattens the output of a standard convolution to match the result of 
    an im2row GEMM operation.
    
    Arguments:
    Y -- Output tensor of shape (batch_size, output_channels, output_height, output_width)
    
    Returns:
    A matrix of shape (batch_size * output_height * output_width, output_channels)
    """
    # 1. Permute dimensions to (batch_size, output_height, output_width, output_channels)
    # We move the channel dimension (axis 1) to the last position.
    Y_permuted = Y.transpose(0, 2, 3, 1)
    
    # 2. Reshape to combine batch and spatial dimensions into rows
    # The -1 infers the row dimension size automatically based on the input size
    output_channels = Y.shape[1]
    result = Y_permuted.reshape(-1, output_channels)
    
    return result

###############################################
###############################################

if __name__ == "__main__":
    """
    To execute: 
        > python reference_onnx.py 
            <debug>
            <mode>
            <onnx_model_path>
            
    Modes available: "ort", "numpy", "compare"
    """
    # Check there are 4 inputs
    if (len(sys.argv) != 4):
        raise Exception(f"\nERROR: Require 4 inputs and there are {len(sys.argv)}! \n")

    
    # Define path and debug
    debug = True if (sys.argv[1] == 'true' or sys.argv[1] == 'True') else False
    mode = sys.argv[2]
    onnx_model_path = sys.argv[3]
    
    # Run the generic inference code
    reference_onnx(onnx_model_path, mode, debug)