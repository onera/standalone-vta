# IMPORT PACKAGES
# ---------------
try:
    from structures import *
except:
    from operations_definition.structures import *

###############################################

# NOP_STAGE_INSTRUCTION
# ---------------------
def nop_stage_instruction(module="COMPUTE", pop_prev_dep=0, pop_next_dep=0, push_prev_dep=0, push_next_dep=0,
                          semaphore={}):
    if (len(semaphore) == 0):
        raise Exception(f"ERROR: no semaphore given! \n\n")

    # Init
    opcode = 0
    buffer_id = 0

    # Check the type of module
    if (module == "LOAD"):
        opcode = 0 # LOAD
        buffer_id = 2 # INP BUFFER

        # Update the semaphore
        semaphore["LD->CMP"] += push_next_dep
        semaphore["CMP->LD"] -= pop_next_dep

    elif (module == "COMPUTE"):
        opcode = 0 # LOAD
        buffer_id = 0 # UOP BUFFER

        # Update the semaphore
        semaphore["LD->CMP"] -= pop_prev_dep
        semaphore["ST->CMP"] -= pop_next_dep
        semaphore["CMP->LD"] += push_prev_dep
        semaphore["CMP->ST"] += push_next_dep

    elif (module == "STORE"):
        opcode = 1 # STORE
        buffer_id = 4 # OUT BUFFER

        # Update the semaphore
        semaphore["ST->CMP"] += push_prev_dep
        semaphore["CMP->ST"] -= pop_prev_dep

    else:
        raise Exception(f"ERROR: NOP-STAGE non-supported ({module}), must be either: 'LOAD', 'COMPUTE', 'STORE'! \n\n")

    # The instruction
    nop_insn = VTAMemInsn(
        opcode=opcode, # 0-LOAD, 1-STORE, 3-FINISH
        # DEP FLAG
        pop_prev_dep=pop_prev_dep,
        pop_next_dep=pop_next_dep,
        push_prev_dep=push_prev_dep, 
        push_next_dep=push_next_dep, 
        # Memory interaction
        buffer_id=buffer_id, # 0-UOP, 1-WGT, 2-INP, 3-ACC, 4-OUT, 5-ACC8bit
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
    )

    return nop_insn, semaphore

# ---------------------------------------------

# LOAD_STORE_INSTRUCTION
# ----------------------
def load_store_instruction(buffer_type="UOP", pop_prev_dep=0, pop_next_dep=0, push_prev_dep=0, push_next_dep=0,
                           sram_base=0, dram_base=0,
                           y_size=0, x_size=0, x_stride=0,
                           semaphore={}):
    if (len(semaphore) == 0):
        raise Exception(f"ERROR: no semaphore given! \n\n")
    
    # Init
    opcode = 0
    buffer_id = 0

    # Check the type of module
    if (buffer_type == "UOP"):
        opcode = 0 # LOAD
        buffer_id = 0 # UOP BUFFER
    elif (buffer_type == "WGT"):
        opcode = 0 # LOAD
        buffer_id = 1 # WGT BUFFER
    elif (buffer_type == "INP"):
        opcode = 0 # LOAD
        buffer_id = 2 # INP BUFFER
    elif (buffer_type == "ACC"):
        opcode = 0 # LOAD
        buffer_id = 3 # ACC BUFFER
    elif (buffer_type == "OUT"):
        opcode = 1 # STORE
        buffer_id = 4 # OUT BUFFER
    else:
        raise Exception(f"ERROR: LOAD-STORE non-supported ({buffer_type}), must be either: 'UOP', 'WGT', 'INP', 'ACC' or 'OUT'! \n\n")
    
    # Update the semaphore
    if (buffer_type == "UOP" or buffer_type == "ACC"): # COMPUTE
        semaphore["LD->CMP"] -= pop_prev_dep
        semaphore["ST->CMP"] -= pop_next_dep
        semaphore["CMP->LD"] += push_prev_dep
        semaphore["CMP->ST"] += push_next_dep
    elif (buffer_type == "INP" or buffer_type == "WGT"): # LOAD
        semaphore["LD->CMP"] += push_next_dep
        semaphore["CMP->LD"] -= pop_next_dep
    else: # buffer_type == "OUT" # STORE
        semaphore["ST->CMP"] += push_prev_dep
        semaphore["CMP->ST"] -= pop_prev_dep

    # The instruction
    load_store_insn = VTAMemInsn(
        opcode=opcode, # 0-LOAD, 1-STORE, 3-FINISH
        # DEP FLAG
        pop_prev_dep=pop_prev_dep,
        pop_next_dep=pop_next_dep,
        push_prev_dep=push_prev_dep, 
        push_next_dep=push_next_dep, 
        # Memory interaction
        buffer_id=buffer_id, # 0-UOP, 1-WGT, 2-INP, 3-ACC, 4-OUT, 5-ACC8bit
        sram_base=sram_base,
        dram_base=dram_base,
        unused=0, # UNUSED
        # Operation over the data
        y_size=y_size,
        x_size=x_size,
        x_stride=x_stride,
        y_pad_top=0,
        y_pad_bottom=0,
        x_pad_left=0,
        x_pad_right=0
    )

    return load_store_insn, semaphore 

