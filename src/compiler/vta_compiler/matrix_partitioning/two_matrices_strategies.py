# IMPORT PACKAGES
# ---------------
import numpy as np

from matrix_partitioning.utils_strategies import *


###############################################

# TWO_MATRICES_STRATEGY
# ---------------------
def two_matrices_strategy(nb_X, acc_block_buffer_size, alu_operations):
    """
    Generates a loading and execution strategy for 2-matrix ALU-related operations based on a limited buffer size.


    Inputs:
        - nb_X (int): The number of blocks to load for one matrix.
        - acc_block_buffer_size (int): The number of blocks that fit the accumulator SRAM buffer.
        - alu_operations (list): The list of operations to perform

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

    # The actual size of the acc buffer is divided by 2 (2 nb_X blocks to load)
    capacity = acc_block_buffer_size // 2

    if (capacity < 2):
        raise Exception(f"ERROR: The capacity of the buffer is {capacity} but it must be at least 2 (to load two blocks)! \n\n")

    # Create the step
    for i in range(0, nb_X, capacity):
        # The last element to store at this step
        end = min(i + capacity, nb_X)

        # Create the list load_X
        load_X = list( range(i, end) )

        # Append the strategy [([], [], [Xi], [SRAM], [DRAM], [Ci], [Ops])]
        strategy.append( ([], [], load_X, load_X, [], load_X, alu_operations) )


    # Return the strategy
    return strategy