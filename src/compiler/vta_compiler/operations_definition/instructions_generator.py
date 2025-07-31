# IMPORT PACKAGES
# ---------------
try:
    from structures import *
    from utils_operations import *
    from step_instructions import *
    from instructions_template import *
except:
    from operations_definition.structures import *
    from operations_definition.utils_operations import *
    from operations_definition.step_instructions import *
    from operations_definition.instructions_template import *

###############################################


# RESET SEQUENCE
# --------------
def reset_sequence(strategy, semaphore, dram_addresses, uop_counter=0, block_size=16):
    """Reset instructions ensure that no residual data remain that could affect the execution"""
    # Init
    insn_buffer = []
    uop_buffer = []

    # Biggest accumulator size used
    reset_size = 0
    for step in strategy:
        reset_size = max(reset_size, len(step[3]))

    # UOP addresse
    uop_addr = int( next(addr for addr in dram_addresses if addr.get("type") == "UOP")["logical_base_address"], 16)

    # UOP - reset
    uop_buffer.append(VTAUop( 
        dst_idx=0, 
        src_idx=0,
        wgt_idx=0
    ))

    # INSN - LOAD UOP
    # Manage the semaphore
    pop_prev_dep = 0
    pop_next_dep = 0
    push_prev_dep = 0
    push_next_dep = 0

    # Generate LOAD UOP
    new_insn, semaphore = load_store_instruction(buffer_type="UOP", pop_prev_dep=pop_prev_dep, pop_next_dep=pop_next_dep, push_prev_dep=push_prev_dep, push_next_dep=push_next_dep, sram_base=0, dram_base=uop_addr, y_size=1, x_size=1, x_stride=1, semaphore=semaphore)
    insn_buffer.append( new_insn )

    # INSN - GEMM RESET
    # Manage the semaphore
    pop_prev_dep = 0
    pop_next_dep = 0
    push_prev_dep = 1 # Ready signal to LOAD
    push_next_dep = 0

    # Generate GEMM reset
    new_insn, semaphore = gemm_instruction(reset=1, pop_prev_dep=pop_prev_dep, pop_next_dep=pop_next_dep, push_prev_dep=push_prev_dep, push_next_dep=push_next_dep,
                                uop_begin=0, uop_end=1,
                                lp_out=1, dst_out=block_size, src_out=0, wgt_out=0,
                                lp_in=block_size, dst_in=1, src_in=0, wgt_in=0,
                                semaphore=semaphore)
    insn_buffer.append( new_insn )

    return insn_buffer, uop_buffer, semaphore, uop_counter + len(uop_buffer)


# ---------------------------------------------

# STEP_INSTRUCTIONS
# -----------------
def step_instructions(step, semaphore, dram_addresses, uop_counter=0, block_size=16, uop_buffer_size=8192):
    # Init the buffers
    insn_buffer = []
    uop_buffer = []

    # Get the DRAM addresses for each object
    uop_addr = [addr for addr in dram_addresses if addr.get("type") == "UOP"]
    inp_addr = [addr for addr in dram_addresses if addr.get("type") == "INP"]
    wgt_addr = [addr for addr in dram_addresses if addr.get("type") == "WGT"]
    acc_addr = [addr for addr in dram_addresses if addr.get("type") == "ACC"]
    acc_bis_addr = [addr for addr in dram_addresses if addr.get("type") == "ACC_BIS"]
    out_addr = [addr for addr in dram_addresses if addr.get("type") == "OUT"]

    # Get the step elements ([Ai], [Bi], [Xi], [Mi], [Ti], [Ci], [Operations])
    load_A = step[0]
    load_B = step[1]
    load_X = step[2]
    sram_state = step[3]
    dram_state = step[4]
    store_C = step[5]
    ops = step[6]

    nb_out = len(store_C)

    # 0 - LOAD INP and WGT
    # ---
    # Check if we load INP or WGT
    if (len(load_A) > 0 or len(load_B) > 0):
        new_insn, semaphore = step_load(load_A, load_B, inp_addr, wgt_addr, block_size, semaphore)
        insn_buffer = insn_buffer + new_insn


    # 1 - LOAD ACC
    # ---
    # Check we load ACC
    if (len(load_X) > 0):
        new_insn, semaphore = step_load_acc(load_X, sram_state, acc_addr, acc_bis_addr, block_size, semaphore)
        insn_buffer = insn_buffer + new_insn


    # 2 - LOAD UOP + GEMM + ALU
    # ---
    doStore = False if (nb_out == 0) else True
    
    new_insn, new_uop, semaphore = step_compute(ops, load_A, load_B, load_X, sram_state, uop_addr, uop_buffer_size, uop_counter, doStore, block_size, semaphore)
    insn_buffer = insn_buffer + new_insn
    uop_buffer = uop_buffer + new_uop


    # 3 - STORE
    # ---
    if (doStore == True):
        new_insn, semaphore = step_store(store_C, sram_state, dram_state, out_addr, block_size, semaphore)
        insn_buffer = insn_buffer + new_insn


    # Return
    # ---
    return insn_buffer, uop_buffer, semaphore, uop_counter + len(uop_buffer)