# ---------------------------------------------

# GEMM_INSTRUCTION
# ----------------
def gemm_instruction(reset=0, pop_prev_dep=0, pop_next_dep=0, push_prev_dep=0, push_next_dep=0,
                     uop_begin=0, uop_end=1,
                     lp_out=0, dst_out=0, src_out=0, wgt_out=0,
                     lp_in=0, dst_in=0, src_in=0, wgt_in=0,
                     semaphore={}):
    if (len(semaphore) == 0):
        raise Exception(f"ERROR: no semaphore given! \n\n")
    
    # The instruction
    gemm_insn = VTAGemInsn( 
        opcode=2, # 2-GEMM
        # DEP FLAG
        pop_prev_dep=pop_prev_dep,
        pop_next_dep=pop_next_dep,
        push_prev_dep=push_prev_dep,
        push_next_dep=push_next_dep,
        # Operations
        reset=reset, # 0-no, 1-reset
        uop_bgn=uop_begin,
        uop_end=uop_end,
        loop_out=lp_out,
        loop_in=lp_in, 
        # UNUSED
        unused=0, # UNUSED
        # Index factors
        dst_factor_out=dst_out, 
        dst_factor_in=dst_in, 
        src_factor_out=src_out,
        src_factor_in=src_in,
        wgt_factor_out=wgt_out,
        wgt_factor_in=wgt_in
    )

    # Update the semaphore
    semaphore["LD->CMP"] -= pop_prev_dep
    semaphore["ST->CMP"] -= pop_next_dep
    semaphore["CMP->LD"] += push_prev_dep
    semaphore["CMP->ST"] += push_next_dep

    return gemm_insn, semaphore

# ---------------------------------------------

# ALU_INSTRUCTION
# ---------------
def alu_instruction(alu_opcode=0, pop_prev_dep=0, pop_next_dep=0, push_prev_dep=0, push_next_dep=0,
                     uop_begin=0, uop_end=1,
                     lp_out=0, dst_out=0, src_out=0, 
                     lp_in=0, dst_in=0, src_in=0, 
                     use_imm=0, imm=0,
                     semaphore={}):
    if (len(semaphore) == 0):
        raise Exception(f"ERROR: no semaphore given! \n\n")
    
    # The instruction
    alu_insn = VTAAluInsn( 
        opcode=4, # 4-ALU
        # DEP FLAG
        pop_prev_dep=pop_prev_dep,
        pop_next_dep=pop_next_dep,
        push_prev_dep=push_prev_dep,
        push_next_dep=push_next_dep,
        # Operations
        reset=0, # 0-no, 1-reset
        uop_bgn=uop_begin,
        uop_end=uop_end,
        loop_out=lp_out,
        loop_in=lp_in,
        # UNUSED
        unused=0, # UNUSED
        # Index factors
        dst_factor_out=dst_out,
        dst_factor_in=dst_in, 
        src_factor_out=src_out,
        src_factor_in=src_in, 
        alu_opcode=alu_opcode, # 0-MIN, 1-MAX, 2-ADD, 3-SHR, 4-MUL
        use_imm=use_imm, # 0-no, 1-yes
        imm=imm
    )

    # Update the semaphore
    semaphore["LD->CMP"] -= pop_prev_dep
    semaphore["ST->CMP"] -= pop_next_dep
    semaphore["CMP->LD"] += push_prev_dep
    semaphore["CMP->ST"] += push_next_dep

    return alu_insn, semaphore

