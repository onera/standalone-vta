# IMPORT PACKAGES
# ---------------


###############################################

# FIND_BLOCK_ADDR_BY_IDX
# ----------------------
def find_logical_block_addr_by_idx(block_idx, addr_dict):
    block_addr_list = addr_dict[0]['blocks_addresses']
    tuple_addr = next(t for t in block_addr_list if t[0] == block_idx)
    return int( tuple_addr[2], 16)

# ---------------------------------------------

# FIND_UOP_ADDR
# -------------
def find_uop_addr(uop_addr, uop_buffer_size, uop_counter):
    uop_logic_addr = int( uop_addr[0]["logical_base_address"], 16)
    current_uop_addr = uop_logic_addr + uop_counter + uop_buffer_size
    return current_uop_addr

# ---------------------------------------------

# BLOCK_IDX_IN_SRAM
# -----------------
def block_idx_in_sram(block_idx, memory_status):
    return memory_status.index(block_idx)

# ---------------------------------------------

# GET_DST_SRC_FROM_CURRENT_ALU
# ----------------------------
def get_dst_src_from_current_alu(current_alu, alu):
    """
    Obtain the DST vector and the SRC vector from an ALU operations
    Input:
        - current_alu (tuple): Either (block_idx, vector_idx) or ((block_idx, vector_idx), [list of src vectors])
        - alu (list): The ALU definition ['OP_NAME', [param], [list of tuples]]
    Output:
        - dst_vector (tuple): The DST vector extracted from the list of vectors
        - src_vector (list): The list of SRC vector extracted from the list of vectors
    """
    # If it is a vector-scalar operation: just a DST vector
    if (alu[0].endswith("_IMM") or alu[0] == "RELU"):
        dst_vector = current_alu
        src_vector = []
    
    # If vector-vector operation: [dst_vector, [src_vectors]]
    else:
        dst_vector = current_alu[0]
        src_vector = current_alu[1]

    return dst_vector, src_vector

# ---------------------------------------------

# HECK_CONSTANT_GAP
# -----------------
def check_constant_gap(numbers: list) -> int:
    """
    Checks if the gap between consecutive elements in a list is constant.
    Args:
        numbers: A list of integers.
    Returns:
        The value of the constant gap if it exists, otherwise -1.
    """
    # A gap cannot be calculated on a list with fewer than 2 elements.
    if len(numbers) < 2:
        return -1
    
    # If it is a tuple, return 1
    if isinstance(numbers[0], tuple):
        return -1

    # Calculate the reference gap using the first two elements.
    expected_gap = numbers[1] - numbers[0]

    # Loop through the rest of the list starting from the third element.
    for i in range(2, len(numbers)):
        # If the current gap is different from the expected one, return -1.
        if numbers[i] - numbers[i-1] != expected_gap:
            return -1

    # If the loop finishes, all gaps are constant.
    return expected_gap