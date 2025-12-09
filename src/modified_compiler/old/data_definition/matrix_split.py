# IMPORT PACKAGES
# ---------------
import numpy as np


# MATRIX SPLIT FUNCTIONS
# ----------------------
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
