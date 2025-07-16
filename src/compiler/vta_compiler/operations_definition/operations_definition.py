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
                          operations_dict={}, block_size=16,
                          A_blocks_col=1, B_blocks_col=1, X_blocks_col=1, C_blocks_col=1,
                          debug=True):
    # Init the lists of instructions, UOPs and semaphore
    insn_buffer = []
    uop_buffer = []
    memory_status = []
    uop_counter = 0
    semaphore_state = (0, 0, 0, 0) # (LD->CMP, CMP->LD, CMP->ST, ST->CMP)

    # Number of strategy steps
    nb_steps = len(strategy)

    # 0 - Reset (input: /, output: CMP->LD)
    new_insn, new_buffer, uop_counter = reset_sequence(strategy, dram_addresses, uop_counter, block_size)
    insn_buffer = insn_buffer + new_insn
    uop_buffer = uop_buffer + new_buffer

    # 1 - strategy step (input: CMP->LD, output: CMP->LD)
    for i, step in enumerate(strategy):
        memory_status = step[3]

        new_insn, new_buffer, uop_counter = strategy_step(step, dram_addresses, memory_status, uop_counter, block_size)
        insn_buffer = insn_buffer + new_insn
        uop_buffer = uop_buffer + new_buffer

    # 2 - Termination sequence (input: CMP->LD, output: /)
    insn_buffer += termination_sequence() 

 

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

        print(f"\n\nUOPs: ({len(uop_buffer)})")
        for i, uop in enumerate(uop_buffer):
            print(f"\nUOP{i}: dst_idx={uop.dst_idx}, src_idx={uop.src_idx}, wgt_idx={uop.wgt_idx}")

    # Return the instructions and UOPs lists
    return insn_buffer, uop_buffer

# ---------------------------------------------


###############################################

if __name__ == "__main__": 
    # Define the strategies: A=[1, 4], B=[4, 2] C=[1, 2]
    A_blocks_col = 4
    B_blocks_col = 2
    C_blocks_col = 2

    # 1 - no overfitting
    strategy_1 = [([0, 1], [0, 1, 2, 3], [0, 1, 2, 3, 5, 6, 7], [0, 1])]

    # 2 - overfitting
    strategy_2 = [
                  ([], [0, 1], [0, 2], [0]),
                  ([0], [2, 3], [4, 6], []),
                  ([], [0, 1], [1, 3], [1]),
                  ([1], [2, 3], [5, 7], []),
                  ]
    
    # Strategy selection
    select = 1 # If 1 strategy_1 is instanciated

    if (select == 1):
        strategy = strategy_1
        isOverfitting = False
    else:
        strategy = strategy_2
        isOverfitting = True
    
    # DRAM allocation
    isAccInit = True # If true, X must be loaded, else no

    dram_addresses = [
        {"type": "INP", 'physical_base_address': 0x1000, "logical_base_address": 0x100, "size": 4*256, "blocks_addresses": [
            ("A0", 0x1000, 0x100), 
            ("A1", 0x1100, 0x110), 
            ("A2", 0x1200, 0x120), 
            ("A3", 0x1300, 0x130)
            ]},
        {"type": "WGT", "physical_base_address": 0x2000, "logical_base_address": 0x20, "size": 8*256, "blocks_addresses": [
            ("B0", 0x2000, 0x20), 
            ("B1", 0x2100, 0x21), 
            ("B2", 0x2200, 0x22), 
            ("B3", 0x2300, 0x23), 
            ("B4", 0x2400, 0x24), 
            ("B5", 0x2500, 0x25), 
            ("B6", 0x2600, 0x26), 
            ("B7", 0x2700, 0x27)
            ]},
        {"type": "ACC", 'physical_base_address': 0x3000, "logical_base_address": 0xc0, "size": 2*64*16, "blocks_addresses": [
            ("X0", 0x3000, 0xc0), 
            ("X1", 0x3400, 0xd0)
            ]},
        {"type": "OUT", 'physical_base_address': 0x4000, "logical_base_address": 0x400, "size": 2*256, "blocks_addresses": [
            ("C0", 0x4000, 0x400), 
            ("C1", 0x4100, 0x410)
            ]},
        {"type": "UOP", 'physical_base_address': 0x5000, "logical_base_address": 0x1400, "size": 4, "blocks_addresses": []}
    ]


    # Execute the functions
    operations_definition()
