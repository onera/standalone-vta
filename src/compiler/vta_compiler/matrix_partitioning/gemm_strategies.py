# IMPORT PACKAGES
# ---------------
import numpy as np

from matrix_partitioning.utils_strategies import *


###############################################

def mul_constant_strategy(nb_A, inp_block_buffer_size, acc_block_buffer_size, out_block_buffer_size, alu_operations):
    # Define buffer size which is the minimal size of the buffer
    buffer_size = min(inp_block_buffer_size, acc_block_buffer_size, out_block_buffer_size)

    # Init strategy
    strategy = [] # [([Ai], [Bi], [Xi], [Mi], [Ti], [Ci], [Operations])]

    if (buffer_size < 2):
        raise Exception(f"ERROR: The capacity of the buffer is {buffer_size} but it must be at least 2 (to load two blocks)! \n\n")

    # Create the step
    for i in range(0, nb_A, buffer_size):

        # Load B only once
        if (i == 0):
            load_B = [0]
        else:
            load_B = []


        # The last element to store at this step
        end = min(i + buffer_size, nb_A)

        # Create the list load_A, load_X and store_C
        load_A = list( range(i, end) )

        # Define the operations
        ops = get_mul_constant_operations(load_A) \
            + imm_alu_on_blocks(alu_operations, load_A)

        # Append the strategy 
        strategy.append( (load_A, load_B, load_A, load_A, [], load_A, ops) )


    # Return the strategy
    return strategy



###############################################


def strategy_1(nb_A=1, A_blocks_col=1, nb_B=1, B_blocks_col=1, nb_X=1, X_blocks_col=1,
               inp_block_buffer_size=4, wgt_block_buffer_size=32, acc_block_buffer_size=4, out_block_buffer_size=4,
               alu_operations=[]):
    """
    Strategy 1 focuses on quickly compute one C element. It loads A row-by-row and B column-by-column.
    """
    # Define buffer size which is the minimal size of the buffer
    buffer_size = min(inp_block_buffer_size, wgt_block_buffer_size, acc_block_buffer_size, out_block_buffer_size)

    # Init strategy
    strategy = [] # [([Ai], [Bi], [Xi], [Mi], [Ti], [Ci], [Operations])]

    # Define the delta 
    delta = min(buffer_size, A_blocks_col)

    # Define A_blocks_col = nb_delta * delta + remainder
    nb_delta, remainder = euclidian_division(A_blocks_col, delta)

    # Iterate over C
    for idx in range(0, nb_X):
        # Load / store X
        load_X = [idx]
        memory_status = load_X

        # Get i and j (idx = B_blocks_col * i + j)
        i, j = euclidian_division(idx, B_blocks_col)

        for idx_delta in range(0, nb_delta):
            # Init the buffers to load
            load_A = []
            load_B = []

            # Fulfil the buffers
            for local_idx in range(0, delta):
                # Get k
                k = local_idx + idx_delta * delta

                # Append the blocks to load
                load_A.append( i * A_blocks_col + k )
                load_B.append( k * B_blocks_col + j )

            # Get the operations
            ops = get_gemm_operations(load_A, load_B, A_blocks_col, B_blocks_col, X_blocks_col)
            
            # Append the strategy [([Ai], [Bi], [Xi], [Mi], [Ti], [Ci], [Operations])]
            if (idx_delta == 0): # First: load X
                strategy.append( (load_A, load_B, load_X, memory_status, [], [], ops) )
            else: # Then, accumulate
                strategy.append( (load_A, load_B, [], memory_status, [], [], ops) )
        
        # Load the remainding A and B blocks
        if (remainder > 0):
            load_A = []
            load_B = []
            for local_idx in range(0, remainder):
                # Get k
                k = local_idx + delta * nb_delta

                # Append the blocks to load
                load_A.append( i * A_blocks_col + k )
                load_B.append( k * B_blocks_col + j )

            # Get the operations
            ops = get_gemm_operations(load_A, load_B, A_blocks_col, B_blocks_col, X_blocks_col) \
                + imm_alu_on_blocks(alu_operations, load_X)

            # Append the strategy [([Ai], [Bi], [Xi], [Mi], [Ti], [Ci], [Operations])]
            strategy.append( (load_A, load_B, [], memory_status, [], load_X, ops) )
        else: # Modify the last step
            last_step = strategy[-1]
            last_ops = last_step[6] + imm_alu_on_blocks(alu_operations, load_X)
            strategy[-1] = (last_step[0], last_step[1], last_step[2], last_step[3], [], load_X, last_ops)

    # Return the strategy
    return strategy


