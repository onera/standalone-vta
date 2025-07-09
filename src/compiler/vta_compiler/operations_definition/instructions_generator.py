# IMPORT PACKAGES
# ---------------
try:
    from structures import *
except:
    from operations_definition.structures import *

###############################################


# RESET SEQUENCE
# --------------
def reset_sequence(strategy, dram_addresses, uop_counter=0, block_size=16):
    """Reset instructions ensure that no residual data remain that could affect the execution"""
    # Init
    insn_buffer = []
    uop_buffer = []

    # Biggest accumulator size used
    reset_size = 0
    for step in strategy:
        reset_size = max(reset_size, len(step[0]))

    # UOP addresse
    uop_addr = int( next(addr for addr in dram_addresses if addr.get("type") == "UOP")["logical_base_address"], 16)

    # UOP - reset
    uop_buffer.append(VTAUop( 
        dst_idx=0, 
        src_idx=0,
        wgt_idx=0
    ))
    # INSN - LOAD UOP
    insn_buffer.append(VTAMemInsn( 
        opcode=0, # 0-LOAD, 1-STORE, 3-FINISH
        # DEP FLAG
        pop_prev_dep=0,
        pop_next_dep=0,
        push_prev_dep=0,
        push_next_dep=0,
        # Memory interaction
        buffer_id=0, # 0-UOP, 1-WGT, 2-INP, 3-ACC, 4-OUT, 5-ACC8bit
        sram_base=0x0000, # Always first UOP
        dram_base=uop_addr, 
        unused=0, # UNUSED
        # Operation over the data
        y_size=1,
        x_size=1,
        x_stride=1,
        y_pad_top=0,
        y_pad_bottom=0,
        x_pad_left=0,
        x_pad_right=0
    ))

    insn_buffer.append(VTAGemInsn( # I1: GEMM RESET
        opcode=2, # 2-GEMM
        # DEP FLAG
        pop_prev_dep=0,
        pop_next_dep=0,
        push_prev_dep=1, # Ready signal to LOAD
        push_next_dep=0,
        # Operations
        reset=1, # 0-no, 1-reset
        uop_bgn=len(uop_buffer) - 1,
        uop_end=len(uop_buffer),
        loop_out=reset_size, # Reset reset_size blocks
        loop_in=block_size, # Reset a block
        # UNUSED
        unused=0, # UNUSED
        # Index factors
        dst_factor_out=1, # Reset reset_size blocks
        dst_factor_in=1, # Reset a block
        src_factor_out=0,
        src_factor_in=0,
        wgt_factor_out=0,
        wgt_factor_in=0
    ))

    return insn_buffer, uop_buffer, uop_counter + len(uop_buffer)


# ---------------------------------------------


