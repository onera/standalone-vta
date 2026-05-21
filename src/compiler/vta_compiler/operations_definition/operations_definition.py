# IMPORT PACKAGES
# ---------------
if __name__ == "__main__": 
    from structures import *
    from instructions_generator import *
else:
    from operations_definition.structures import *
    from operations_definition.instructions_generator import *


###############################################


# OPERATIONS DEFINITION
# ---------------------
def operations_definition(strategy=[], dram_addresses=[],
                          operations_dict={}, flag_dict={},
                          block_size=16, uop_buffer_size=8192,
                          A_blocks_col=1, B_blocks_col=1, C_blocks_col=1,
                          debug=True):
    # Init the lists of instructions, UOPs and semaphore
    insn_buffer = []
    uop_buffer = []
    memory_status = []
    uop_counter = 0

    # Create a semaphore dictionnary
    semaphore = {
        "LD->CMP": 0,
        "CMP->ST": 0,
        "ST->CMP": 0,
        "CMP->LD": 0
    }

    # # # Dump instructions
    # # new_insn, new_buffer, semaphore = dump_instructions(nb_insn=10000, semaphore=semaphore) 
    # # insn_buffer.extend(new_insn)
    # # uop_buffer.extend(new_buffer)

    # 0 - Reset 
    new_insn, new_buffer, semaphore, uop_counter = reset_sequence(strategy, semaphore, dram_addresses, uop_counter, block_size)
    # Extend the buffers
    insn_buffer.extend(new_insn)
    uop_buffer.extend(new_buffer)

    # 1 - strategy step 
    for i, step in enumerate(strategy):
        # Get the status of the SRAM memory
        memory_status = step[3]
        # Create the instructions for each step
        new_insn, new_buffer, semaphore, uop_counter = core_instructions(step, semaphore, flag_dict, dram_addresses, uop_counter, block_size, C_blocks_col, uop_buffer_size)
        # Extend the buffers
        insn_buffer.extend(new_insn)
        uop_buffer.extend(new_buffer)


    # 2 - Termination sequence 
    new_insn, semaphore = termination_sequence(semaphore) 
    insn_buffer.extend(new_insn)


    # Debug
    if (debug):
        print("\n\nOPERATIONS DEFINITION:")

        print(f"Instructions: ({len(insn_buffer)})")
        for i, insn in enumerate(insn_buffer):
            print(f"\nI{i}:")
            # Print the hexadecimal value
            _, string_insn = hex_128bit(insn, debug=False)
            # Decode the instructions
            decode_vta_insn(string_insn)
        
        # Print the semaphore
        print(f"\n\nSemaphore: \n\t {semaphore}")

        print(f"\n\nUOPs: ({len(uop_buffer)})")
        for i, uop in enumerate(uop_buffer):
            print(f"\nUOP{i}: dst_idx={uop.dst_idx}, src_idx={uop.src_idx}, wgt_idx={uop.wgt_idx}")

    # Return the instructions and UOPs lists
    return insn_buffer, uop_buffer

# ---------------------------------------------


###############################################
