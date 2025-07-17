# IMPORT PACKAGES
# ---------------
import numpy as np
import collections
import pprint


###############################################


# Matrix partitioning
# -------------------
def matrix_partitioning(nb_A=1, A_blocks_col=1, nb_B=1, B_blocks_col=1, nb_X=1, X_blocks_col=1, nb_C=1, C_blocks_col=1,
                        inp_block_buffer_size=4, wgt_block_buffer_size=32, acc_block_buffer_size=4, out_block_buffer_size=4,
                        alu_operations=[], idx_to_store=[],
                        strategy_selector=1, block_size=16,
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
        - strategy_selector (int): an integer in [1..4] to select a strategy on GeMM
        - block_size (int): an integer coming from the VTA configuration
        - debug (boolean): a boolean to print the execution information
    Outputs:
        - isOverfitting (boolean): it is true if at least one matrix overfits the SRAM (i.e., a strategy is applied)
        - strategy (list of tuple): each tuple represents a computation step. 
            The tuple is composed of several lists: ([Ai], [Bi], [Xi], [Mi], [Ti], [Ci], [Operations]). 
            Each list correspond to a specific action to perform at this step: 
                1. [Ai]: The A input elements to load (int: block index / tuple: block idx, vector)
                2. [Bi]: The B weight elements to load
                3. [Xi]: The X accumulator elemments to load
                4. [Mi]: The current elements within the SRAM ACC buffer
                5. [Ti]: TO REMOVE
                6. [Ci]: The C output elements to store in OUT region within DRAM
                7. [Operations]: The operations to perform at each step
    
     Remarks: three case are supported:
        - CASE 1: Matrix multiplication (GeMM) without overfitting followed by ALU operations (either vector-scalar or vector-vector)
        - CASE 2: Matrix multiplication (GeMM) with overfitting followed by vector-scalar operations
        - CASE 3: ALU operations
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
    
    # Init the output
    isOverfitting = False
    strategy = []

    # CASE 1 & 2: MATRIX MULTIPLICATION
    if (nb_A != 0 and nb_B != 0):
        # Additional data consistency verification
        if ( (nb_A//A_blocks_col != nb_C//C_blocks_col) or (B_blocks_col != C_blocks_col) or (nb_X != nb_C) ):
            raise Exception(f"ERROR: Data are not consistent: results should be equal: \
                            \n\t nb_A//A_blocks_col ({nb_A//A_blocks_col}) = nb_C//C_blocks_col ({nb_C//C_blocks_col}), \
                            \n\t B_blocks_col ({B_blocks_col}) = C_blocks_col ({C_blocks_col}), \
                            \n\t nb_X ({nb_X}) = nb_C ({nb_C})!\n\n")
        
        # CASE 1: NO OVERFITTING
        if ((nb_A < inp_block_buffer_size) and (nb_B < wgt_block_buffer_size) and (nb_C < out_block_buffer_size)):
            isOverfitting = False
            
            # Load all the blocks ([Ai], [Bi], [Xi], [Mi], [Ti], [Ci], [Operations])
            load_A = [i for i in range(0, nb_A)]
            load_B = [i for i in range(0, nb_B)]
            load_X = [i for i in range(0, nb_X)]
            memory_status = load_X
            dram_state = [] # TODO: not used
            store_C = load_X

            # Get the GEMM operations
            ops = get_operations(load_A, load_B, A_blocks_col, B_blocks_col, C_blocks_col)

            # Add ALU operations
            ops = ops + alu_operations

            # Create the strategy [([Ai], [Bi], [Xi], [Mi], [Ti], [Ci], [Operations])]
            strategy = [ (load_A, load_B, load_X, memory_status, dram_state, store_C, ops) ]

        # CASE 2: OVERFITTING
        else: # ((nb_A > inp_block_buffer_size) or (nb_B > wgt_block_buffer_size) or (nb_C > out_block_buffer_size))
            isOverfitting = False

            # Check if the operations in alu_operations are only vector-scalar
            for alu_ops in alu_operations:
                if (alu_ops[0] != "RELU" and not alu_ops[0].endswith("_IMM")):
                    raise Exception(f"ERROR: {alu_ops[0]} is not supported when there is an overfitting GeMM operations!\n\n")
            
            # Gather the parameters (common parameters for all strategies) within a dictionnary and execute the strategy
            params = {
                'nb_A': nb_A, 'A_blocks_col': A_blocks_col,
                'nb_B': nb_B, 'B_blocks_col': B_blocks_col,
                'nb_X': nb_X, 'X_blocks_col': X_blocks_col,
                'nb_C': nb_C, 'C_blocks_col': C_blocks_col,
                'inp_block_buffer_size': inp_block_buffer_size,
                'wgt_block_buffer_size': wgt_block_buffer_size,
                'acc_block_buffer_size': acc_block_buffer_size,
                'out_block_buffer_size': out_block_buffer_size,
                'alu_operations': alu_operations
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
    

    # CASE 3: ALU OPERATIONS
    else:
        # Check if it fits
        if (nb_X < acc_block_buffer_size):
            isOverfitting = False
            
            # Load all the blocks ([Ai], [Bi], [Xi], [Mi], [Ti], [Ci], [Operations])
            load_A = []
            load_B = []
            load_X = [i for i in range(0, nb_X)]
            memory_status = load_X
            dram_state = idx_to_store
            store_C = dram_state

            # Create the strategy [([Ai], [Bi], [Xi], [Mi], [Ti], [Ci], [Operations])]
            strategy = [ (load_A, load_B, load_X, memory_status, dram_state, store_C, alu_operations) ]

        # It does not fit
        else:
            isOverfitting = True

            # Sort the alu_operations
            sorted_alu_operations = sort_alu_by_dst(alu_operations)

            # Define the strategy
            strategy = alu_strategy(sorted_alu_ops=sorted_alu_operations, acc_block_buffer_size=acc_block_buffer_size)

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
        print(f"\nStrategy [([Ai], [Bi], [Xi], [Mi], [Ti], [Ci], [Operations])]: (nb of steps: {len(strategy)})")
        for i, step in enumerate(strategy):
            print(f"\nStep {i}: {step}")

    # Return if it is overfitting and the strategy [([Ai], [Bi], [Xi], [Mi], [Ti], [Ci], [Operations])]
    return isOverfitting, strategy


###############################################


def strategy_1(nb_A=1, A_blocks_col=1, nb_B=1, B_blocks_col=1, nb_X=1, X_blocks_col=1, nb_C=1, C_blocks_col=1,
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
    for idx in range(0, nb_C):
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
            ops = get_operations(load_A, load_B, A_blocks_col, B_blocks_col, C_blocks_col)
            
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
            ops = get_operations(load_A, load_B, A_blocks_col, B_blocks_col, C_blocks_col) \
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

def strategy_2(nb_A=1, A_blocks_col=1, nb_B=1, B_blocks_col=1, nb_X=1, X_blocks_col=1, nb_C=1, C_blocks_col=1,
               inp_block_buffer_size=4, wgt_block_buffer_size=32, acc_block_buffer_size=4, out_block_buffer_size=4,
               alu_operations=[]):
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
                
                # Append the strategy [([Ai], [Bi], [Xi], [Mi], [Ti], [Ci], [Operations])]
                strategy.append((a_indices, b_indices, load_X, x_indices, [], [], ops))

            # Finally, store C_ij
            if strategy:
                last_step = strategy[-1]
                last_ops = last_step[6] + imm_alu_on_blocks(alu_operations, c_indices)
                strategy[-1] = (last_step[0], last_step[1], last_step[2], last_step[3], [], c_indices, last_ops)

    return strategy


# ---------------------------------------------

def strategy_3(nb_A=1, A_blocks_col=1, nb_B=1, B_blocks_col=1, nb_X=1, X_blocks_col=1, nb_C=1, C_blocks_col=1,
               inp_block_buffer_size=4, wgt_block_buffer_size=32, acc_block_buffer_size=4, out_block_buffer_size=4,
               alu_operations=[]):
    """
    Strategy 3 computes C column-by-column. It loads A column-by-column and single element of B.
    """
    # Define buffer size which is the minimal size of the buffer
    buffer_size = min(inp_block_buffer_size, wgt_block_buffer_size, acc_block_buffer_size, out_block_buffer_size)

    # Init strategy
    strategy = [] # [([Ai], [Bi], [Xi], [Mi], [Ti], [Ci], [Operations])]

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
                    memory_status = load_X if (len(load_X) > 0) else memory_status
                    
                    # Load A 
                    load_A.append( i * A_blocks_col + k )

                    # Store C on the last iteration
                    if (k==A_blocks_col-1):
                        store_C.append( i * C_blocks_col + j )

                # Get the operations
                ops = get_operations(load_A, load_B, A_blocks_col, B_blocks_col, C_blocks_col) \
                    + imm_alu_on_blocks(alu_operations, store_C)

                # Append the strategy [([Ai], [Bi], [Xi], [Mi], [Ti], [Ci], [Operations])]
                strategy.append( (load_A, load_B, load_X, memory_status, [], store_C, ops) )
            
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
                    memory_status = load_X if (len(load_X) > 0) else memory_status
                    
                    # Load A 
                    load_A.append( i * A_blocks_col + k )

                    # Store C on the last iteration
                    if (k==A_blocks_col-1):
                        store_C.append( i * C_blocks_col + j )
                
                # Get the operations
                ops = get_operations(load_A, load_B, A_blocks_col, B_blocks_col, C_blocks_col) \
                    + imm_alu_on_blocks(alu_operations, store_C)

                # Append the strategy [([Ai], [Bi], [Xi], [Mi], [Ti], [Ci], [Operations])]
                strategy.append( (load_A, load_B, load_X, memory_status, [], store_C, ops) )
  
    # Return the strategy
    return strategy

# ---------------------------------------------

def strategy_4(nb_A=1, A_blocks_col=1, nb_B=1, B_blocks_col=1, nb_X=1, X_blocks_col=1, nb_C=1, C_blocks_col=1,
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
                    memory_status = load_X if (len(load_X) > 0) else memory_status
                    
                    # Load B (B_blocks_col = C_blocks_col)
                    load_B.append( k * B_blocks_col + j )

                    # Store C on the last iteration
                    if (k==A_blocks_col-1):
                        store_C.append( i * C_blocks_col + j )
                
                # Get the operations
                ops = get_operations(load_A, load_B, A_blocks_col, B_blocks_col, C_blocks_col) \
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
                        load_X.append( i * C_blocks_col + j )
                    memory_status = load_X if (len(load_X) > 0) else memory_status
                    
                    # Load B (B_blocks_col = C_blocks_col)
                    load_B.append( k * B_blocks_col + j )

                    # Store C on the last iteration
                    if (k==A_blocks_col-1):
                        store_C.append( i * C_blocks_col + j )
                
                # Get the operations
                ops = get_operations(load_A, load_B, A_blocks_col, B_blocks_col, C_blocks_col) \
                    + imm_alu_on_blocks(alu_operations, store_C)

                # Append the strategy [([Ai], [Bi], [Xi], [Mi], [Ti], [Ci], [Operations])]
                strategy.append( (load_A, load_B, load_X, memory_status, [], store_C, ops) )
  
    # Return the strategy
    return strategy


###############################################


# ALU Strategy Generation
# -----------------------
# TODO: bug - do not support OP overfitting followed by IMM
def alu_strategy(sorted_alu_ops, acc_block_buffer_size):
    """
    Generates a loading and execution strategy for ALU operations based on a limited buffer size.
    This version enforces a strict sequential execution order for operations targeting the same destination.

    Inputs:
        - sorted_alu_ops (list): A list of ALU operations, pre-sorted by destination vector.
        - acc_block_buffer_size (int): The number of blocks that fit the accumulator SRAM buffer.

    Outputs:
        - strategy (list of tuple): Each tuple represents a computation step.
          The tuple is composed of several lists: ([Ai], [Bi], [Xi], [Mi], [Ti], [Ci], [Operations]).
            1. [Ai]: The A input elements to load (empty for ALU).
            2. [Bi]: The B weight elements to load (empty for ALU).
            3. [Xi]: The X accumulator elements to load for this step.
            4. [Mi]: The current elements within the SRAM ACC buffer (memory status).
            5. [Ti]: The elements that have been computed and stored back to DRAM so far.
            6. [Ci]: The C output elements to store in DRAM in this step.
            7. [Operations]: The ALU operations to perform in this step.
    """
    if acc_block_buffer_size <= 0:
        raise ValueError("Buffer size must be strictly positive.")

    # Step 1: Group operations by destination vector
    grouped_ops = collections.OrderedDict()
    for op in sorted_alu_ops:
        dst, srcs = parse_alu_op(op)
        if dst not in grouped_ops:
            grouped_ops[dst] = {'ops': [], 'all_srcs': set()}
        grouped_ops[dst]['ops'].append(op)
        grouped_ops[dst]['all_srcs'].update(srcs)

    strategy = []
    buffer = set()
    saved_dsts = set()  # Tracks destinations that have been fully computed and saved

    # Step 2: Iterate through all operations to build the strategy
    for op in sorted_alu_ops:
        dst, _ = parse_alu_op(op)
        # If this destination has already been processed and saved, skip it
        if dst in saved_dsts:
            continue

        # Get all operations and sources for the current destination
        data = grouped_ops[dst]
        all_ops_for_dst = data['ops']
        all_srcs_for_dst = data['all_srcs']
        
        if acc_block_buffer_size < 1:
            raise ValueError("Buffer size must be at least 1.")

        # This list will track pending operations for the destination
        pending_ops_for_dst = list(all_ops_for_dst)

        # Ensure the destination vector is prioritized but clear other unnecessary items from buffer
        buffer.intersection_update({dst})
        vectors_to_load = sorted(list(all_srcs_for_dst - buffer))
        if dst not in buffer:
            vectors_to_load.insert(0, dst)

        # Step 3: Load vectors in chunks and execute operations
        i = 0
        while i < len(vectors_to_load):
            free_slots = acc_block_buffer_size - len(buffer)
            # If buffer is full, evict non-essential vectors
            if free_slots <= 0:
                eviction_candidates = buffer - {dst}
                if not eviction_candidates:
                    raise RuntimeError(f"Logic Error: Buffer is full for dst={dst} with nothing to evict.")
                buffer.difference_update(eviction_candidates)
                free_slots = acc_block_buffer_size - len(buffer)

            # Load the next chunk of vectors
            chunk_to_load = vectors_to_load[i : i + free_slots]
            buffer.update(chunk_to_load)
            i += len(chunk_to_load)

            ops_for_this_step = []
            
            # --- Sequential Processing Logic ---
            # Process pending operations as long as progress can be made.
            while pending_ops_for_dst:
                # Always check the *first* operation in the pending queue.
                op_to_check = pending_ops_for_dst[0]
                
                filtered_op = filter_op_for_step(op_to_check, buffer)
                
                if not filtered_op:
                    # The head-of-line operation is not yet executable.
                    # Cannot proceed further for this destination in this step.
                    break
                
                # The operation is executable, add it to the current step.
                ops_for_this_step.append(filtered_op)
                
                # Check if the op is fully completed with the current buffer state.
                _, original_srcs = parse_alu_op(op_to_check)
                if all(src in buffer for src in original_srcs):
                    # Yes, it's complete. Remove it from the pending queue.
                    pending_ops_for_dst.pop(0)
                    # Continue to see if the *new* head-of-line op is also executable.
                    continue
                else:
                    # No, it's only partially executed. We cannot start the next one.
                    break
            
            # Check if this is the final load for the current destination group
            is_final_step_for_dst = (i >= len(vectors_to_load))
            to_save_this_step = [dst] if is_final_step_for_dst else []
            if is_final_step_for_dst:
                saved_dsts.add(dst)

            # Create the strategy step tuple: ([Ai], [Bi], [Xi], [Mi], [Ti], [Ci], [Ops])
            step = ([], [], sorted(chunk_to_load), sorted(list(buffer)), sorted(list(saved_dsts)), to_save_this_step, ops_for_this_step)
            
            # Only add a step if it involves loading or executing operations
            if chunk_to_load or ops_for_this_step:
                strategy.append(step)
            
    return strategy


###############################################

# ALU Operation Parsing
# ---------------------

def parse_alu_op(alu_op):
    """
    Parses an ALU operation to extract its destination and source vectors.

    Inputs:
        - alu_op (list): A list representing a single ALU operation.
          Format: [op_name, params, tuples_list]

    Outputs:
        - dst_vector (tuple or int): The destination vector index.
        - src_vectors (list): A list of source vector indices.
    """
    op_name, params, tuples_list = alu_op
    first_element = tuples_list[0]

    # Check the format of the tuple to distinguish destination and sources
    if isinstance(first_element[0], int):
        # Format: (dst, ...) for scalar ops or ops with immediate values
        dst_vector = first_element
        src_vectors = []
    else:
        # Format: ((dst), [src1, src2, ...]) for vector-vector operations
        dst_vector = first_element[0]
        src_vectors = first_element[1]

    return dst_vector, src_vectors

# ---------------------------------------------

def filter_op_for_step(alu_op, buffer_set):
    """
    Filters an ALU operation based on the current buffer content to determine
    if it can be partially or fully executed in the current step.

    Inputs:
        - alu_op (list): The ALU operation to check.
        - buffer_set (set): A set of vector indices currently in the buffer.

    Outputs:
        - (list or None): A new operation list for the current step if executable,
          otherwise None.
    """
    op_name, params, tuples_list = alu_op
    dst_vector, src_vectors = parse_alu_op(alu_op)

    # The destination must be in the buffer to perform the operation
    if dst_vector not in buffer_set:
        return None

    # For operations without source vectors (e.g., with immediate values)
    if not src_vectors:
        return [op_name, params, [(dst_vector)]]

    # Filter source vectors that are currently in the buffer
    filtered_srcs = [src for src in src_vectors if src in buffer_set]
    return [op_name, params, [((dst_vector), filtered_srcs)]]


###############################################


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


###############################################

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
