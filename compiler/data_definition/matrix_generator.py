# IMPORT PACKAGES
# ---------------
import numpy as np


# MATRIX GENERATOR FUNCTIONS
# --------------------------
def matrix_int8_creation(n_row=16, n_col=16, isInitRandom=True, random_bound=128):
    """Create a matrix with int8 values."""
    if (isInitRandom): # Random values
        matrix = np.random.randint(-random_bound, random_bound - 1, size=(n_row, n_col), dtype=np.int8)
    else: # Init with 0
        matrix = np.zeros((n_row, n_col), dtype=np.int8)
    # Return the matrix
    return matrix


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
