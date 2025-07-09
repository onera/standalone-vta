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

# CREATE_ALU_OPERATIONS_LIST
# --------------------
def create_alu_operations_list(operations_dict, nb_C_blocks=1, C_blocks_col=1, block_size=16):
    """
    Create the list of ALU operations from the operations dictionary.
    Inputs:
        - operations_dict: (dictionary) extract from the input JSON file
        - nb_C_blocks: (int) number of blocks in C
        - C_blocks_col: (int) number of columns of C
    Output:
        - alu_operations_list: (list) The ALU operations to perform

    The output format: ["OP", [information within matrix], [information within block]]
        - Information within matrix:
            non-iterative vector-vector: [DST row idx, SRC row idx]
            iterative vector-vector: [[1st DST idx, step], [1st SRC idx, step], number of iteration]
            non-iterative vector-scalar ("_IMM"): [DST row idx, scalar]
            iterative vector-scalar ("_IMM"): [[1st DST idx, step], scalar, number of iteration]
        - Information within blocks:
            vector-vector: [((DST block idx, DST block's row idx), (SRC block idx, SRC block's row idx)), ...]
            vector-scalar: [(block idx, block's row idx)]
    """
    # Init the output
    alu_operations_list = []

    # If there is ALU operations, append the list
    if "ALU" in operations_dict:

        # Iterate over all the ALU
        for alu_ops in operations_dict["ALU"]:
            block_information = []

            # Check if the ALU is iterative or not
            if (len(alu_ops[1]) == 3):
                dst_idx = alu_ops[1][0][0]
                dst_step = alu_ops[1][0][1]
                nb_iteration = alu_ops[1][2]
                if not alu_ops[0].endswith("_IMM"):
                    src_idx = alu_ops[1][1][0]
                    src_step = alu_ops[1][1][1]
            else: 
                dst_idx = alu_ops[1][0]
                dst_step = 0
                nb_iteration = 1

            # For each iteration append block_information
            for nb in range(0, nb_iteration):
                local_dst_idx = dst_idx + dst_step*nb
                dst_block_idx = (local_dst_idx // block_size) * C_blocks_col
                dst_row = local_dst_idx % block_size

                # Vector-scalar
                if alu_ops[0].endswith("_IMM"):
                    # Append block_information
                    for col in range(0, C_blocks_col):
                        block_information.append( (dst_block_idx+col, dst_row) )
                else: # Vector-vector
                    # Iterative
                    if (len(alu_ops[1]) == 3):
                        local_src_idx = src_idx + src_step*nb
                        src_block_idx = (local_src_idx // block_size) * C_blocks_col
                        src_row = local_src_idx % block_size
                    else:
                        src_idx = alu_ops[1][1]
                        src_block_idx = (src_idx // block_size) * C_blocks_col
                        src_row = src_idx % block_size
                    # Append block_information
                    for col in range(0, C_blocks_col):
                        block_information.append( ((dst_block_idx+col, dst_row), (src_block_idx+col, src_row)) )

            # Append the current alu_ops
            alu_ops.append(block_information)
            # Append the list with the current alu_ops
            alu_operations_list.append(alu_ops)

    return alu_operations_list

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