# ---------------------------------------------

def strategy_2(nb_A=1, A_blocks_col=1, nb_B=1, B_blocks_col=1, nb_X=1, X_blocks_col=1,
               inp_block_buffer_size=4, wgt_block_buffer_size=32, acc_block_buffer_size=4, out_block_buffer_size=4,
               alu_operations=[]):
    """
    Strategy 2 performs region-based computation, tiling matrices into smaller square regions.
    """
    # --- Calcul des dimensions des matrices en blocs ---
    A_blocks_row = nb_A // A_blocks_col
    B_blocks_row = nb_B // B_blocks_col # Must be equal to A_blocks_col
    X_blocks_row = nb_X // X_blocks_col # Must be equal to A_blocks_row

    # 1 - Size of the C's tile (biggest rectangular tile fitting within acc_block_buffer_size: tile_h x tile_w)
    # Try to be square
    if acc_block_buffer_size > 0:
        tile_h = int(np.sqrt(acc_block_buffer_size))
        while tile_h > 0 and acc_block_buffer_size % tile_h != 0:
            tile_h -=1
        if tile_h == 0: tile_h = 1 # Fallback
        tile_w = acc_block_buffer_size // tile_h
    else:
        tile_h, tile_w = 1, 1

    # Limit tile's dimension to C's dimension
    tile_h = min(tile_h, A_blocks_row)
    tile_w = min(tile_w, X_blocks_col)
    
    # 2 - Size of the chunk for the common dimension K
    # A (tile_h x tile_k) must fit inp_block_buffer_size
    # B (tile_k x tile_w) must fit wgt_block_buffer_size
    # => Compute maximum size of tile_k respecting both constraints
    if tile_h > 0:
        max_k_for_A = inp_block_buffer_size // tile_h
    else:
        max_k_for_A = A_blocks_col
        
    if tile_w > 0:
        max_k_for_B = wgt_block_buffer_size // tile_w
    else:
        max_k_for_B = A_blocks_col

    tile_k = min(A_blocks_col, max_k_for_A, max_k_for_B)
    if tile_k == 0: tile_k = 1 # Ensure having at least 1 element

    # Subfunction to get indices of the sub-matrices
    def get_sub_matrix_indices(start_row, start_col, num_rows, num_cols, total_matrix_cols):
        indices = []
        for r_offset in range(num_rows):
            for c_offset in range(num_cols):
                idx = (start_row + r_offset) * total_matrix_cols + (start_col + c_offset)
                indices.append(idx)
        return indices

    # 3 - Generate the computation strategy
    strategy = []
    
    # Iterate over C's tiles (row then column)
    for i in range(0, X_blocks_row, tile_h):
        current_h = min(tile_h, X_blocks_row - i)

        for j in range(0, X_blocks_col, tile_w):
            current_w = min(tile_w, X_blocks_col - j)
            
            # Indices for the current C_ij tile (and the associated X)
            c_indices = get_sub_matrix_indices(i, j, current_h, current_w, X_blocks_col)
            x_indices = c_indices
            
            # Iteration over K
            # C_ij = sum_k(A_ik * B_kj)
            for k_step, k in enumerate(range(0, A_blocks_col, tile_k)):
                current_k = min(tile_k, A_blocks_col - k)

                # Indices for A's tile (A_ik)
                a_indices = get_sub_matrix_indices(i, k, current_h, current_k, A_blocks_col)
                
                # Indices for B's tile (B_kj) 
                b_indices = get_sub_matrix_indices(k, j, current_k, current_w, B_blocks_col)
                
                # At the very beginning: load X, then accumulate
                load_X = x_indices if k_step == 0 else []

                # Get the operations
                ops = get_gemm_operations(a_indices, b_indices, A_blocks_col, B_blocks_col, X_blocks_col)
                
                # Append the strategy [([Ai], [Bi], [Xi], [Mi], [Ti], [Ci], [Operations])]
                strategy.append((a_indices, b_indices, load_X, x_indices, [], [], ops))

            # Finally, store C_ij
            if strategy:
                last_step = strategy[-1]
                last_ops = last_step[6] + imm_alu_on_blocks(alu_operations, c_indices)
                strategy[-1] = (last_step[0], last_step[1], last_step[2], last_step[3], [], c_indices, last_ops)

    return strategy


