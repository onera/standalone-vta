# IMPORT PACKAGES
# ---------------
import numpy as np


# ALU OPERATIONS
# --------------
def alu_operations(matrix, alu_operation="MAX_IMM", dst_idx=0, elem2=0, isIMM=True):
    """
    Perform an alu_operation on the matrix on the line index dst_idx.
    If isIMM: operand = elem2 else operand = matrix[elem2]
    The operations is matrix[dst_idx] = ALU(matrix[dst_idx], operand)

    Inputs:
        - matrix: a numpy matrix
        - alu_operation: a string for the operation to perform
        - dst_idx: the line index on which perform the operation
        - elem2: the line index or imm_value to use for the operation
        - isIMM: boolean to identify if it is vector-vector operation or vector-scalar
    Result:
        - matrix: the updated numpy matrix
    """
    operand = elem2 if isIMM else matrix[elem2]

    if (alu_operation.startswith("MAX")):
        matrix[dst_idx] = np.maximum(matrix[dst_idx], operand)
    elif (alu_operation.startswith("MIN")):
        matrix[dst_idx] = np.minimum(matrix[dst_idx], operand)
    elif (alu_operation.startswith("ADD")):
        matrix[dst_idx] = np.add(matrix[dst_idx], operand)
    elif (alu_operation.startswith("MUL")):
        matrix[dst_idx] = np.multiply(matrix[dst_idx], operand)
    elif (alu_operation.startswith("SHR")):
        matrix[dst_idx] = np.right_shift(matrix[dst_idx], operand)
    else:
        raise Exception(f"ERROR: ALU non-supported operations ({alu_operation})! \n\n")

    return matrix

# ---------------------------------------------

# DELETE MATRIX ROW
# -----------------
def delete_matrix_row(input_blocks, blocks_col=1, block_size=16, idx_to_delete=[], matrix_height=1, padding=0):
    # Add the padding in the idx_to_delete
    for i in range(padding):
        idx_to_delete.append(i+matrix_height)

    # Sort the list and remove duplicata
    idx_to_delete = sorted(set(idx_to_delete))

    # Copy the matrix and not modify the previous
    blocks = input_blocks.copy()

    # Iterate on the index
    for idx in reversed(idx_to_delete):
        # Compute the local index within the block
        block_idx = (idx // block_size) * blocks_col
        local_idx = idx % block_size

        # Iterate over all the blocks in the same row
        for col in range(blocks_col):
            blocks[block_idx+col] = np.delete(blocks[block_idx+col], local_idx, axis=0)
    
    # Return the blocks and the sorted idx_to_delete
    return blocks, idx_to_delete
