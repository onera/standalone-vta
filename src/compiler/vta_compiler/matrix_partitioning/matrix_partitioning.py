# IMPORT PACKAGES
# ---------------
import numpy as np


###############################################


# Matrix partitioning
# -------------------
def matrix_partitioning(nb_A=1, A_blocks_col=1, nb_B=1, B_blocks_col=1, nb_X=1, X_blocks_col=1, nb_C=1, C_blocks_col=1,
                        inp_block_buffer_size=4, wgt_block_buffer_size=32, acc_block_buffer_size=4, out_block_buffer_size=4,
                        strategy_selector=1, debug=True):
    # Check strategy assumptions
    if not ( (inp_block_buffer_size == min(inp_block_buffer_size, wgt_block_buffer_size, out_block_buffer_size)) 
           and (acc_block_buffer_size == out_block_buffer_size) 
           and (nb_X == nb_C) and (X_blocks_col == C_blocks_col) ):
        raise Exception(f"ERROR: Assumptions for matrix partitioning: \
                        \n\t 1. acc_block_buffer_size ({acc_block_buffer_size}) = out_block_buffer_size ({out_block_buffer_size}); \
                        \n\t 2. inp_block_buffer_size ({inp_block_buffer_size}) is smaller (or equal) than wgt_block_buffer_size ({wgt_block_buffer_size}), out_block_buffer_size ({out_block_buffer_size}); \
                        \n\t 3. nb_X ({nb_X}) = nb_C ({nb_C}) and X_blocks_col ({X_blocks_col}) = C_blocks_col ({C_blocks_col})! \n\n")
    # Check data consistency
    if ( (nb_A%A_blocks_col != 0) or (nb_B%B_blocks_col != 0) or (nb_C%C_blocks_col != 0) ):
        raise Exception(f"ERROR: Data are not consistent: results should be 0 \
                        \n\t nb_A%A_blocks_col = {nb_A%A_blocks_col} \
                        \n\t nb_B%B_blocks_col = {nb_B%B_blocks_col} \
                        \n\t nb_C%C_blocks_col = {nb_C%C_blocks_col} \n\n")
    if ( (nb_A//A_blocks_col != nb_C//C_blocks_col) or (nb_X != nb_C) ):
        raise Exception(f"ERROR: Data are not consistent: results should be equal: \
                        \n\t nb_A//A_blocks_col ({nb_A//A_blocks_col}) = nb_C//C_blocks_col ({nb_C//C_blocks_col}), \
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
    # Init strategy
    strategy = [] # (C, A, B, X)

    # Check the load capacity of A
    nb_loadable_rows = inp_block_buffer_size//A_blocks_col

    # Iterate over the C rows
    for row in range(0, nb_C//C_blocks_col):

        # Check if one A's row fit input buffer
        if (nb_loadable_rows > 0): 
            A_row_addr = row * A_blocks_col
            load_A = [i+A_row_addr for i in range(0, A_blocks_col)]

            # Load the corresponding B, X and store the C
            for col in range(0, C_blocks_col):
                # Load one B's column (assumption 2.)
                load_B = [i*B_blocks_col + col for i in range(0, A_blocks_col)]
                # Load a single X element
                load_X = [col+row*C_blocks_col]
                # Store a single C element
                store_C = [col+row*C_blocks_col]

                # Append the strategy (C, A, B, X)
                if (col == 0):
                    strategy.append( (store_C, load_A, load_B, load_X) )
                else: 
                    strategy.append( (store_C, [], load_B, load_X) )

        else: # Cannot load one A's row
            # Compute the number of inp_block_buffer_size within A_blocks_col
            nb_load_per_row = A_blocks_col//inp_block_buffer_size

            # Iterate over C column
            for col in range(0, C_blocks_col):
                # Define the C and X elements to use
                store_C = [col+row*C_blocks_col]
                load_X = [col+row*C_blocks_col]

                # Get A and B elements
                for elem in range(0, nb_load_per_row):
                    # Compute the initial index of A elements
                    local_A_load = ((row*C_blocks_col)//C_blocks_col)*A_blocks_col + elem*inp_block_buffer_size
                    local_B_load = (local_A_load*B_blocks_col)%nb_B

                    # Load A
                    load_A = [i+local_A_load for i in range(0, inp_block_buffer_size)]
                    # Load B
                    load_B = [(i*B_blocks_col + col) + local_B_load for i in range(0, inp_block_buffer_size)]

                    # Append the strategy (C, A, B, X)
                    if (elem == 0):
                        strategy.append( ([], load_A, load_B, load_X) )
                    else: 
                        strategy.append( ([], load_A, load_B, []) )
                
                # Compute the rest to load to complete the A's row
                rest_to_load = A_blocks_col%inp_block_buffer_size
                if (rest_to_load>0):
                    # Compute local load indexes
                    local_A_load = local_A_load + inp_block_buffer_size
                    local_B_load = (local_A_load*B_blocks_col)%nb_B

                    # Load A and B
                    load_A = [i+local_A_load for i in range(0, rest_to_load)]
                    load_B = [(i*B_blocks_col + col) + local_B_load for i in range(0, rest_to_load)]
                    # Append the strategy
                    strategy.append( (store_C, load_A, load_B, []) )

                else: # Update the last element of the list to add store
                    strategy[-1] = (store_C, load_A, load_B, [])


    # Return the strategy
    return strategy


# ---------------------------------------------

if __name__ == "__main__": 
    strategy_selector = 1 # 1,
    nb_A = 70 # 70,
    A_blocks_col = 10 # 10,
    nb_B = 10 # 10, 40
    B_blocks_col = 1 # 1, 4
    nb_C = 7 # 7, 28
    C_blocks_col = 1 # 1, 4
    inp_block_buffer_size=400 # 4,
    wgt_block_buffer_size=400 # 4,
    out_block_buffer_size=400 # 4,

    nb_X = nb_C
    X_blocks_col = C_blocks_col
    acc_block_buffer_size=out_block_buffer_size


    matrix_partitioning(nb_A, A_blocks_col, nb_B, B_blocks_col, nb_X, X_blocks_col, nb_C, C_blocks_col, inp_block_buffer_size, wgt_block_buffer_size, acc_block_buffer_size, out_block_buffer_size, strategy_selector, debug=True)
