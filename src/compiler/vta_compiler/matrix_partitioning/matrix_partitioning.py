# IMPORT PACKAGES
# ---------------
import numpy as np


###############################################


# Matrix partitioning
# -------------------
def matrix_partitioning(nb_A=1, A_blocks_col=1, nb_B=1, B_blocks_col=1, nb_X=1, X_blocks_col=1, nb_C=1, C_blocks_col=1,
                        inp_block_buffer_size=4, wgt_block_buffer_size=32, acc_block_buffer_size=4, out_block_buffer_size=4,
                        alu_operations=[], idx_to_delete=[],
                        strategy_selector=1,
                        debug=True):
    """
    The function checks if any matrix (A, B, X, C) is overfitting.
    If yes, it applies the selected strategy. Else, the computation is perform without partitioning.

    Inputs: # represents either matrix A, B, X or C, $ represents either inp, wgt, acc or out.
        - nb_# (int): the number of blocks in the related matrix
        - #_blocks_col (int): the number of blocks to have a matrix row. 
            E.g., nb_A = 6 and A_blocks_col = 2 represents the 3x2-blocks A matrix
        - $_block_buffer_size (int): the number of blocks that fit the related SRAM buffer
        - alu_operations (list): a list of the ALU operations to perfom
        - idx_to_delete (list): a list of the output matrix's row indexes not to store
        - strategy_selector (int): an integer in [1..4] to select a strategy
        - debug (boolean): a boolean to print the execution information
    Outputs:
        - isOverfitting (boolean): it is true if at least one matrix overfits the SRAM (i.e., a strategy is applied)
        - strategy (list of tuple): each tuple represents a computation step. 
            The tuple is composed of 5 lists: ([Ci], [Ai], [Bi], [Xi], [Operations]). 
            Each list correspond to a specific action to perform at this step: 
                1. the C elements to store, 
                2. the A elements to load, 
                3. the B elements to load, 
                4. the X elements to load,
                5. the operations to perform on each block.
    """
    # Check strategy assumptions
    if not ( (acc_block_buffer_size == out_block_buffer_size) \
           and (nb_X == nb_C) and (X_blocks_col == C_blocks_col) ):
        raise Exception(f"ERROR: Assumptions for matrix partitioning: \
                        \n\t 1. acc_block_buffer_size ({acc_block_buffer_size}) = out_block_buffer_size ({out_block_buffer_size}); \
                        \n\t 2. nb_X ({nb_X}) = nb_C ({nb_C}) and X_blocks_col ({X_blocks_col}) = C_blocks_col ({C_blocks_col})! \n\n")
    # Check data consistency
    if ( (nb_A%A_blocks_col != 0) or (nb_B%B_blocks_col != 0) or (nb_C%C_blocks_col != 0) ):
        raise Exception(f"ERROR: Data are not consistent: results should be 0 \
                        \n\t nb_A%A_blocks_col = {nb_A%A_blocks_col} \
                        \n\t nb_B%B_blocks_col = {nb_B%B_blocks_col} \
                        \n\t nb_C%C_blocks_col = {nb_C%C_blocks_col} \n\n")
    if ( (nb_A//A_blocks_col != nb_C//C_blocks_col) or (B_blocks_col != C_blocks_col) or (nb_X != nb_C) ):
        raise Exception(f"ERROR: Data are not consistent: results should be equal: \
                        \n\t nb_A//A_blocks_col ({nb_A//A_blocks_col}) = nb_C//C_blocks_col ({nb_C//C_blocks_col}), \
                        \n\t B_blocks_col ({B_blocks_col}) = C_blocks_col ({C_blocks_col}), \
                        \n\t nb_X ({nb_X}) = nb_C ({nb_C})!\n\n")
    
    # Check if the data fits
    if ((nb_A > inp_block_buffer_size) or (nb_B > wgt_block_buffer_size) or (nb_C > out_block_buffer_size)):
        isOverfitting = True

        # Get the alu_imm operations 
        imm_operations = []
        nb_alu_imm = next( (i for i, op in enumerate(alu_operations) if (not op[0].endswith("_IMM") and op[0] != "RELU")), len(alu_operations) )
        for i in range(0, nb_alu_imm):
            imm_operations.append( alu_operations[i] )

        # Get the other operations
        other_alu_operations = []
        for i in range(nb_alu_imm, len(alu_operations)):
            other_alu_operations.append( alu_operations[i] )


        # Common parameters for all strategies
        params = {
            'nb_A': nb_A, 'A_blocks_col': A_blocks_col,
            'nb_B': nb_B, 'B_blocks_col': B_blocks_col,
            'nb_X': nb_X, 'X_blocks_col': X_blocks_col,
            'nb_C': nb_C, 'C_blocks_col': C_blocks_col,
            'inp_block_buffer_size': inp_block_buffer_size,
            'wgt_block_buffer_size': wgt_block_buffer_size,
            'acc_block_buffer_size': acc_block_buffer_size,
            'out_block_buffer_size': out_block_buffer_size,
            'alu_operations': imm_operations, 
            'idx_to_delete': idx_to_delete
        }
        
        # Apply the strategy:
        if (strategy_selector == 1):
            strategy = strategy_1(**params)
        elif (strategy_selector == 2):
            strategy = strategy_2(**params)
        elif (strategy_selector == 3):
            strategy = strategy_3(**params)
        elif (strategy_selector == 4):
            strategy = strategy_4(**params)
        else:
            raise Exception(f"ERROR: Matrix partitioning strategy {strategy_selector} does not exist!\n\n")
    
    else: # No overfitting
        isOverfitting = False

        # Load A and B and get the operations
        load_A = [i for i in range(0, nb_A)]
        load_B = [i for i in range(0, nb_B)]
        ops = get_operations(load_A, load_B, A_blocks_col, B_blocks_col, C_blocks_col)
        
        # Add ALU operations
        ops = ops + alu_operations

        strategy = [([i for i in range(0, nb_C)],
                     load_A,
                     load_B,
                     [i for i in range(0, nb_X)],
                     ops)]
    
    # Debug
    if (debug):
        print("\n\nMATRIX PARTITIONING:")
        print(f"Number of storable blocks within each SRAM buffer: \
            \n INP: {inp_block_buffer_size} blocks, \
            \n WGT: {wgt_block_buffer_size} blocks, \
            \n ACC=OUT: {out_block_buffer_size} blocks \n")
        print(f"Number of blocks to store: \
            \n INP: {nb_A} blocks (including A_blocks_col = {A_blocks_col}), \
            \n WGT: {nb_B} blocks (including B_blocks_col = {B_blocks_col}), \
            \n ACC=OUT: {nb_C} blocks (including C_blocks_col = {C_blocks_col})\n")
        print(f"\nDoes matrix overfit SRAM? {isOverfitting} \nThe strategy to address it: {strategy_selector}")
        print(f"\nStrategy [([C], [A], [B], [X], [Operations])]: (nb of steps: {len(strategy)})")
        for i, step in enumerate(strategy):
            print(f"\nStep {i}: {step}")

    # Return if it is overfitting and the strategy [([Ci], [Ai], [Bi], [Xi])]
    return isOverfitting, strategy

# ---------------------------------------------

def strategy_1(nb_A=1, A_blocks_col=1, nb_B=1, B_blocks_col=1, nb_X=1, X_blocks_col=1, nb_C=1, C_blocks_col=1,
               inp_block_buffer_size=4, wgt_block_buffer_size=32, acc_block_buffer_size=4, out_block_buffer_size=4,
               alu_operations=[], idx_to_delete=[]):
    """
    Strategy 1 focuses on quickly compute one C element. It loads A row-by-row and B column-by-column.
    """
    # Define buffer size which is the minimal size of the buffer
    buffer_size = min(inp_block_buffer_size, wgt_block_buffer_size, acc_block_buffer_size, out_block_buffer_size)

    # Init strategy
    strategy = [] # (C, A, B, X)

    # Define the delta 
    delta = min(buffer_size, A_blocks_col)

    # Define A_blocks_col = nb_delta * delta + remainder
    nb_delta, remainder = euclidian_division(A_blocks_col, delta)

    # Iterate over C
    for idx in range(0, nb_C):
        # Load / store X
        load_X = [idx]

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
            ops = get_operations(load_A, load_B, A_blocks_col, B_blocks_col, C_blocks_col)
            
            # Append the strategy (C, A, B, X, Operations)
            if (idx_delta == 0): # First: load X
                strategy.append( ([], load_A, load_B, load_X, ops) )
            else: # Then, accumulate
                strategy.append( ([], load_A, load_B, [], ops) )
        
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
            ops = get_operations(load_A, load_B, A_blocks_col, B_blocks_col, C_blocks_col) \
                + imm_alu_on_blocks(alu_operations, load_X)

            # Append the strategy (C, A, B, X, Operations)
            strategy.append( (load_X, load_A, load_B, [], ops) )
        else: # Modify the last step
            last_step = strategy[-1]
            last_ops = last_step[4] + imm_alu_on_blocks(alu_operations, load_X)
            strategy[-1] = (load_X, last_step[1], last_step[2], last_step[3], last_ops)

    # Return the strategy
    return strategy


# ---------------------------------------------

def strategy_2(nb_A=1, A_blocks_col=1, nb_B=1, B_blocks_col=1, nb_X=1, X_blocks_col=1, nb_C=1, C_blocks_col=1,
               inp_block_buffer_size=4, wgt_block_buffer_size=32, acc_block_buffer_size=4, out_block_buffer_size=4,
               alu_operations=[], idx_to_delete=[]):
    """
    Strategy 2 performs region-based computation, tiling matrices into smaller square regions.
    """
    # --- Calcul des dimensions des matrices en blocs ---
    A_blocks_row = nb_A // A_blocks_col
    B_blocks_row = nb_B // B_blocks_col # Must be equal to A_blocks_col
    C_blocks_row = nb_C // C_blocks_col # Must be equal to A_blocks_row

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
    tile_w = min(tile_w, C_blocks_col)
    
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
    for i in range(0, C_blocks_row, tile_h):
        current_h = min(tile_h, C_blocks_row - i)

        for j in range(0, C_blocks_col, tile_w):
            current_w = min(tile_w, C_blocks_col - j)
            
            # Indices for the current C_ij tile (and the associated X)
            c_indices = get_sub_matrix_indices(i, j, current_h, current_w, C_blocks_col)
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
                ops = get_operations(a_indices, b_indices, A_blocks_col, B_blocks_col, C_blocks_col)
                
                # Append the strategy (Store C, Load A, Load B, Load X, Operations)
                strategy.append(([], a_indices, b_indices, load_X, ops))

            # Finally, store C_ij
            if strategy:
                last_step = strategy[-1]
                last_ops = last_step[4] + imm_alu_on_blocks(alu_operations, c_indices)
                strategy[-1] = (c_indices, last_step[1], last_step[2], last_step[3], last_ops)

    return strategy


# ---------------------------------------------

def strategy_3(nb_A=1, A_blocks_col=1, nb_B=1, B_blocks_col=1, nb_X=1, X_blocks_col=1, nb_C=1, C_blocks_col=1,
               inp_block_buffer_size=4, wgt_block_buffer_size=32, acc_block_buffer_size=4, out_block_buffer_size=4,
               alu_operations=[], idx_to_delete=[]):
    """
    Strategy 3 computes C column-by-column. It loads A column-by-column and single element of B.
    """
    # Define buffer size which is the minimal size of the buffer
    buffer_size = min(inp_block_buffer_size, wgt_block_buffer_size, acc_block_buffer_size, out_block_buffer_size)

    # Init strategy
    strategy = [] # (C, A, B, X)

    # Define C_blocks_row
    C_blocks_row = nb_C//C_blocks_col

    # Define the delta 
    delta = min(buffer_size, C_blocks_row)

    # Define C_blocks_row = nb_delta * delta + remainder
    nb_delta, remainder = euclidian_division(C_blocks_row, delta)

    # Iterate over nb_delta
    for idx_delta in range(0, nb_delta):
        # Iterate over the number of C's columns
        for j in range(0, C_blocks_col):
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
                        load_X.append( i * C_blocks_col + j )
                    
                    # Load A 
                    load_A.append( i * A_blocks_col + k )

                    # Store C on the last iteration
                    if (k==A_blocks_col-1):
                        store_C.append( i * C_blocks_col + j )

                # Get the operations
                ops = get_operations(load_A, load_B, A_blocks_col, B_blocks_col, C_blocks_col) \
                    + imm_alu_on_blocks(alu_operations, store_C)

                # Append the strategy (C, A, B, X, Operations)
                strategy.append( (store_C, load_A, load_B, load_X, ops) )
            
    # Load the remainding C elements on the row
    if (remainder > 0):
        # Iterate over the number of C's columns
        for j in range(0, C_blocks_col):
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
                        load_X.append( i * C_blocks_col + j )
                    
                    # Load A 
                    load_A.append( i * A_blocks_col + k )

                    # Store C on the last iteration
                    if (k==A_blocks_col-1):
                        store_C.append( i * C_blocks_col + j )
                
                # Get the operations
                ops = get_operations(load_A, load_B, A_blocks_col, B_blocks_col, C_blocks_col) \
                    + imm_alu_on_blocks(alu_operations, store_C)

                # Append the strategy (C, A, B, X, Operations)
                strategy.append( (store_C, load_A, load_B, load_X, ops) )
  
    # Return the strategy
    return strategy

# ---------------------------------------------

def strategy_4(nb_A=1, A_blocks_col=1, nb_B=1, B_blocks_col=1, nb_X=1, X_blocks_col=1, nb_C=1, C_blocks_col=1,
               inp_block_buffer_size=4, wgt_block_buffer_size=32, acc_block_buffer_size=4, out_block_buffer_size=4,
               alu_operations=[], idx_to_delete=[]):
    """
    Strategy 4 computes C row-by-row. It loads single element of A and B row-by-row.
    """
    # Define buffer size which is the minimal size of the buffer
    buffer_size = min(inp_block_buffer_size, wgt_block_buffer_size, acc_block_buffer_size, out_block_buffer_size)

    # Init strategy
    strategy = [] # (C, A, B, X)

    # Define the delta 
    delta = min(buffer_size, C_blocks_col)

    # Define C_blocks_col = nb_delta * delta + remainder
    nb_delta, remainder = euclidian_division(C_blocks_col, delta)

    # Iterate over the rows of C
    for i in range(0, nb_C//C_blocks_col):
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
                        load_X.append( i * C_blocks_col + j )
                    
                    # Load B (B_blocks_col = C_blocks_col)
                    load_B.append( k * B_blocks_col + j )

                    # Store C on the last iteration
                    if (k==A_blocks_col-1):
                        store_C.append( i * C_blocks_col + j )
                
                # Get the operations
                ops = get_operations(load_A, load_B, A_blocks_col, B_blocks_col, C_blocks_col) \
                    + imm_alu_on_blocks(alu_operations, store_C)

                # Append the strategy (C, A, B, X, Operations)
                strategy.append( (store_C, load_A, load_B, load_X, ops) )
            
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
                        load_X.append( i * C_blocks_col + j )
                    
                    # Load B (B_blocks_col = C_blocks_col)
                    load_B.append( k * B_blocks_col + j )

                    # Store C on the last iteration
                    if (k==A_blocks_col-1):
                        store_C.append( i * C_blocks_col + j )
                
                # Get the operations
                ops = get_operations(load_A, load_B, A_blocks_col, B_blocks_col, C_blocks_col) \
                    + imm_alu_on_blocks(alu_operations, store_C)

                # Append the strategy (C, A, B, X, Operations)
                strategy.append( (store_C, load_A, load_B, load_X, ops) )
  
    # Return the strategy
    return strategy

# ---------------------------------------------

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

def get_operations(load_A, load_B, A_blocks_col, B_blocks_col, C_blocks_col):
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
                c_idx = i * C_blocks_col + j
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

if __name__ == "__main__": 
    strategy_selector = 2
    A_blocks_col = 10
    nb_A = A_blocks_col*7 
    B_blocks_col = 4 
    nb_B = B_blocks_col*A_blocks_col
    C_blocks_col = B_blocks_col 
    nb_C = C_blocks_col*(nb_A//A_blocks_col) 
    inp_block_buffer_size=4
    wgt_block_buffer_size=inp_block_buffer_size
    out_block_buffer_size=wgt_block_buffer_size

    nb_X = nb_C
    X_blocks_col = C_blocks_col
    acc_block_buffer_size=out_block_buffer_size

    alu_operations = [
        ["ADD_IMM", [0, 1], [(i, 0) for i in range(0, C_blocks_col)]],
        ["MIN", [[0,1], [3,1], 3], [((0, 0), (0, 3)), ((1, 0), (1, 3)), ((2, 0), (2, 3)), ((3, 0), (3, 3)), ((0, 1), (0, 4)), ((1, 1), (1, 4)), ((2, 1), (2, 4)), ((3, 1), (3, 4)), ((0, 2), (0, 5)), ((1, 2), (1, 5)), ((2, 2), (2, 5)), ((3, 2), (3, 5))]]
    ]


    matrix_partitioning(nb_A, A_blocks_col, nb_B, B_blocks_col, nb_X, X_blocks_col, nb_C, C_blocks_col, inp_block_buffer_size, wgt_block_buffer_size, acc_block_buffer_size, out_block_buffer_size, alu_operations, [], strategy_selector, debug=True)
