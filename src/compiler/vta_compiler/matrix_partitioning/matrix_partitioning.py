# IMPORT PACKAGES
# ---------------
import numpy as np

import matrix_partitioning.gemm_strategies as GS
import matrix_partitioning.alu_strategies as AS
import matrix_partitioning.two_matrices_strategies as TS

from matrix_partitioning.utils_strategies import *


###############################################


# Matrix partitioning
# -------------------
def matrix_partitioning(nb_A=1, A_blocks_col=1, nb_B=1, B_blocks_col=1, nb_X=1, X_blocks_col=1,
                        inp_buffer_size=4*256, wgt_buffer_size=32*16, acc_buffer_size=4*256, out_buffer_size=4*256,
                        alu_operations=[], idx_to_store=[],
                        doGemm=False, doAddMatrix=False, doAlu=False,
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
        - do* (boolean): perform the specific operations
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
                5. [Ti]: The current elements stored back in the DRAM
                6. [Ci]: The C output elements to store in OUT region within DRAM
                7. [Operations]: The operations to perform at each step
    
     Remarks: the supported cases are:
        - CASE 1: Matrix multiplication (GeMM) without overfitting followed by ALU operations (either vector-scalar or vector-vector)
        - CASE 2: Matrix multiplication (GeMM) with overfitting followed by vector-scalar operations
        - CASE 3: TWO MATRICES OPERATIONS
        - CASE 4: ALU operations
    """
    # Check strategy assumptions
    if not ( (acc_buffer_size == out_buffer_size) ):
        raise Exception(f"ERROR: Assumptions for matrix partitioning: \
                        \n\t 1. acc_buffer_size ({acc_buffer_size}) = out_buffer_size ({out_buffer_size})! \n\n")
    
    # Init the output
    isOverfitting = False
    strategy = []

    # Define the block capacity
    inp_block_buffer_size = int( inp_buffer_size / block_size )
    wgt_block_buffer_size = wgt_buffer_size
    acc_block_buffer_size = int( acc_buffer_size / block_size )
    out_block_buffer_size = acc_block_buffer_size

    # CASE 1 & 2: MATRIX MULTIPLICATION
    if doGemm == True:
        # Check data consistency
        if ( (nb_A%A_blocks_col != 0) or (nb_B%B_blocks_col != 0) or (nb_X%X_blocks_col != 0) ):
            raise Exception(f"ERROR: Data are not consistent: results should be 0 \
                            \n\t nb_A%A_blocks_col = {nb_A%A_blocks_col} \
                            \n\t nb_B%B_blocks_col = {nb_B%B_blocks_col} \
                            \n\t nb_X%X_blocks_col = {nb_X%X_blocks_col} \n\n")
        if ( (nb_A//A_blocks_col != nb_X//X_blocks_col) or (B_blocks_col != X_blocks_col) ):
            raise Exception(f"ERROR: Data are not consistent: results should be equal: \
                            \n\t nb_A//A_blocks_col ({nb_A//A_blocks_col}) = nb_X//X_blocks_col ({nb_X//X_blocks_col}), \
                            \n\t B_blocks_col ({B_blocks_col}) = X_blocks_col ({X_blocks_col})!\n\n")
        
        # CASE 1: NO OVERFITTING
        if ((nb_A < inp_block_buffer_size) and (nb_B < wgt_block_buffer_size) and (nb_X < out_block_buffer_size)):
            isOverfitting = False
            
            # Load all the blocks ([Ai], [Bi], [Xi], [Mi], [Ti], [Ci], [Operations])
            load_A = [i for i in range(0, nb_A)]
            load_B = [i for i in range(0, nb_B)]
            load_X = [i for i in range(0, nb_X)]
            memory_status = load_X
            if (len(idx_to_store) > 0):
                dram_state = idx_to_store
                store_C = idx_to_store
            else:
                dram_state = load_X
                store_C = load_X

            # Get the GEMM operations
            ops = get_operations(load_A, load_B, A_blocks_col, B_blocks_col, X_blocks_col)

            # Add ALU operations
            ops = ops + alu_operations

            # Create the strategy [([Ai], [Bi], [Xi], [Mi], [Ti], [Ci], [Operations])]
            strategy = [ (load_A, load_B, load_X, memory_status, dram_state, store_C, ops) ]

        # CASE 2: OVERFITTING
        else: # ((nb_A > inp_block_buffer_size) or (nb_B > wgt_block_buffer_size) or (nb_X > out_block_buffer_size))
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
                'inp_block_buffer_size': inp_block_buffer_size,
                'wgt_block_buffer_size': wgt_block_buffer_size,
                'acc_block_buffer_size': acc_block_buffer_size,
                'out_block_buffer_size': out_block_buffer_size,
                'alu_operations': alu_operations
            }
            
            # Apply the strategy:
            if (strategy_selector == 1):
                strategy = GS.strategy_1(**params)
            elif (strategy_selector == 2):
                strategy = GS.strategy_2(**params)
            elif (strategy_selector == 3):
                strategy = GS.strategy_3(**params)
            elif (strategy_selector == 4):
                strategy = GS.strategy_4(**params)
            else:
                raise Exception(f"ERROR: Matrix partitioning strategy {strategy_selector} does not exist!\n\n")
    
    # CASE 3: TWO MATRICES OPERATIONS
    elif (doAddMatrix == True):

        # Check if it fits
        if (2*nb_X < acc_block_buffer_size):
            isOverfitting = False
            
            # Load all the blocks ([Ai], [Bi], [Xi], [Mi], [Ti], [Ci], [Operations])
            load_A = []
            load_B = []
            load_X = [i for i in range(0, nb_X)]
            memory_status = load_X
            dram_state = load_X
            store_C = load_X

            # Create the strategy [([Ai], [Bi], [Xi], [Mi], [Ti], [Ci], [Operations])]
            strategy = [ (load_A, load_B, load_X, memory_status, dram_state, store_C, ops) ]

        # It does not fit
        else:
            isOverfitting = True
            pass

    
    # CASE 4: ALU OPERATIONS
    else: # doAlu == True
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
            strategy = AS.alu_strategy(sorted_alu_ops=sorted_alu_operations, acc_buffer_size=acc_buffer_size)


    # Debug
    if (debug):
        print("\n\nMATRIX PARTITIONING:")
        print(f"Number of storable blocks within each SRAM buffer: \
            \n INP: {inp_block_buffer_size} blocks, \
            \n WGT: {wgt_block_buffer_size} blocks, \
            \n ACC=OUT: {out_block_buffer_size} blocks \n")
        print(f"The operations are: ")
        print(f"The operations are:  \
            \n\t doGemm: {doGemm}, \
            \n\t doAddMatrix: {doAddMatrix}, \
            \n doAlu: {doAlu} \n")
        print(f"Number of blocks to load: ")
        if (doGemm):
            print(f" INP: {nb_A} blocks (including A_blocks_col = {A_blocks_col}), \
            \n WGT: {nb_B} blocks (including B_blocks_col = {B_blocks_col}),")
        print(f" ACC=: {nb_X} blocks (including X_blocks_col = {X_blocks_col})\n")

        print(f"\nDoes matrix overfit SRAM? {isOverfitting} \nThe strategy to address it: {strategy_selector}")

        print(f"\nStrategy [([Ai], [Bi], [Xi], [Mi], [Ti], [Ci], [Operations])]: (nb of steps: {len(strategy)})")
        for i, step in enumerate(strategy):
            print(f"\nStep {i}: {step}")

    # Return if it is overfitting and the strategy [([Ai], [Bi], [Xi], [Mi], [Ti], [Ci], [Operations])]
    return isOverfitting, strategy


###############################################

if __name__ == "__main__": 
    strategy_selector = 2
    A_blocks_col = 10
    nb_A = A_blocks_col*7 
    B_blocks_col = 4 
    nb_B = B_blocks_col*A_blocks_col
    X_blocks_col = B_blocks_col 
    nb_X = X_blocks_col*(nb_A//A_blocks_col) 
    inp_block_buffer_size=4
    wgt_block_buffer_size=inp_block_buffer_size
    out_block_buffer_size=wgt_block_buffer_size

    acc_block_buffer_size=out_block_buffer_size

    alu_operations = [
        ["ADD_IMM", [0, 1], [(i, 0) for i in range(0, X_blocks_col)]],
        ["MIN", [[0,1], [3,1], 3], [((0, 0), (0, 3)), ((1, 0), (1, 3)), ((2, 0), (2, 3)), ((3, 0), (3, 3)), ((0, 1), (0, 4)), ((1, 1), (1, 4)), ((2, 1), (2, 4)), ((3, 1), (3, 4)), ((0, 2), (0, 5)), ((1, 2), (1, 5)), ((2, 2), (2, 5)), ((3, 2), (3, 5))]]
    ]


    matrix_partitioning(nb_A, A_blocks_col, nb_B, B_blocks_col, nb_X, X_blocks_col, inp_block_buffer_size, wgt_block_buffer_size, acc_block_buffer_size, out_block_buffer_size, alu_operations, [], strategy_selector, debug=True)
