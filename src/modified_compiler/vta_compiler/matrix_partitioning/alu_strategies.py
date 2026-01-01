# IMPORT PACKAGES
# ---------------
import numpy as np

from matrix_partitioning.utils_strategies import *

###############################################

# ALU Strategy Generation
# -----------------------
def alu_strategy(sorted_alu_ops, acc_buffer_size, idx_to_store):
    """
    Generates a loading and execution strategy for ALU operations based on a limited buffer size.
    This version enforces a strict sequential execution order for operations targeting the same destination.

    Inputs:
        - sorted_alu_ops (list): A list of ALU operations, pre-sorted by destination vector.
        - acc_buffer_size (int): The number of vectors that fit the accumulator SRAM buffer.

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
    # Init the strategy [([], [], [Xi], [SRAM], [DRAM], [Ci], [Ops])]
    strategy = []
    load_X = []
    sram_status = []
    # dram_status = []
    dram_status = idx_to_store # To filter
    store_C = []
    ops = []

    if (acc_buffer_size < 2):
        raise Exception(f"ERROR: The capacity of the buffer is {acc_buffer_size} but it must be at least 2 (to load a DST vector and a SRC vector)! \n\n")

    # Nb of ALU operations
    nb_alu = len(sorted_alu_ops)
    
    # Iterate over all the alu_operations, each ALU contains a single DST vector
    for alu_idx, alu_ops in enumerate(sorted_alu_ops):
        # Get the DST and SRC vectors
        dst_vector, src_vectors = get_dst_src_vectors(alu_ops=alu_ops)

        # Append ops
        ops.append(alu_ops)

        # Check if the DST_vector is in SRAM
        if (not dst_vector in sram_status):
            # Load the DST vector 
            load_X.append(dst_vector)
            sram_status.append(dst_vector)
        if (not dst_vector in store_C):
            store_C.append(dst_vector)

        # Iterate over the SRC vectors

        for src_idx, src_vector in enumerate(src_vectors):
            if (len(sram_status) >= acc_buffer_size):
                # Filter the ops
                filtered_ops = filter_op_for_step(alu_ops=ops, sram_status=sram_status)
                # Append the strategy [([], [], [Xi], [SRAM], [DRAM], [Ci], [Ops])]
                strategy.append( ([], [], load_X, sram_status, dram_status, [], filtered_ops) )

                # Reset the lists (SRAM maintains DST vector)
                load_X = []
                # load_X = store_C.copy()
                sram_status = store_C.copy()

            # Update load and SRAM
            load_X.append(src_vector)
            sram_status.append(src_vector)

        # Check if it is the last ALU
        if (alu_idx < nb_alu - 1):
            # Check if the next ALU uses the same DST vector
            next_dst, next_src = get_dst_src_vectors(sorted_alu_ops[alu_idx+1])

            # Check if the next ALU is a vector-scalar operation
            if (sorted_alu_ops[alu_idx+1][0].endswith("_IMM") or sorted_alu_ops[alu_idx+1][0] == "RELU"):
                if (next_dst in sram_status):
                    continue
            
            # Vector-vector operation
            else: 
                # Check the size of the next ALU_ops
                if ( (next_dst in sram_status) and (len(next_src)+len(sram_status) < acc_buffer_size - 1) ):
                    # If the next ALU fit the buffer, continue the step
                    continue
                elif (len(next_src)+len(sram_status) < acc_buffer_size - 1):
                    # If the next ALU fit the buffer, continue the step
                    continue

                # If it the same DST vector but it does not fit, finalise the step but do not store
                elif (next_dst in sram_status):
                    # Filter the ops
                    filtered_ops = filter_op_for_step(alu_ops=ops, sram_status=sram_status)
                    # Append the strategy [([], [], [Xi], [SRAM], [DRAM], [Ci], [Ops])]
                    strategy.append( ([], [], load_X, sram_status, dram_status, [], filtered_ops) )
                    # Reset
                    load_X = []
                    sram_status = store_C.copy()
                    ops = []
                    continue


        # Else, finalise the step

        # Update the DRAM
        # dram_status = dram_status + store_C
        # Filter the ops
        filtered_ops = filter_op_for_step(alu_ops=ops, sram_status=sram_status)
        # Append the strategy [([], [], [Xi], [SRAM], [DRAM], [Ci], [Ops])]
        strategy.append( ([], [], load_X, sram_status, dram_status, store_C, filtered_ops) )

        # Reset the lists
        load_X = []
        sram_status = []
        store_C = []
        ops = []

    # Return the strategy
    return strategy

