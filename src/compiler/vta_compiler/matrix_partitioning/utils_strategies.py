# IMPORT PACKAGES
# ---------------
import numpy as np


###############################################

###############################################


def filter_op_for_step(alu_ops, sram_status):
    """
    Filter the current ALU operation regarding the SRAM status (perform the operations only on the loaded vectors).

    Inputs:
        - alu_ops (list): The ALU operation to filter.
        - sram_status (list): The list of loaded vectors.

    Outputs:
        - filtered_ops (list): The filtered ALU operations.
    """
    # Init the final list
    filtered_ops = []

    # Iterate over the alu ops
    for alu_op in alu_ops:
        op_name, params, tuples_list = alu_op

        # If Vector-scalar, it is okay
        if (op_name.endswith("_IMM") or op_name == " RELU"):
            filtered_ops.append(alu_op)
        
        # If vector-vector operation, iterate over the src_list
        else:
            filtered_src = []
            # Iterate over the src_vector
            for src_vector in tuples_list[0][1]:
                if (src_vector in sram_status):
                    filtered_src.append(src_vector)
            
            filtered_ops.append( [op_name, params, [( tuples_list[0][0], filtered_src )]] )
    
    return filtered_ops

# ---------------------------------------------

def get_dst_src_vectors(alu_ops):
    """
    Obtain the DST vector and the SRC vector from an ALU operations
    Input:
        - alu_ops (list): The shape of the list is ['OP_NAME', [some parameters], [list of vectors]]
    Output:
        - dst_vector (tuple): The DST vector extracted from the list of vectors
        - src_vector (list): The list of SRC vector extracted from the list of vectors
    """
    # If it is a vector-scalar operation: just a DST vector
    if (alu_ops[0].endswith("_IMM") or alu_ops[0] == "RELU"):
        dst_vector = alu_ops[2][0]
        src_vector = []
    
    # If vector-vector operation: [dst_vector, [src_vectors]]
    else:
        dst_vector = alu_ops[2][0][0]
        src_vector = alu_ops[2][0][1]

    return dst_vector, src_vector


###############################################


def euclidian_division(dividend, divisor):
    """
    Euclidian division: dividend = divisor * quotient + remainder
    Inputs:
        - dividend: (int) the number to decompose
        - divisor: (int) the modulo
    Outputs:
        - quotient: (int) result of dividend // divisor
        - remainder: (int) result of dividenc % divisor
    """
    return dividend // divisor, dividend % divisor


# ---------------------------------------------

def get_operations(load_A, load_B, A_blocks_col, B_blocks_col, X_blocks_col):
    """
    Generates the list of GeMM operations for a given set of loaded A and B blocks.
    An operation is valid if a block A[i, k] and a block B[k, j] are both loaded.
    The result is accumulated in C[i, j].
    """
    operations = []
    # Create a lookup for B blocks for faster access: map row_k to list of (col_j, B_idx)
    b_lookup = {}
    for b_idx in load_B:
        k, j = euclidian_division(b_idx, B_blocks_col)
        if k not in b_lookup:
            b_lookup[k] = []
        b_lookup[k].append((j, b_idx))

    # Iterate through loaded A blocks
    for a_idx in load_A:
        i, k = euclidian_division(a_idx, A_blocks_col)
        
        # Check if there are any B blocks with a matching row index 'k'
        if k in b_lookup:
            # For each matching B block, create a GeMM operation
            for j, b_idx in b_lookup[k]:
                c_idx = i * X_blocks_col + j
                operations.append(("GeMM", c_idx, a_idx, b_idx))
                
    return operations

# ---------------------------------------------

def imm_alu_on_blocks(imm_operations, store_C):
    # Init
    to_execute = []

    # Iterate on the immediate operations
    for alu_ops in imm_operations:
        # Init tuple to execute
        tuple_list = []
        # Iterate on the tuples 
        for tuple_idx in alu_ops[2]:
            # The tuple is executed on the current C blocks
            if (tuple_idx[0] in store_C):
                # Append the list to return
                tuple_list.append(tuple_idx)
        
        # Append the list with the current operation
        if (len(tuple_list) > 0):
            current_ops = [alu_ops[0]] + [alu_ops[1]] + [tuple_list]
            to_execute.append(current_ops)
        
    return to_execute

# ---------------------------------------------

def sort_alu_by_dst(alu_operations=[]):
    """
    Regroup the ALU operations using the same DST vector
    Input:
        - alu_operations (list): the operations to perform (a sublist can contain multiple DST vectors)
    Output:
        - sorted_list (list): the sorted list of ALU operations (each sublist contains a single DST vector)
    """
    # Step 1: Flatten the list.
    # This ensures that each operation in the new list has exactly one output tuple.
    # Operations with multiple tuples ("_IMM") are duplicated.
    flattened_list = []
    for op_name, params, tuples_list in alu_operations:
        if len(tuples_list) > 1:
            # Create a new list entry for each tuple in the list
            for t in tuples_list:
                flattened_list.append([op_name, params, [t]])
        else:
            # Keep the operation as is if it has only one tuple
            flattened_list.append([op_name, params, tuples_list])

    # Step 2: Sort the flattened list.
    # The sorting key checks the structure of the tuple data to find the correct (a,b) pair.
    # It handles both direct tuples like (a, b) and nested ones like ((a, b), [...]).
    sorted_list = sorted(
        flattened_list,
        key=lambda op: op[2][0][0] if isinstance(op[2][0][0], tuple) else op[2][0]
    )
    return sorted_list
