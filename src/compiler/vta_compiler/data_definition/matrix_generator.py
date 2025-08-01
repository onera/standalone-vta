# IMPORT PACKAGES
# ---------------
import numpy as np


# MATRIX GENERATOR FUNCTIONS
# --------------------------
def matrix_creation(n_row=16, n_col=16, isInitRandom=True, random_bound=0, dtype=np.int8, onlyPositive=False):
    """Create a matrix with dtype values (e.g., int8 or int32)."""
    low_bound = 0 if onlyPositive else -random_bound
    if (isInitRandom): # Random values
        matrix = np.random.randint(low_bound, random_bound - 1, size=(n_row, n_col), dtype=dtype)
    else: # Init with same value everywhere
        matrix = np.full((n_row, n_col), random_bound, dtype=dtype)
    # Return the matrix
    return matrix


def matrix_diagonal(diag_value=0, block_size=16, dtype=np.int8):
    """Create a diagonal matrix with dtype values (e.g., int8 or int32)."""
    # Check if the diag value is an integer
    if (isinstance(diag_value, int)):
        matrix = diag_value * np.eye(block_size, dtype=dtype)
    else:
        raise Exception(f"ERROR: Multiplication constant is in a non-supported data-type ({type(B).__name__}), only integer or matrix are supported! \n\n")
        
    # Return the matrix
    return matrix


def create_matrix_from_binary(file="test.bin", h=1, w=1, dtype=np.int8):
    """Create a matrix from a binary file (the binary file must be arranged as the numpy .tofile function)."""
    # Read the data (1D)
    flat_array = np.fromfile(file, dtype=dtype)
    
    # Reshaphe the data in 2D (h, w)
    matrix = flat_array.reshape((h, w))
    
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
