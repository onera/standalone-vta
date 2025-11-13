# IMPORT PACKAGES
# ---------------
import os
import sys
from pathlib import Path
import numpy as np

###############################################

# MAIN FUNCTION
# -------------
def data_formatting(binary_file, m_rows=16, n_columns=16, isInput=True,
                    dtype=np.int8, block_size=16, debug=True):
    
    # Create an array from binary
    flat_array = np.fromfile(binary_file, dtype=dtype)

    # Transform the array into matrix
    matrix = flat_array.reshape((m_rows, n_columns))
    
    # Pad the matrix
    matrix_padded = matrix_padding(matrix=matrix, block_size=block_size, isWeight=False, isSquare=True)

    # Split the matrix
    matrix_blocks, blocks_col = matrix_splitting(matrix=matrix_padded, block_size=block_size, isWeight=False, isSquare=True)

    # Generate binary
    p = Path(binary_file)
    # p.parent -> 'folder'
    # p.stem   -> 'file'   (file name)
    # p.suffix -> '.bin'   (extension)
    new_binary_file = p.parent / f"{p.stem}_formatted{p.suffix}"
    with open(new_binary_file, 'wb') as f:
        for block in matrix_blocks:
            block.tofile(f)

    # Print
    if (debug):
        print(f"Matrix {binary_file} ({m_rows}x{n_columns}): \n\t isInput? {isInput}\n")
        print(f"INITIAL MATRIX: \n{matrix} \n\n")

        print(f"PADDED MATRIX: \n{matrix_padded} \n\n")

        print(f"BLOCK MATRIX (blocks_col={blocks_col}):")
        for i, block in enumerate(matrix_blocks):
                print("\n Block ", i)
                print(block)


    # ---------------------------------------------
    # RETURN 
    return 0


###############################################

# OTHER FUNCTIONS
# ---------------
def matrix_padding(matrix, block_size=16, isWeight=False, isSquare=True):
    """Pad the matrix such that its shape is a multiple of block_size.
       If it is input, then only the number of column is padded."""
    # Get the matrix size
    n_row, n_col = matrix.shape

    # Define the target dimensions (block_size or upper multiple of block_size)
    if (isWeight or isSquare):  # Pad only the lines for the weight matrices
        target_rows = ((n_row - 1) // block_size + 1) * block_size
    else: # Else, only the column are padded
        target_rows = n_row 

    # Pad the column
    target_cols = ((n_col - 1) // block_size + 1) * block_size

    # Pad the matrix with 0 (pad = target - n)
    padded_matrix = np.pad(matrix, ((0, target_rows-n_row), (0, target_cols-n_col)), mode='constant')

    # Return the padded matrix
    return padded_matrix

def matrix_splitting(matrix, block_size=16, isWeight=False, isSquare=True):
    """Split the matrix into blocks using slicing to handle unequal row division.
    For weight matrices (isWeight=True), it splits into square blocks of size block_size x block_size.
    For other matrices (isWeight=False), it splits into blocks of size up to block_size x block_size,
    splitting only along rows if the number of rows exceeds block_size."""
    
    # Get the matrix dimensions
    n_row, n_col = matrix.shape

    # Ensure the matrix width is a multiple of block_size
    if n_col % block_size != 0:
        raise ValueError("ERROR: Matrix width must be a multiple of block_size")

    blocks_col = n_col // block_size  # Number of blocks in each column
    blocks = []  # List to store the blocks

    if (isWeight or isSquare):
        # Ensure the matrix height is a multiple of block_size
        if n_row % block_size != 0:
            raise ValueError("Matrix height must be a multiple of block_size")

        blocks_row = n_row // block_size  # Number of blocks in each row
        for i in range(blocks_row):
            for j in range(blocks_col):
                block = matrix[i * block_size:(i + 1) * block_size, j * block_size:(j + 1) * block_size]
                blocks.append(block)
    else:
        # Calculate the number of blocks in each column
        blocks_row = (n_row + block_size - 1) // block_size # Ensure that all rows are processed
        for i in range(blocks_row):
            for j in range(blocks_col):
                row_start = i * block_size
                row_end = min((i + 1) * block_size, n_row)  # Ensure not to exceed the number of rows
                block = matrix[row_start:row_end, j * block_size:(j + 1) * block_size]
                blocks.append(block)

    # Return the list of blocks
    return blocks, blocks_col


###############################################


# EXECUTE MAIN FUNCTION
# ---------------------
if __name__ == "__main__": 
    """
    To execute: 
        > python data_formatting.py <binary_file> <m_rows> <n_columns> <input|weight>
    """
    # Parameters
    dtype = np.int8
    block_size = 16
    debug = True

    # Check the number of arguments
    if len(sys.argv) != 5:
        raise Exception("ERROR: The arguments must be <binary_file> <m_rows> <n_columns> <input|weight> \n\n")

    # Map arguments
    binary_file = sys.argv[1]
    m_rows = int( sys.argv[2] )
    n_columns = int( sys.argv[3] )
    isInput = True if (sys.argv[3] == "input") else False

    # Call the main function
    data_formatting(binary_file, m_rows=16, n_columns=16, isInput=True,
                    dtype=dtype, block_size=block_size, debug=debug)
            

