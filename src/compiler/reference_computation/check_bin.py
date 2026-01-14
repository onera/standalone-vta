# IMPORT PACKAGES
# ---------------
import os
import sys

import numpy as np

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils.find_project_root import *
from utils.read_csv import *


###############################################


# MAIN FUNCTION
# -------------
def check_bin(dtype=np.int8, 
              debug=False):
    # Read dependency.csv to have high level information
    output_dir = compiler_output_setup()
    file_dep_path = filepath_definition(output_dir, 'dependency.csv')

    # Get information
    dep_dict = load_csv_to_dict(file_dep_path)
    output_layer = dep_dict['output']
    output_name = output_layer[1]

    # Standard NCHW shape
    shape = [1, int(output_layer[2]), int(output_layer[3]), int(output_layer[4])]
    batch_size, channels, height, width = shape


    # ---
    # Read the binaries
    file_ref_path = filepath_definition(output_dir, 'reference.bin')
    file_out_path = filepath_definition(output_dir, 'final_output.bin')

    try:
        ref_raw = np.fromfile(file_ref_path, dtype=dtype)
    except FileNotFoundError:
        raise Exception(f"ERROR: Could not find {file_ref_path}")
        return

    try:
        final_output_raw = np.fromfile(file_out_path, dtype=dtype)
    except FileNotFoundError:
        raise Exception(f"ERROR: Could not find {file_out_path}")
        return


    # ---
    # Transform the binary in tensors
    total_elements = batch_size * channels * height * width
    
    # Sanity check on file size vs shape
    if ref_raw.size != total_elements:
        raise Exception(f"ERROR: Reference size {ref_raw.size} does not match shape {shape} (Total: {total_elements})")
        return

    # Define shape
    tensor_ref = ref_raw.reshape(batch_size, channels, height, width)
    tensor_output = final_output_raw.reshape(batch_size, channels, height, width)


    # ---
    # Compare the tensor
    # Ensure calculation is done in higher precision to avoid overflow during diff
    diff = tensor_ref.astype(np.float32) - tensor_output.astype(np.float32)

    isCorrect = True
    if np.issubdtype(dtype, np.integer):
        isCorrect = np.array_equal(tensor_ref, tensor_output)
    else:
        isCorrect = np.allclose(tensor_ref, tensor_output, rtol=1e-05, atol=1e-08)


    # Compare element and register the position of the discrepancy
    mismatches = []
    num_mismatches = 0
    
    if not isCorrect:
        # --- UPDATED: Handle 4 dimensions indices ---
        # np.where returns a tuple of arrays, one for each dimension
        b_idxs, c_idxs, h_idxs, w_idxs = np.where(diff != 0)
        num_mismatches = len(b_idxs)
        
        # Store first 10 errors for display
        for i in range(min(10, num_mismatches)):
            b = b_idxs[i]
            c = c_idxs[i]
            h = h_idxs[i]
            w = w_idxs[i]
            
            val_ref = tensor_ref[b, c, h, w]
            val_out = tensor_output[b, c, h, w]
            val_diff = diff[b, c, h, w]
            
            mismatches.append(
                f"Batch {b}, Ch {c}, H {h}, W {w} | Ref: {val_ref} vs Out: {val_out} (Diff: {val_diff})"
            )
    
        # Calculate Statistics
        percentage = (num_mismatches / total_elements) * 100
        max_diff = np.max(diff)
        min_diff = np.min(diff)
        max_abs_diff = np.max(np.abs(diff))


    # ---
    # Debug
    if (debug==True or isCorrect==False):
        # Configure numpy to print EVERYTHING (no truncation)
        np.set_printoptions(threshold=sys.maxsize, linewidth=200)

        print(f"Is the result correct? {isCorrect}\n")

        # Print the mismatches
        if not isCorrect:
            print(f"\nFound {num_mismatches} mismatches out of {total_elements} elements ({percentage:.3f}%)!")
            print(f"Statistics: max={max_diff}, min={min_diff}, abs_error={max_abs_diff}")
            print(f"-"*30)
            print(f"First 10 Mismatches:")
            for m in mismatches:
                print(f"\t{m}")

            # Print the difference
            print(f"\n\nDIFFERENCE Matrix:")
            print(diff)
        
        # Print the matrix
        print(f"\n\nREFERENCE (Shape: {tensor_ref.shape}):")
        print(tensor_ref)

        print(f"\n\nRESULT (Shape: {tensor_output.shape}):")
        print(tensor_output)

        # Reset print options
        np.set_printoptions(threshold=1000)

    # If there is a difference print an error message
    if (not isCorrect):
        if (max_abs_diff < 5 and percentage < 5.):
            raise Exception(f"\n\nWarning: There are approximation errors (up to {max_abs_diff} over {percentage:.3f}% of the data)! \n")

        else:
            raise Exception(f"\n\nERROR: The final result does not match the reference!\n\t (up to {max_abs_diff} over {percentage:.3f}% of the data) \n")


###############################################
###############################################

if __name__ == "__main__":
    """
    To execute: 
        > python check_bin.py 
            <debug>
    """
    # Check there are 2 inputs
    if (len(sys.argv) != 2):
        raise Exception(f"\nERROR: Require 2 inputs and there are {len(sys.argv)}! \n")

    # Default dtype (Adjust if your binaries are float32)
    dtype = np.int8
    
    # Define debug
    debug = True if (sys.argv[1] == 'true' or sys.argv[1] == 'True') else False
    
    # Run the generic inference code
    check_bin(dtype=dtype, debug=debug)