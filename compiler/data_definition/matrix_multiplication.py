# IMPORT PACKAGES
# ---------------
import numpy as np


# MATRIX MULTIPLICATION FUNCTIONS
# -------------------------------
def truncate_to_int8(x):
    """Truncate a value into int8 (keep the LSB)."""
    return np.bitwise_and(x, 0xFF).astype(np.int8)


def matrix_int8_multiplication(A, B, useClip=False, useReLU=False):
    """Multiply the two matrix together. Return the matrix in int16 and in int8."""
    # Compute ACC in int16
    ACC = np.matmul(A.astype(np.int16), B.astype(np.int16))

    # C is the cast of ACC into int8
    if (useClip): # clip: max(127, value) if value > 0
        C = np.clip(ACC, -128, 127).astype(np.int8) 
    else: # Truncate
        C = truncate_to_int8(ACC)

    # Apply ReLU
    if (useReLU):
        C = np.maximum(C, 0)

    # Return ACC and C
    return ACC, C

def block_matrix_multiply(A_blocks, B_blocks, A_blocks_col, B_blocks_col, block_size=16):
    """Multiply blocks of A with blocks of B and provide the multiplication combinations."""
    # Determine the number of blocks in each dimension
    num_A_blocks_col = A_blocks_col   # Number of blocks per line in A
    num_B_blocks_col = B_blocks_col   # Number of blocks per line in B
    num_A_blocks_row = len(A_blocks) // num_A_blocks_col # Number of row blocks
    num_B_blocks_row = len(B_blocks) // num_B_blocks_col # Number of row blocks
    
    # Initialize the result blocks
    C_blocks = [np.zeros((block_size, block_size), dtype=np.int16) for _ in range(num_A_blocks_row * num_B_blocks_col)]
    
    # Store the combinations done
    combinations = []

    # Perform block multiplication
    for i in range(num_A_blocks_row): # line A
        for j in range(num_B_blocks_col): # col B, number of blocks per line
            for k in range(num_A_blocks_col): # col A / line B, number of blocks to do the multiplication
                A_block_index = i * num_A_blocks_col + k # Current block of A
                B_block_index = k * num_B_blocks_col + j # Current block of B
                C_block_index = i * num_B_blocks_col + j # Current block of C

                # Perform matrix multiplication and accumulate the result
                C_blocks[C_block_index][:A_blocks[A_block_index].shape[0], :B_blocks[B_block_index].shape[1]] += np.matmul(A_blocks[A_block_index].astype(np.int16), B_blocks[B_block_index].astype(np.int16)) # Do the multiplication
                combinations.append(f"C{C_block_index} += A{A_block_index} * B{B_block_index}") # Add the combination

    return C_blocks, combinations # return the blocks and the combinations

# Function to reconstruct the matrix from blocks
def reconstruct_matrix(blocks, original_shape, block_size=16):
    """Get a single matrix from multiple matrix blocks."""
    rows = (original_shape[0] + block_size - 1) // block_size
    cols = (original_shape[1] + block_size - 1) // block_size
    
    # Initialize the full matrix with zeros
    full_matrix = np.zeros((rows * block_size, cols * block_size), dtype=blocks[0].dtype)
    
    # Fill in the blocks
    for i in range(rows):
        for j in range(cols):
            block_index = i * cols + j
            full_matrix[i*block_size:(i+1)*block_size, j*block_size:(j+1)*block_size] = blocks[block_index]
    
    return full_matrix[:original_shape[0], :original_shape[1]]  # Trunc to initial dimension