# ---------------------------------------------


# TERMINATION SEQUENCE (input: CMP->LD, output: /)
# --------------------
def termination_sequence(semaphore):
    # Init
    insn_buffer = []

    # Check the semaphore
    cmp_ld_signal = semaphore["CMP->LD"]
    ld_cmp_signal = semaphore["LD->CMP"]
    cmp_st_signal = semaphore["CMP->ST"]
    st_cmp_signal = semaphore["ST->CMP"]

    if (cmp_ld_signal > 0):
        push_next_dep = 1 if (ld_cmp_signal == 0) else 0

        # INSN - NOP-MEMORY-STAGE (LOAD) 
        new_insn, semaphore = nop_stage_instruction(module="LOAD", pop_prev_dep=0, pop_next_dep=1, push_prev_dep=0, push_next_dep=push_next_dep, semaphore=semaphore)
        insn_buffer.append( new_insn )

    if (cmp_st_signal > 0):
        push_prev_dep = 1 if (st_cmp_signal == 0) else 0

        # INSN - NOP-MEMORY-STAGE (STORE) 
        new_insn, semaphore = nop_stage_instruction(module="STORE", pop_prev_dep=0, pop_next_dep=1, push_prev_dep=push_prev_dep, push_next_dep=0, semaphore=semaphore)
        insn_buffer.append( new_insn )

    # Check again the semaphore
    ld_cmp_signal = semaphore["LD->CMP"]
    st_cmp_signal = semaphore["ST->CMP"]

    pop_prev_dep = 1 if (ld_cmp_signal > 0) else 0
    pop_next_dep = 1 if (st_cmp_signal > 0) else 0

    # INSN -  NOP-COMPUTE-STAGE (input: LD->CMP, output: /)
    new_insn, semaphore = nop_stage_instruction(module="COMPUTE", pop_prev_dep=pop_prev_dep, pop_next_dep=pop_next_dep, push_prev_dep=0, push_next_dep=0, semaphore=semaphore)
    insn_buffer.append( new_insn )


    # INSN - FINISH
    insn_buffer.append(VTAMemInsn( 
        opcode=3, # 0-LOAD, 1-STORE, 3-FINISH
        # DEP FLAG
        pop_prev_dep=0,
        pop_next_dep=0,
        push_prev_dep=0,
        push_next_dep=0,
        # Memory interaction
        buffer_id=0, # 0-UOP, 1-WGT, 2-INP, 3-ACC, 4-OUT, 5-ACC8bit
        sram_base=0x0000,
        dram_base=0x00000000,
        unused=0, # UNUSED
        # Operation over the data
        y_size=0,
        x_size=0,
        x_stride=0,
        y_pad_top=0,
        y_pad_bottom=0,
        x_pad_left=0,
        x_pad_right=0
    ))

    return insn_buffer, semaphore



###############################################


# DUMP_INSTRUCTIONS
# -----------------
def dump_instructions(nb_insn=1, semaphore={}):
    """Generate a given number of NOP-COMPUTE-STAGE instructions"""
    # Init
    insn_buffer = []
    uop_buffer = []

    # UOP - reset
    uop_buffer.append(VTAUop( 
        dst_idx=0, 
        src_idx=0,
        wgt_idx=0
    ))


    # INSN -  NOP-COMPUTE-STAGE
    for i in range(0, nb_insn-1):
        new_insn, semaphore = nop_stage_instruction(module="STORE", pop_prev_dep=0, pop_next_dep=0, push_prev_dep=0, push_next_dep=0, semaphore=semaphore)
        insn_buffer.append( new_insn )


    # INSN - FINISH
    insn_buffer.append(VTAMemInsn( 
        opcode=3, # 0-LOAD, 1-STORE, 3-FINISH
        # DEP FLAG
        pop_prev_dep=0,
        pop_next_dep=0,
        push_prev_dep=0,
        push_next_dep=0,
        # Memory interaction
        buffer_id=0, # 0-UOP, 1-WGT, 2-INP, 3-ACC, 4-OUT, 5-ACC8bit
        sram_base=0x0000,
        dram_base=0x00000000,
        unused=0, # UNUSED
        # Operation over the data
        y_size=0,
        x_size=0,
        x_stride=0,
        y_pad_top=0,
        y_pad_bottom=0,
        x_pad_left=0,
        x_pad_right=0
    ))

    return insn_buffer, uop_buffer, semaphore
