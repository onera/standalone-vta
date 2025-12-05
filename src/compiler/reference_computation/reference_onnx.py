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


###############################################


# MAIN FUNCTION
# -------------
def reference_onnx(model_path, debug=False):
    # Read dependency.csv to have high level information
    output_dir = compiler_output_setup()
    file_dep_path = filepath_definition(output_dir, 'dependency.csv')

    # Get information
    dep_dict = load_csv_to_dict(file_dep_path)
    # The first layer
    first_layer_name = dep_dict['0'][2]

    # Get attributes
    attributes = dep_dict[first_layer_name]
    shape = [1, int( attributes[1] ), int( attributes[2] ), int( attributes[3] ) ]
    offset = int( attributes[5] )
    kernel = ( int(attributes[6]), int(attributes[7]) )
    stride = ( int(attributes[8]), int(attributes[9]) )
    padding = ( int(attributes[10]), int(attributes[11]), int(attributes[12]), int(attributes[13]) )


    # ---
    # Create Inference Session
    session = ort.InferenceSession(model_path)
    
    # Get Input Metadata generically
    input_name = session.get_inputs()[0].name
    input_shape = session.get_inputs()[0].shape
    input_type = session.get_inputs()[0].type

    # Check the shape
    if (input_shape != shape):
        raise Exception(f"\nERROR: We get shape={shape} when the expected is {input_shape}! \n\n")

    # Generate Random Integer Input 
    low_bound = -128
    high_bound = 0 # Exclusive
    
    # Create random tensor matching the input shape
    input_data = np.random.randint(low_bound, high_bound, size=input_shape).astype(np.int8)


    # ---
    # Run Inference
    outputs = session.run(None, {input_name: input_data})
    
    # Get the first output
    output_data = outputs[0]


    # ---
    # Refactor the data for the FSIM
    input_with_offset = input_data - offset

    matrix = im2row(
        X=input_with_offset, 
        kernel_size=kernel, 
        stride=stride, 
        padding=padding
    )

    # ---
    # Binarise
    file_inp_path = filepath_definition(output_dir, 'input'+first_layer_name+'.bin')
    file_ref_path = filepath_definition(output_dir, 'reference.bin')

    # Write the result
    with open(file_inp_path, 'wb') as f:
        matrix.tofile(f)
    with open(file_ref_path, 'wb') as f:
        output_data.tofile(f)


    # ---
    #Debug
    if (debug):
        print(f"Input Name: {input_name}")
        print(f"Input Shape: {input_shape}")
        print(f"Input Type: {input_type}")

        print(f"\nFirst layer: {first_layer_name}")
        print(f"\t offset={offset}, kernel={kernel}, stride={stride}, padding={padding} \n")

        print("\nInput Data:")
        print(input_data)
        print("\nInput Data with offset:")
        print(input_with_offset)
        print("\nInput IM2ROW:")
        print(matrix)
        
        print("\nOutput Data:")
        print(output_data)


###############################################

# IM2ROW
# ------
def im2row(X, kernel_size=(1,1), stride=(1,1), padding=(0,0,0,0)):
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
    # Get the attributes
    kernel_height, kernel_width = kernel_size
    stride_height, stride_width = stride
    pad_top, pad_left, pad_bottom, pad_right = padding

    # Apply a zero-padding
    X_padded = np.pad(X, (
        (0, 0),                     # Batch
        (0, 0),                     # Channels
        (pad_top, pad_bottom),      # Hauteur
        (pad_left, pad_right)       # Largeur
    ), mode='constant', constant_values=0)

    # Get the padded tensor dimension
    batch_size, input_channels, input_height, input_width = X_padded.shape

    
    # Calculate the output dimensions
    output_height = (input_height - kernel_height) // stride_height + 1
    output_width = (input_width - kernel_width) // stride_width + 1
    
    # Initial output matrix
    rows = batch_size * output_height * output_width
    cols = input_channels * kernel_height * kernel_width
    result = np.zeros((rows, cols), dtype=np.int8)
    
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
            <onnx_model_path>
    """
    # Check there are 3 inputs
    if (len(sys.argv) != 3):
        raise Exception(f"\nERROR: Require 3 inputs and there are {len(sys.argv)}! \n")

    
    # Define path and debug
    debug = True if (sys.argv[1] == 'true' or sys.argv[1] == 'True') else False
    onnx_model_path = sys.argv[2]
    
    # Run the generic inference code
    reference_onnx(onnx_model_path, onnx_model_path)