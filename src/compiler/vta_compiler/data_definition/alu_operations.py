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

    if (alu_operation.startswith("MAX") or alu_operation == "RELU"):
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
    idx_to_store = []

    # If there is ALU operations, append the list
    if "ALU" in operations_dict:

        # Iterate over all the ALU
        for alu_ops in operations_dict["ALU"]:
            block_information = []

            # Check if it is a special operator
            if ("RELU" == alu_ops[0]):
                if "ACCUMULATOR" in operations_dict["MATRICES"][0]:
                    nb_iteration = operations_dict["MATRICES"][0]["ACCUMULATOR"][0]
                else:
                    nb_iteration = operations_dict["MATRICES"][0]["INPUT"][0]
                alu_ops = ["RELU", [[0, 1], 0, nb_iteration]]
                dst_idx = 0
                dst_step = 1
            
            # Check if the ALU is iterative or not
            elif (len(alu_ops[1]) == 3): # ITERATIVE
                # Define the DST vector index (in the unsplitted matrix)
                dst_idx = alu_ops[1][0][0]
                dst_step = alu_ops[1][0][1]
                # Define the SRC vector index if vector-vector operation
                if not alu_ops[0].endswith("_IMM") and alu_ops[0] != "RELU" :
                    src_idx = alu_ops[1][1][0]
                    src_step = alu_ops[1][1][1]
                # Define the number of iteration
                nb_iteration = alu_ops[1][2]
            else: # UNIQUE
                # Define the DST vector index (in the unsplitted matrix)
                dst_idx = alu_ops[1][0]
                dst_step = 0
                # Define the SRC vector index if vector-vector operation
                if not alu_ops[0].endswith("_IMM") and alu_ops[0] != "RELU" :
                    src_idx = alu_ops[1][1]
                    src_step = 0
                # Define the number of iteration
                nb_iteration = 1

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
                        idx_to_store.append ( (dst_block_idx+col, dst_row) )

            # Append the current alu_ops
            if (nb_iteration > 0):
                alu_ops.append(block_information)

            # Sort the alu_ops
            alu_ops = sort_alu_operations(alu_ops)

            # Append the list with the current alu_ops
            alu_operations_list.append(alu_ops)
    
    # Sort the idx_to_store
    idx_to_store = sorted(set(idx_to_store))

    return alu_operations_list, idx_to_store

# ---------------------------------------------

# DELETE MATRIX ROW
# -----------------
def delete_matrix_row(input_blocks, blocks_col=1, block_size=16, idx_to_store=[], matrix_height=1, padding=0):
    # If idx_to_store is empty, everything is stored
    if (len(idx_to_store) == 0):
        return input_blocks
    
    # Else, store the right vectors
    
    # Define the number of blocks
    nb_block = len(input_blocks)
    
    # Copy the matrix and not modify the previous
    blocks = input_blocks.copy()

    # Init the idx to delete
    idx_to_delete = []
    for b in range(0, nb_block):
        for v in reversed(range(0, block_size)):
            if (b, v) in idx_to_store:
                # Skip this idx
                continue
            else: # Else append the idx to delete
                idx_to_delete.append( (b,v) )

    # Iterate over the list to delete and remove the vector
    for block_idx, vector_idx in idx_to_delete:
        blocks[block_idx] = np.delete( blocks[block_idx], vector_idx, axis=0 )

    # Return the blocks
    return blocks

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