# STRATEGY STEP
# -------------
def strategy_step(step, dram_addresses, memory_status, uop_counter=0, block_size=16):
    # Init
    insn_buffer = []
    uop_buffer = []

    # DRAM addresses
    uop_addr = [addr for addr in dram_addresses if addr.get("type") == "UOP"]
    inp_addr = [addr for addr in dram_addresses if addr.get("type") == "INP"]
    wgt_addr = [addr for addr in dram_addresses if addr.get("type") == "WGT"]
    acc_addr = [addr for addr in dram_addresses if addr.get("type") == "WGT"]
    out_addr = [addr for addr in dram_addresses if addr.get("type") == "WGT"]


    # LOAD MODULE (input: CMP->LD, output: LD->CMP)
    # -----------
    # Check if INP and WGT must be loaded
    nb_inp = len(step[1])
    nb_wgt = len(step[2])
    doLoadInp = False if (nb_inp == 0) else True
    doLoadWgt = False if (nb_wgt == 0) else True

    # Set the dep flag
    ack_signal = 0 if (doLoadInp == True) else 1
    ready_signal = 0 if (doLoadWgt == True) else 1

    # INSN - LOAD INP
    for i, block_idx in enumerate(step[1]):
        # Get the idx
        current_block_addr = find_logical_block_addr_by_idx(block_idx, inp_addr)
        # Append
        insn_buffer.append(VTAMemInsn( 
            opcode=0, # 0-LOAD, 1-STORE, 3-FINISH
            # DEP FLAG
            pop_prev_dep=0,
            pop_next_dep=1 if (i == 0) else 0, # Acknowledge COMPUTE ready signal (first load)
            push_prev_dep=0,
            push_next_dep=ready_signal if (i == nb_inp-1) else 0, # Ready signal to COMPUTE if no WGT load (last load)
            # Memory interaction
            buffer_id=2, # 0-UOP, 1-WGT, 2-INP, 3-ACC, 4-OUT, 5-ACC8bit
            sram_base=0x0000 + i*block_size,
            dram_base=current_block_addr,
            unused=0, # UNUSED
            # Operation over the data
            y_size=1,
            x_size=block_size, # Load a full block
            x_stride=block_size,
            y_pad_top=0,
            y_pad_bottom=0,
            x_pad_left=0,
            x_pad_right=0
        ))

    # INSN - LOAD WGT
    for i, block_idx in enumerate(step[2]):
        # Get the idx
        current_block_addr = find_logical_block_addr_by_idx(block_idx, wgt_addr)
        # Append
        insn_buffer.append(VTAMemInsn( 
            opcode=0, # 0-LOAD, 1-STORE, 3-FINISH
            # DEP FLAG
            pop_prev_dep=0,
            pop_next_dep=ack_signal if (i == 0) else 0, # Acknowledge COMPUTE ready signal if no INP load (first load)
            push_prev_dep=0,
            push_next_dep=1 if (i == nb_wgt-1) else 0, # Ready signal to COMPUTE if no WGT load (last load)
            # Memory interaction
            buffer_id=2, # 0-UOP, 1-WGT, 2-INP, 3-ACC, 4-OUT, 5-ACC8bit
            sram_base=0x0000 + i,
            dram_base=current_block_addr,
            unused=0, # UNUSED
            # Operation over the data
            y_size=1,
            x_size=1,
            x_stride=1,
            y_pad_top=0,
            y_pad_bottom=0,
            x_pad_left=0,
            x_pad_right=0
        ))
    
    # Acknowledge and send ready if no load
    if (doLoadInp == False and doLoadWgt == False):
        # INSN - NOP-MEMORY-STAGE (load)
        insn_buffer.append(VTAMemInsn( 
            opcode=0, # 0-LOAD, 1-STORE, 3-FINISH
            # DEP FLAG
            pop_prev_dep=0,
            pop_next_dep=1, # Acknowledge COMPUTE ready signal
            push_prev_dep=0, 
            push_next_dep=1, # Ready signal to COMPUTE
            # Memory interaction
            buffer_id=2, # 0-UOP, 1-WGT, 2-INP, 3-ACC, 4-OUT, 5-ACC8bit
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


    # COMPUTE MODULE (input: LD->CMP, output: CMP->LD & CMP->ST)
    # --------------
    nbLoadAcc = len(step[3])
    nb_gemm = sum(1 for item in step[4] if item[0] == 'GeMM')
    nb_alu = len(step[4]) - nb_gemm

    doLoadAcc = False if (nbLoadAcc == 0) else True
    doGemm = False if (nb_gemm == 0) else True
    doAlu = False if (nb_alu == 0) else True

    # INSN - LOAD ACC
    isLastCompute = False if (doGemm == True or doAlu == True) else True
    for i, block_idx in enumerate(step[3]):
        # Get the idx
        current_block_addr = find_logical_block_addr_by_idx(block_idx, acc_addr)
        # Append
        insn_buffer.append(VTAMemInsn( 
            opcode=0, # 0-LOAD, 1-STORE, 3-FINISH
            # DEP FLAG
            pop_prev_dep=1 if (i == 0) else 0, # Acknowledge LOAD ready signal (first load)
            pop_next_dep=0, 
            push_prev_dep=0,
            push_next_dep=1 if (i == nb_alu-1 and isLastCompute == True) else 0, # Ready signal to STORE (last load)
            # Memory interaction
            buffer_id=2, # 0-UOP, 1-WGT, 2-INP, 3-ACC, 4-OUT, 5-ACC8bit
            sram_base=0x0000 + i*block_size,
            dram_base=current_block_addr,
            unused=0, # UNUSED
            # Operation over the data
            y_size=1,
            x_size=block_size, # Load a full block
            x_stride=block_size,
            y_pad_top=0,
            y_pad_bottom=0,
            x_pad_left=0,
            x_pad_right=0
        ))

    # INSN - GEMM (+ load UOP)
    isFirstCompute = False if (doLoadAcc == True) else True
    isLastCompute = False if (doAlu == True) else True

    for gemm_idx in range(0, nb_gemm):
        gemm = step[4][gemm_idx]

        c_sram_idx = block_idx_in_sram(gemm[1], memory_status)
        a_sram_idx = block_idx_in_sram(gemm[2], step[1])
        b_sram_idx = block_idx_in_sram(gemm[3], step[2])

        current_uop_addr = find_uop_addr(uop_addr, len(uop_buffer), uop_counter)

        # UOP
        uop_buffer.append(VTAUop( 
            dst_idx=c_sram_idx, 
            src_idx=a_sram_idx,
            wgt_idx=b_sram_idx
        ))
        # INSN - LOAD UOP
        insn_buffer.append(VTAMemInsn( 
            opcode=0, # 0-LOAD, 1-STORE, 3-FINISH
            # DEP FLAG
            pop_prev_dep=1 if (i == 0 and isFirstCompute == True) else 0, # Acknowledge LOAD ready signal (first load)
            pop_next_dep=0,
            push_prev_dep=0,
            push_next_dep=0,
            # Memory interaction
            buffer_id=0, # 0-UOP, 1-WGT, 2-INP, 3-ACC, 4-OUT, 5-ACC8bit
            sram_base=0x0000 + gemm_idx, # Always first UOP
            dram_base=current_uop_addr,
            unused=0, # UNUSED
            # Operation over the data
            y_size=1,
            x_size=1,
            x_stride=1,
            y_pad_top=0,
            y_pad_bottom=0,
            x_pad_left=0,
            x_pad_right=0
        ))
        # INSN - GEMM
        insn_buffer.append(VTAGemInsn( 
            opcode=2, # 2-GEMM
            # DEP FLAG
            pop_prev_dep=0,
            pop_next_dep=0,
            push_prev_dep=1 if (gemm_idx == nb_gemm-1) else 0, # Ready signal to LOAD (last GeMM)
            push_next_dep=1 if (gemm_idx == nb_gemm-1 and isLastCompute == True) else 0, # Ready signal to STORE (last compute)
            # Operations
            reset=1, # 0-no, 1-reset
            uop_bgn=uop_counter + len(uop_buffer) - 1,
            uop_end=uop_counter + len(uop_buffer),
            loop_out=1,
            loop_in=block_size, # Compute a block
            # UNUSED
            unused=0, # UNUSED
            # Index factors
            dst_factor_out=0, 
            dst_factor_in=1, # Compute a block
            src_factor_out=0,
            src_factor_in=0,
            wgt_factor_out=0,
            wgt_factor_in=0
        ))

    # INSN - ALU (+ load UOP)
    isFirstCompute = False if (doLoadAcc == True or doGemm == True) else True
    to_store = []

    for alu_idx in range(nb_gemm, nb_alu):
        alu = step[4][alu_idx]
        
        # Define the opcode
        if (alu[0].startswith("MAX")):
            alu_opcode = 1
        elif (alu[0].startswith("MIN")):
            alu_opcode = 0
        elif (alu[0].startswith("ADD")):
            alu_opcode = 2
        elif (alu[0].startswith("MUL")):
            alu_opcode = 4
        elif (alu[0].startswith("SHR")):
            alu_opcode = 3
        else:
            raise Exception(f"ERROR: ALU non-supported operations ({alu[0]})! \n\n")
        
        # Define if it is immediate
        imm = 0
        isImm = False
        if (alu[0].endswith("_IMM")):
            imm = alu[1][1]
            isImm = True

        for i, current_alu in enumerate(alu[2]):
            if (isImm == False):
                c_sram_idx = block_idx_in_sram(current_alu[0][0], memory_status)
                to_store.append( current_alu[1] * c_sram_idx )
                src_sram_idx = block_idx_in_sram(current_alu[1][0], memory_status)
            else: 
                c_sram_idx = block_idx_in_sram(current_alu[0], memory_status)
                to_store += [line * c_sram_idx for line in range(0,block_size) ]

            current_uop_addr = find_uop_addr(uop_addr, len(uop_buffer), uop_counter)

            # UOP
            uop_buffer.append(VTAUop( 
                dst_idx=c_sram_idx, 
                src_idx=src_sram_idx if (isImm == False) else 0,
                wgt_idx=0
            ))
            # INSN - LOAD UOP
            insn_buffer.append(VTAMemInsn( 
                opcode=0, # 0-LOAD, 1-STORE, 3-FINISH
                # DEP FLAG
                pop_prev_dep=1 if (i == 0 and isFirstCompute == True) else 0, # Acknowledge LOAD ready signal (first load)
                pop_next_dep=0,
                push_prev_dep=0,
                push_next_dep=0,
                # Memory interaction
                buffer_id=0, # 0-UOP, 1-WGT, 2-INP, 3-ACC, 4-OUT, 5-ACC8bit
                sram_base=0x0000 + alu_idx, # Always first UOP
                dram_base=current_uop_addr,
                unused=0, # UNUSED
                # Operation over the data
                y_size=1,
                x_size=1,
                x_stride=1,
                y_pad_top=0,
                y_pad_bottom=0,
                x_pad_left=0,
                x_pad_right=0
            ))
            # INSN - ALU
            insn_buffer.append(VTAAluInsn( # I9: ALU - SHR (Average Pooling 3/3)
                opcode=4, # 4-ALU
                # DEP FLAG
                pop_prev_dep=0,
                pop_next_dep=0,
                push_prev_dep=0,
                push_next_dep=1 if (alu_idx == nb_alu - 1) else 0, # Ready signal to STORE (last alu)
                # Operations
                reset=0, # 0-no, 1-reset
                uop_bgn=uop_counter + len(uop_buffer) - 1,
                uop_end=uop_counter + len(uop_buffer) - 1,
                loop_out=1,
                loop_in=1,
                # UNUSED
                unused=0, # UNUSED
                # Index factors
                dst_factor_out=0,
                dst_factor_in=0, 
                src_factor_out=0,
                src_factor_in=0, 
                alu_opcode=alu_opcode, # 0-MIN, 1-MAX, 2-ADD, 3-SHR, 4-MUL
                use_imm=1 if (isImm == True) else 0, # 0-no, 1-yes
                imm=imm if (isImm == True) else 0
            ))

    # If no compute stage
    if (doLoadAcc == False and doGemm == False and doAlu == False):
        # INSN - NOP-COMPUTE-STAGE
        insn_buffer.append(VTAMemInsn( 
            opcode=0, # 0-LOAD, 1-STORE, 3-FINISH
            # DEP FLAG
            pop_prev_dep=1, # Acknowledge LOAD ready signal
            pop_next_dep=0, 
            push_prev_dep=1, # Ready signal to LOAD
            push_next_dep=1, # Ready signal to STORE
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


    # STORE MODULE (input: CMP->LD & CMP->ST, output: CMP->LD)
    # ------------
    nb_out = len(step[0])
    # INSN - STORE
    if (len(to_store) == 0):
        for i, block_idx in enumerate(step[0]):
            # Get the idx
            current_block_addr = find_logical_block_addr_by_idx(block_idx, out_addr)
            # Append
            insn_buffer.append(VTAMemInsn( 
                opcode=1, # 0-LOAD, 1-STORE, 3-FINISH
                # DEP FLAG
                pop_prev_dep=1 if (i == 0) else 0, # Acknowledge COMPUTE ready signal (first store)
                pop_next_dep=0,
                push_prev_dep=1 if (i == nb_out - 1) else 0, # Ready signal to COMPUTE
                push_next_dep=0,
                # Memory interaction
                buffer_id=4, # 0-UOP, 1-WGT, 2-INP, 3-ACC, 4-OUT, 5-ACC8bit
                sram_base=0x0000 + i*block_size, 
                dram_base=current_block_addr, 
                unused=0, # UNUSED
                # Operation over the data
                y_size=1,
                x_size=block_size, # Store a full block
                x_stride=block_size,
                y_pad_top=0,
                y_pad_bottom=0,
                x_pad_left=0,
                x_pad_right=0
            ))
    else:
        for i, line in enumerate(to_store):
            # Get the base address of UOP
            base_addr = int( uop_addr[0]["logical_base_address"], 16)
            # Append
            insn_buffer.append(VTAMemInsn( 
                opcode=1, # 0-LOAD, 1-STORE, 3-FINISH
                # DEP FLAG
                pop_prev_dep=1 if (i == 0) else 0, # Acknowledge COMPUTE ready signal (first store)
                pop_next_dep=0,
                push_prev_dep=1 if (i == len(to_store) - 1) else 0, # Ready signal to COMPUTE
                push_next_dep=0,
                # Memory interaction
                buffer_id=4, # 0-UOP, 1-WGT, 2-INP, 3-ACC, 4-OUT, 5-ACC8bit
                sram_base=line, 
                dram_base=base_addr + i, 
                unused=0, # UNUSED
                # Operation over the data
                y_size=1,
                x_size=1, # Store vector by vector
                x_stride=1,
                y_pad_top=0,
                y_pad_bottom=0,
                x_pad_left=0,
                x_pad_right=0
            ))
    
    # INSN - NOP-COMPUTE-STAGE
    insn_buffer.append(VTAMemInsn( 
        opcode=0, # 0-LOAD, 1-STORE, 3-FINISH
        # DEP FLAG
        pop_prev_dep=0, 
        pop_next_dep=1, # Acknowledge STORE ready signal
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

    # Return the sequences
    return insn_buffer, uop_buffer, uop_counter + len(uop_buffer)


# ---------------------------------------------


# RESET SEQUENCE
# --------------
def termination_sequence():
    # Init
    insn_buffer = []
    uop_buffer = []

    # INSN - NOP-MEMORY-STAGE (LOAD)
    insn_buffer.append(VTAMemInsn(
        opcode=0, # 0-LOAD, 1-STORE, 3-FINISH
        # DEP FLAG
        pop_prev_dep=0,
        pop_next_dep=1, # Acknowledge COMPUTE ready signal
        push_prev_dep=0, 
        push_next_dep=1, # Ready signal to COMPUTE
        # Memory interaction
        buffer_id=2, # 0-UOP, 1-WGT, 2-INP, 3-ACC, 4-OUT, 5-ACC8bit
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

    insn_buffer.append(VTAMemInsn( # I209: NOP-COMPUTE-STAGE
        opcode=0, # 0-LOAD, 1-STORE, 3-FINISH
        # DEP FLAG
        pop_prev_dep=1, # Acknowledge LOAD ready signal
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

    insn_buffer.append(VTAMemInsn( # I210: FINISH
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

    return insn_buffer


###############################################
# FIND_BLOCK_ADDR_BY_IDX
# ----------------------
def find_logical_block_addr_by_idx(block_idx, addr_dict):
    block_addr_list = addr_dict[0]['blocks_addresses']
    tuple_addr = next(t for t in block_addr_list if t[0] == block_idx)
    return int( tuple_addr[2], 16)

# ---------------------------------------------

# FIND_UOP_ADDR
# ----------------------
def find_uop_addr(uop_addr, uop_buffer_size, uop_counter):
    uop_logic_addr = int( uop_addr[0]["logical_base_address"], 16)
    current_uop_addr = uop_logic_addr + uop_counter + (uop_buffer_size-1)
    return current_uop_addr

# ---------------------------------------------

# BLOCK_IDX_IN_SRAM
# --------------------
def block_idx_in_sram(block_idx, memory_status):
    return memory_status.index(block_idx)
