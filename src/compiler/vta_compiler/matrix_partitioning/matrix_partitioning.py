# IMPORT PACKAGES
# ---------------
import numpy as np


###############################################


# Matrix partitioning
# -------------------
def matrix_partitioning(nb_A=1, A_blocks_col=1, nb_B=1, B_blocks_col=1, nb_X=1, X_blocks_col=1, nb_C=1, C_blocks_col=1,
                        inp_block_buffer_size=4, wgt_block_buffer_size=32, acc_block_buffer_size=4, out_block_buffer_size=4,
                        strategy_selector=1, debug=True):
    """
    The function checks if any matrix (A, B, X, C) is overfitting.
    If yes, it applies the selected strategy. Else, the computation is perform without partitioning.

    Inputs: # represents either matrix A, B, X or C, $ represents either inp, wgt, acc or out.
        - nb_# (int): the number of blocks in the related matrix
        - #_blocks_col (int): the number of blocks to have a matrix row. 
            E.g., nb_A = 6 and A_blocks_col = 2 represents the 3x2-blocks A matrix
        - $_block_buffer_size (int): the number of blocks that fit the related SRAM buffer
        - strategy_selector (int): an integer in [1..4] to select a strategy
        - debug (boolean): a boolean to print the execution information
    Outputs:
        - isOverfitting (boolean): it is true if at least one matrix overfits the SRAM (i.e., a strategy is applied)
        - strategy (list of tuple): each tuple represents a computation step. 
            The tuple is composed of 4 lists: ([Ci], [Ai], [Bi], [Xi]). 
            Each list correspond to a specific action to perform at this step: 1. the C elements to store, 2. the A elements to load, 3. the B elements to load, 4. the X elements to load.
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
        
        # Apply the strategy:
        if (strategy_selector == 1):
            strategy = strategy_1(nb_A, A_blocks_col, nb_B, B_blocks_col, nb_X, X_blocks_col, nb_C, C_blocks_col,
                                  inp_block_buffer_size, wgt_block_buffer_size, acc_block_buffer_size, out_block_buffer_size)
        elif (strategy_selector == 2):
            strategy = strategy_2(nb_A, A_blocks_col, nb_B, B_blocks_col, nb_X, X_blocks_col, nb_C, C_blocks_col,
                                  inp_block_buffer_size, wgt_block_buffer_size, acc_block_buffer_size, out_block_buffer_size)
        elif (strategy_selector == 3):
            strategy = strategy_3(nb_A, A_blocks_col, nb_B, B_blocks_col, nb_X, X_blocks_col, nb_C, C_blocks_col,
                                  inp_block_buffer_size, wgt_block_buffer_size, acc_block_buffer_size, out_block_buffer_size)
        elif (strategy_selector == 4):
            strategy = strategy_4(nb_A, A_blocks_col, nb_B, B_blocks_col, nb_X, X_blocks_col, nb_C, C_blocks_col,
                                  inp_block_buffer_size, wgt_block_buffer_size, acc_block_buffer_size, out_block_buffer_size)
        else:
            raise Exception(f"ERROR: Matrix partitioning strategy {strategy_selector} does not exist!\n\n")
    
    else: # No overfitting
        isOverfitting = False
        strategy = [([i for i in range(0, nb_C)],
                     [i for i in range(0, nb_A)],
                     [i for i in range(0, nb_B)],
                     [i for i in range(0, nb_X)])]
    
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
        print(f"\nStrategy [([C], [A], [B], [X])]: \n")
        i = 0
        for step in strategy:
            print(f"Step {i}: {step}")
            i = i + 1

    # Return if it is overfitting and the strategy [([Ci], [Ai], [Bi], [Xi])]
    return isOverfitting, strategy

# ---------------------------------------------

def strategy_1(nb_A=1, A_blocks_col=1, nb_B=1, B_blocks_col=1, nb_X=1, X_blocks_col=1, nb_C=1, C_blocks_col=1,
               inp_block_buffer_size=4, wgt_block_buffer_size=32, acc_block_buffer_size=4, out_block_buffer_size=4):
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
            
            # Append the strategy (C, A, B, X)
            if (idx_delta == 0): # First: load X
                strategy.append( ([], load_A, load_B, load_X) )
            else: # Then, accumulate
                strategy.append( ([], load_A, load_B, []) )
        
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
            # Append the strategy (C, A, B, X)
            strategy.append( (load_X, load_A, load_B, []) )
        else: # Modify the last step
            strategy[-1] = (load_X, load_A, load_B, [])

    # Return the strategy
    return strategy


# ---------------------------------------------

def strategy_2(nb_A=1, A_blocks_col=1, nb_B=1, B_blocks_col=1, nb_X=1, X_blocks_col=1, nb_C=1, C_blocks_col=1,
               inp_block_buffer_size=4, wgt_block_buffer_size=32, acc_block_buffer_size=4, out_block_buffer_size=4):
    """
    Strategy 2 performs region-based computation, tiling matrices into smaller square regions.
    """
    # --- Assumptions Check ---
    # Assumption 1: The input buffer size must be a perfect square to form a square region.
    if int(np.sqrt(inp_block_buffer_size))**2 != inp_block_buffer_size:
        raise Exception(f"ERROR: Strategy 2 requires inp_block_buffer_size ({inp_block_buffer_size}) to be a perfect square.")
    region_side_size = int(np.sqrt(inp_block_buffer_size))

    # Assumption 2: Matrix dimensions (in blocks) must be a multiple of the region side for perfect tiling.
    A_height_blocks = nb_A // A_blocks_col
    if A_height_blocks % region_side_size != 0:
        raise Exception(f"ERROR: Strategy 2 requires A's height in blocks ({A_height_blocks}) to be a multiple of region_side_size ({region_side_size}).")
    if A_blocks_col % region_side_size != 0:
        raise Exception(f"ERROR: Strategy 2 requires A's width in blocks ({A_blocks_col}) to be a multiple of region_side_size ({region_side_size}).")
    if C_blocks_col % region_side_size != 0:
        raise Exception(f"ERROR: Strategy 2 requires C's width in blocks ({C_blocks_col}) to be a multiple of region_side_size ({region_side_size}).")
    
    # Assumption 3: Weight and Output buffers must be large enough for the regions they need to hold.
    if wgt_block_buffer_size < region_side_size * region_side_size:
         raise Exception(f"ERROR: Strategy 2 requires wgt_block_buffer_size ({wgt_block_buffer_size}) >= {region_side_size*region_side_size}")
    if out_block_buffer_size < region_side_size * region_side_size:
         raise Exception(f"ERROR: Strategy 2 requires out_block_buffer_size ({out_block_buffer_size}) >= {region_side_size*region_side_size}")

    # --- Helper function to get linear indices for a 2D region ---
    def get_region_indices(start_row, start_col, num_rows, num_cols, total_matrix_cols):
        indices = []
        for r_offset in range(num_rows):
            for c_offset in range(num_cols):
                # Block index = (row * total_width) + column
                idx = (start_row + r_offset) * total_matrix_cols + (start_col + c_offset)
                indices.append(idx)
        return indices

    # --- Strategy Implementation ---
    strategy = []
    
    # Iterate over the output C matrix, region by region (C_ij)
    # i = start row of the C region
    for i in range(0, A_height_blocks, region_side_size):
        # j = start column of the C region
        for j in range(0, C_blocks_col, region_side_size):
            
            # Define the C and X regions for the current C_ij computation
            c_region_indices = get_region_indices(i, j, region_side_size, region_side_size, C_blocks_col)
            x_region_indices = c_region_indices # C and X have same dimensions
            
            # Inner loop over the common dimension K, region by region
            # This computes C_ij = sum(A_ik * B_kj) over k
            # k = start of the common dimension for A's columns and B's rows
            for k_step, k in enumerate(range(0, A_blocks_col, region_side_size)):
                
                # Get the region of A to load (A_ik)
                a_region_indices = get_region_indices(i, k, region_side_size, region_side_size, A_blocks_col)
                
                # Get the region of B to load (B_kj)
                b_region_indices = get_region_indices(k, j, region_side_size, region_side_size, B_blocks_col)
                
                # The first step of the K-loop also loads the initial X region
                load_X = x_region_indices if k_step == 0 else []
                
                # Append the compute step: (Store C, Load A, Load B, Load X)
                strategy.append(([], a_region_indices, b_region_indices, load_X))

            # After the K-loop is finished, C_ij is fully computed in the accumulator.
            # Update the last recorded step to add the instruction to store the C region.
            if strategy:
                last_step = strategy[-1]
                strategy[-1] = (c_region_indices, last_step[1], last_step[2], last_step[3])

    return strategy


# ---------------------------------------------

def strategy_3(nb_A=1, A_blocks_col=1, nb_B=1, B_blocks_col=1, nb_X=1, X_blocks_col=1, nb_C=1, C_blocks_col=1,
               inp_block_buffer_size=4, wgt_block_buffer_size=32, acc_block_buffer_size=4, out_block_buffer_size=4):
    """
    Strategy 3 computes C column-by-column. It loads A column-by-column and single element of B.
    """
    # Check strategy assumptions
    if not ( out_block_buffer_size == min(inp_block_buffer_size, wgt_block_buffer_size, out_block_buffer_size) ):
        raise Exception(f"ERROR: Assumptions for matrix partitioning - strategy 3: \
                        \n\t 3. out_block_buffer_size ({out_block_buffer_size}) is smaller (or equal) than inp_block_buffer_size ({inp_block_buffer_size}), wgt_block_buffer_size ({wgt_block_buffer_size})! \n\n")
    if ( nb_C // C_blocks_col > out_block_buffer_size ):
        raise Exception(f"ERROR: Assumptions for matrix partitioning - strategy 3: \
                        \n\t 4. nb_C // C_blocks_col = nb_C_rows ({nb_C // C_blocks_col}) must be smaller (or equal) than out_block_buffer_size ({out_block_buffer_size})! \n\n")

    # Init strategy
    strategy = [] # (C, A, B, X)

    # Calculate the number of rows in C
    nb_C_rows = nb_C // C_blocks_col

    # Check the load capacity of C
    nb_loadable_rows = out_block_buffer_size//nb_C_rows

    # Iterate over each column of C
    for col in range(0, C_blocks_col):
        # Can store a full C's row in OUT buffer
        if (nb_loadable_rows > 0):
            # Store a C's row and load a X's row
            store_C = [i*C_blocks_col + col for i in range(0, nb_C_rows)]
            load_X = [i*C_blocks_col + col for i in range(0, nb_C_rows)]

            # Iterate over the element of A's row
            for col_A in range(0, A_blocks_col):
                # Load A
                load_A = [i*A_blocks_col + col_A for i in range(0, nb_C_rows)]
                # Load B
                load_B = [col + col_A*B_blocks_col]

                # Append the strategy (C, A, B, X)
                if (col_A == 0):
                    strategy.append( ([], load_A, load_B, load_X) )
                else:
                    strategy.append( ([], load_A, load_B, []) )
            
            # Update the last element to store
            strategy[-1] = (store_C, load_A, load_B, [])

        else: # Cannot store a full C's column in OUT buffer
            continue # Not supported yet
    
    # Return the strategy
    return strategy

# ---------------------------------------------

def strategy_4(nb_A=1, A_blocks_col=1, nb_B=1, B_blocks_col=1, nb_X=1, X_blocks_col=1, nb_C=1, C_blocks_col=1,
               inp_block_buffer_size=4, wgt_block_buffer_size=32, acc_block_buffer_size=4, out_block_buffer_size=4):
    """
    Strategy 4 computes C row-by-row. It loads single element of A and B row-by-row.
    """
    # Check strategy assumptions
    if not ( out_block_buffer_size == min(inp_block_buffer_size, wgt_block_buffer_size, out_block_buffer_size) ):
        raise Exception(f"ERROR: Assumptions for matrix partitioning - strategy 4: \
                        \n\t 3. out_block_buffer_size ({out_block_buffer_size}) is smaller (or equal) than inp_block_buffer_size ({inp_block_buffer_size}), wgt_block_buffer_size ({wgt_block_buffer_size})! \n\n")
    if ( C_blocks_col > out_block_buffer_size ):
        raise Exception(f"ERROR: Assumptions for matrix partitioning - strategy 4: \
                        \n\t 4. C_blocks_col ({C_blocks_col}) must be smaller (or equal) than out_block_buffer_size ({out_block_buffer_size})! \n\n")

    # Init strategy
    strategy = [] # (C, A, B, X)

    # Calculate the number of rows in C
    nb_C_rows = nb_C // C_blocks_col

    # Check the load capacity of C
    nb_loadable_col = out_block_buffer_size//C_blocks_col

    # Iterate over each row of C
    for row in range(0, nb_C_rows):
        # Can store a full C's row in OUT buffer
        if (nb_loadable_col > 0):
            # Store a C's row and load a X's row
            store_C = [i + (row*C_blocks_col) for i in range(0, C_blocks_col)]
            load_X = [i + (row*C_blocks_col) for i in range(0, C_blocks_col)]

            # Iterate over the element of A's row
            for col in range(0, A_blocks_col):
                # Load A
                load_A = [col + row*A_blocks_col]
                # Load B
                load_B = [i + (col*B_blocks_col) for i in range(0, B_blocks_col)]

                # Append the strategy (C, A, B, X)
                if (col == 0):
                    strategy.append( ([], load_A, load_B, load_X) )
                else:
                    strategy.append( ([], load_A, load_B, []) )
            
            # Update the last element to store
            strategy[-1] = (store_C, load_A, load_B, [])

        else: # Cannot store a full C's row in OUT buffer
            continue # Not supported yet
  
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

if __name__ == "__main__": 
    strategy_selector = 2 
    A_blocks_col = 10
    nb_A = A_blocks_col*8 
    B_blocks_col = 4 
    nb_B = B_blocks_col*10
    C_blocks_col = B_blocks_col 
    nb_C = C_blocks_col*(nb_A//A_blocks_col) 
    inp_block_buffer_size=4
    wgt_block_buffer_size=4
    out_block_buffer_size=4

    nb_X = nb_C
    X_blocks_col = C_blocks_col
    acc_block_buffer_size=out_block_buffer_size


    matrix_partitioning(nb_A, A_blocks_col, nb_B, B_blocks_col, nb_X, X_blocks_col, nb_C, C_blocks_col, inp_block_buffer_size, wgt_block_buffer_size, acc_block_buffer_size, out_block_buffer_size, strategy_selector, debug=True)