# ---------------------------------------------

def strategy_3(nb_A=1, A_blocks_col=1, nb_B=1, B_blocks_col=1, nb_X=1, X_blocks_col=1,
               inp_block_buffer_size=4, wgt_block_buffer_size=32, acc_block_buffer_size=4, out_block_buffer_size=4,
               alu_operations=[]):
    """
    Strategy 3 computes C column-by-column. It loads A column-by-column and single element of B.
    """
    # Define buffer size which is the minimal size of the buffer
    buffer_size = min(inp_block_buffer_size, wgt_block_buffer_size, acc_block_buffer_size, out_block_buffer_size)

    # Init strategy
    strategy = [] # [([Ai], [Bi], [Xi], [Mi], [Ti], [Ci], [Operations])]

    # Define X_blocks_row
    X_blocks_row = nb_X//X_blocks_col

    # Define the delta 
    delta = min(buffer_size, X_blocks_row)

    # Define X_blocks_row = nb_delta * delta + remainder
    nb_delta, remainder = euclidian_division(X_blocks_row, delta)

    # Iterate over nb_delta
    for idx_delta in range(0, nb_delta):
        # Iterate over the number of C's columns
        for j in range(0, X_blocks_col):
            # Define each step
            for k in range(0, A_blocks_col):
                # Load B
                load_B = [ k * B_blocks_col + j ]

                # Init other loads / store
                load_A = []
                load_X = []
                store_C = []

                # Load / store delta row elements of C, A, X
                for local_idx in range(0, delta):
                    i = idx_delta * delta + local_idx

                    # Load X only the first time, then accumulate
                    if (k==0):
                        load_X.append( i * X_blocks_col + j )
                    memory_status = load_X if (len(load_X) > 0) else memory_status
                    
                    # Load A 
                    load_A.append( i * A_blocks_col + k )

                    # Store C on the last iteration
                    if (k==A_blocks_col-1):
                        store_C.append( i * X_blocks_col + j )

                # Get the operations
                ops = get_gemm_operations(load_A, load_B, A_blocks_col, B_blocks_col, X_blocks_col) \
                    + imm_alu_on_blocks(alu_operations, store_C)

                # Append the strategy [([Ai], [Bi], [Xi], [Mi], [Ti], [Ci], [Operations])]
                strategy.append( (load_A, load_B, load_X, memory_status, [], store_C, ops) )
            
    # Load the remainding C elements on the row
    if (remainder > 0):
        # Iterate over the number of C's columns
        for j in range(0, X_blocks_col):
            # Define each step
            for k in range(0, A_blocks_col):
                # Load B
                load_B = [ k * B_blocks_col + j ]

                # Init other loads / store
                load_A = []
                load_X = []
                store_C = []

                # Load / store delta row elements of C, A, X
                for local_idx in range(0, remainder):
                    i = delta * nb_delta + local_idx

                    # Load X only the first time, then accumulate
                    if (k==0):
                        load_X.append( i * X_blocks_col + j )
                    memory_status = load_X if (len(load_X) > 0) else memory_status
                    
                    # Load A 
                    load_A.append( i * A_blocks_col + k )

                    # Store C on the last iteration
                    if (k==A_blocks_col-1):
                        store_C.append( i * X_blocks_col + j )
                
                # Get the operations
                ops = get_gemm_operations(load_A, load_B, A_blocks_col, B_blocks_col, X_blocks_col) \
                    + imm_alu_on_blocks(alu_operations, store_C)

                # Append the strategy [([Ai], [Bi], [Xi], [Mi], [Ti], [Ci], [Operations])]
                strategy.append( (load_A, load_B, load_X, memory_status, [], store_C, ops) )
  
    # Return the strategy
    return strategy

