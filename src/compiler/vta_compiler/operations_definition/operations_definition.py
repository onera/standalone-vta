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
                          A_blocks_col=1, B_blocks_col=1, X_blocks_col=1,
                          debug=True):
    # Init the lists of instructions, UOPs and semaphore
    insn_buffer = []
    uop_buffer = []
    memory_status = []
    uop_counter = 0
    
    semaphore = [0, 0, 0, 1] # (LD->CMP, CMP->ST, ST->CMP, CMP->LD)

    # Number of strategy steps
    nb_steps = len(strategy)

    # 0 - Reset (input: /, output: CMP->LD)
    new_insn, new_buffer, uop_counter = reset_sequence(strategy, dram_addresses, uop_counter, block_size)
    insn_buffer = insn_buffer + new_insn
    uop_buffer = uop_buffer + new_buffer

    # 1 - strategy step (input: CMP->LD, output: CMP->LD)
    for i, step in enumerate(strategy):
        memory_status = step[3]

        new_insn, new_buffer, uop_counter, semaphore = strategy_step(step, dram_addresses, memory_status, uop_counter, semaphore, block_size, uop_buffer_size)
        insn_buffer = insn_buffer + new_insn
        uop_buffer = uop_buffer + new_buffer

    # 2 - Termination sequence (input: CMP->LD, output: /)
    insn_buffer += termination_sequence() 
    semaphore[3] -= 1

 

    # Debug
    if (debug):
        print("\n\nOPERATIONS DEFINITION:")

        print(f"Instructions: ({len(insn_buffer)})")
        for i, insn in enumerate(insn_buffer):
            print(f"\nI{i}:")
            # Print the hexadecimal value
            print_hex_128bit(insn)
            # Print the fields of the instructions
            for field in insn._fields_:
                field_name = field[0]
                field_value = getattr(insn, field_name)
                if (field_name == "opcode"):
                    if (field_value == 0): field_value = f"{getattr(insn, field_name)} - LOAD"
                    elif (field_value == 1): field_value = f"{getattr(insn, field_name)} - STORE"
                    elif (field_value == 2): field_value = f"{getattr(insn, field_name)} - GEMM"
                    elif (field_value == 3): field_value = f"{getattr(insn, field_name)} - FINISH"
                    elif (field_value == 4): field_value = f"{getattr(insn, field_name)} - ALU"
                elif (field_name == "buffer_id"):
                    if (field_value == 0): field_value = f"{getattr(insn, field_name)} - UOP"
                    elif (field_value == 1): field_value = f"{getattr(insn, field_name)} - WGT"
                    elif (field_value == 2): field_value = f"{getattr(insn, field_name)} - INP"
                    elif (field_value == 3): field_value = f"{getattr(insn, field_name)} - ACC"
                    elif (field_value == 4): field_value = f"{getattr(insn, field_name)} - OUT"
                elif (field_name == "sram_base" or field_name == "dram_base"):
                    field_value = f"{getattr(insn, field_name)} - {hex(getattr(insn, field_name))}"
                print(f"{field_name}: {field_value}")
        
        # Print the semaphore
        print(f"\n\nSemaphore: {semaphore}")

        print(f"\n\nUOPs: ({len(uop_buffer)})")
        for i, uop in enumerate(uop_buffer):
            print(f"\nUOP{i}: dst_idx={uop.dst_idx}, src_idx={uop.src_idx}, wgt_idx={uop.wgt_idx}")

    # Return the instructions and UOPs lists
    return insn_buffer, uop_buffer

# ---------------------------------------------


###############################################
