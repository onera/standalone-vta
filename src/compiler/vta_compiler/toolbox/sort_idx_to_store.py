# IMPORT PACKAGES
# ---------------


###############################################


# sort_idx_to_store
# -----------------
def sort_idx_to_store(idx_to_store, nb_col, block_size):
    """
    Sort idx_to_store into output blocks

    Args:
        idx_to_store (list): Initial list of vectors (tuples (a,b)).
        nb_col (int): Number of blocks on a column.
        block_size (int): Hardware constraint.

    Returns:
        list: sorted list (a,b).
    """
    
    # 1. Nb of parameters 
    N = len(idx_to_store)
    
    # Get the number of block rows (C_blocks_col)
    nb_rows = (N + nb_col - 1) // nb_col  
    
    # Get the number of output block rows
    nb_blocks = (nb_rows + block_size - 1) // block_size 
    
    reorganised_list = []
    
    # 2. Iterate over the number of rows 
    for block_idx in range(nb_blocks):
        # Get the rows to store at this iteration
        start_row_idx = block_idx * block_size
        # Last idx on a row (exclusive), limited by the number of total rows
        end_row_idx = min(start_row_idx + block_size, nb_rows)
        
        # Empty block = stop 
        if start_row_idx >= end_row_idx:
            break
            
        # 3. Iterate on the columns
        for col_idx in range(nb_col):
            
            # 4. Iterate over the elements within a block (the a of the tuple)
            for row_idx in range(start_row_idx, end_row_idx):
                
                # Get the first idx on the current row 
                original_index = (row_idx * nb_col) + col_idx
                
                # Check if the idx does not overflow (last block can be smaller) 
                if original_index < N:
                    reorganised_list.append(idx_to_store[original_index])
    
    # Return the new list
    return reorganised_list