# ---------------------------------------------

def strategy_4(nb_A=1, A_blocks_col=1, nb_B=1, B_blocks_col=1, nb_X=1, X_blocks_col=1,
               inp_block_buffer_size=4, wgt_block_buffer_size=32, acc_block_buffer_size=4, out_block_buffer_size=4,
               alu_operations=[]):
    """
    Strategy 4 computes C row-by-row. It loads single element of A and B row-by-row.
    """
    # Define buffer size which is the minimal size of the buffer
    buffer_size = min(inp_block_buffer_size, wgt_block_buffer_size, acc_block_buffer_size, out_block_buffer_size)

    # Init strategy
    strategy = [] # (C, A, B, X)

    # Define the delta 
    delta = min(buffer_size, X_blocks_col)

    # Define X_blocks_col = nb_delta * delta + remainder
    nb_delta, remainder = euclidian_division(X_blocks_col, delta)

    # Iterate over the rows of C
    for i in range(0, nb_X//X_blocks_col):
        # Iterate over nb_delta to load a row of C
        for idx_delta in range(0, nb_delta):
            # Define each step
            for k in range(0, A_blocks_col):
                # Load A
                load_A = [ i * A_blocks_col + k ]

                # Init other loads / store
                load_B = []
                load_X = []
                store_C = []

                # Load / store delta row elements of C, B, X
                for local_idx in range(0, delta):
                    j = idx_delta * delta + local_idx

                    # Load X only the first time, then accumulate
                    if (k==0):
                        load_X.append( i * X_blocks_col + j )
                    memory_status = load_X if (len(load_X) > 0) else memory_status
                    
                    # Load B (B_blocks_col = X_blocks_col)
                    load_B.append( k * B_blocks_col + j )

                    # Store C on the last iteration
                    if (k==A_blocks_col-1):
                        store_C.append( i * X_blocks_col + j )
                
                # Get the operations
                ops = get_gemm_operations(load_A, load_B, A_blocks_col, B_blocks_col, X_blocks_col) \
                    + imm_alu_on_blocks(alu_operations, store_C)

                # Append the strategy [([Ai], [Bi], [Xi], [Mi], [Ti], [Ci], [Operations])]
                strategy.append( (load_A, load_B, load_X, memory_status, [], store_C, ops) )
            
        # Load the remainding C elements on the row
        if (remainder > 0):
            # Load delta row elements
            for k in range(0, A_blocks_col):
                # Load A
                load_A = [ i * A_blocks_col + k ]

                # Init other loads / store
                load_B = []
                load_X = []
                store_C = []

                # Load / store C, B, X
                for local_idx in range(0, remainder):
                    j = delta * nb_delta + local_idx

                    # Load X only the first time, then accumulate
                    if (k==0):
                        load_X.append( i * X_blocks_col + j )
                    memory_status = load_X if (len(load_X) > 0) else memory_status
                    
                    # Load B (B_blocks_col = X_blocks_col)
                    load_B.append( k * B_blocks_col + j )

                    # Store C on the last iteration
                    if (k==A_blocks_col-1):
                        store_C.append( i * X_blocks_col + j )
                
                # Get the operations
                ops = get_gemm_operations(load_A, load_B, A_blocks_col, B_blocks_col, X_blocks_col) \
                    + imm_alu_on_blocks(alu_operations, store_C)

                # Append the strategy [([Ai], [Bi], [Xi], [Mi], [Ti], [Ci], [Operations])]
                strategy.append( (load_A, load_B, load_X, memory_status, [], store_C, ops) )
  
    # Return the strategy
    return strategy

