# IMPORT PACKAGES
# ---------------
import numpy as np


# ALU OPERATIONS
# --------------
def alu_operations(alu_operations=[], shape=(16,16), block_size=16):
    """
    Manage all the ALU operations excepting the ALU operations over two matrices.

    Inputs:
        - alu_operations (list from IR): The list of ALU operations
        - shape (tuple: int, int): the shape of the output matrix
        - block_size (int): The hardware constraint dimension
    Results:
        - alu_operations (list): The updated list of operations
    """
    # Dimension
    C_row, C_col = shape

    # Create a new list of alu_operations
    alu_operations = create_alu_operations_list(alu_operations=alu_operations, C_row=C_row, C_col=C_col, block_size=block_size)

    return alu_operations

# ---------------------------------------------

# CREATE_ALU_OPERATIONS_LIST
# --------------------------
def create_alu_operations_list(alu_operations, C_row=1, C_col=1, block_size=16):
    """
    Create the list of ALU operations from the operations dictionary.
    Inputs:
        - alu_operations (list): The extracted operations from the input JSON file
        - C_row (int): The number of rows of C
        - C_col (int): The number of columns of C
        - block_size (int): The vector size
    Output:
        - alu_operations (list): The ALU operations to perform

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

    # Compute C_blocks_col
    C_blocks_col = (C_col + block_size - 1) // block_size

    # Iterate over all the ALU
    for alu_ops in alu_operations:
        block_information = []
        
        # Define the DST vector index (in the unsplitted matrix)
        dst_idx = alu_ops[1][0][0]
        dst_step = alu_ops[1][0][1]

        # Define the SRC vector index if vector-vector operation
        if not alu_ops[0].endswith("_IMM") and alu_ops[0] != "RELU" :
            src_idx = alu_ops[1][1][0]
            src_step = alu_ops[1][1][1]
        # Define the number of iteration
        nb_iteration = alu_ops[1][2]

        # For each iteration append block_information
        for nb in range(0, nb_iteration):
            # Update the DST vector index
            local_dst_idx = dst_idx + dst_step * nb
            # Define the position within a block (first block of a row)
            dst_block_idx = (local_dst_idx // block_size) * C_blocks_col
            dst_row = local_dst_idx % block_size

            # Vector-scalar -> Get the position within all the block on a same row
            if alu_ops[0].endswith("_IMM") or alu_ops[0] == "RELU":
                # Append block_information of the row
                for col in range(0, C_blocks_col):
                    block_information.append( (dst_block_idx+col, dst_row) )
            
            else: # Vector-vector
                # Update the DST vector index
                local_src_idx = src_idx + src_step*nb

                # Define the position within a block (first block of a row)
                src_block_idx = (local_src_idx // block_size) * C_blocks_col
                src_row = local_src_idx % block_size

                # Append block_information of the row
                for col in range(0, C_blocks_col):
                    block_information.append( ((dst_block_idx+col, dst_row), (src_block_idx+col, src_row)) )

        # Append the current alu_ops
        if (nb_iteration > 0):
            alu_ops.append(block_information)

        # Sort the alu_ops
        alu_ops = sort_alu_operations(alu_ops)

        # Append the list with the current alu_ops
        alu_operations_list.append(alu_ops)

    return alu_operations_list

# ---------------------------------------------

# SORT_ALU_OPERATIONS
# -------------------
def sort_alu_operations(alu_ops):
    # Check if it is a IMM or RELU
    if (alu_ops[0].endswith("_IMM") or alu_ops[0] == "RELU"):
        # Do nothing
        pass
    else:
        # Gather the DST vector together
        dict_ops = {}
        for key, value in alu_ops[2]:
            dict_ops.setdefault(key, []).append(value)

        # Convert dict_ops in a list
        alu_ops[2] = list( dict_ops.items() )

    return alu_ops