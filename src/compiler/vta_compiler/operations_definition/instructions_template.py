# IMPORT PACKAGES
# ---------------
try:
    from structures import *
except:
    from operations_definition.structures import *

###############################################

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
    acc_addr = [addr for addr in dram_addresses if addr.get("type") == "ACC"]
    out_addr = [addr for addr in dram_addresses if addr.get("type") == "OUT"]


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
            buffer_id=1, # 0-UOP, 1-WGT, 2-INP, 3-ACC, 4-OUT, 5-ACC8bit
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
        # INSN - NOP-MEMORY-STAGE (load) (input: CMP->LD, output: LD->CMP)
        insn_buffer.append( 
            nop_stage_instruction(module="LOAD", pop_prev_dep=0, pop_next_dep=1, push_prev_dep=0, push_next_dep=1)
        )


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
            buffer_id=3, # 0-UOP, 1-WGT, 2-INP, 3-ACC, 4-OUT, 5-ACC8bit
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

    # INSTRUCTION LOAD UOP + GEMM
    isFirstCompute = False if (doLoadAcc == True) else True
    isLastCompute = False if (doAlu == True) else True

    # Get the current uop DRAM address
    current_uop_addr = find_uop_addr(uop_addr, len(uop_buffer), uop_counter)

    # Generate all the UOP
    for gemm_idx in range(0, nb_gemm):
        gemm = step[4][gemm_idx]

        c_sram_idx = block_idx_in_sram(gemm[1], memory_status)
        a_sram_idx = block_idx_in_sram(gemm[2], step[1])
        b_sram_idx = block_idx_in_sram(gemm[3], step[2])

        # UOP
        uop_buffer.append(VTAUop( 
            dst_idx=c_sram_idx * block_size, 
            src_idx=a_sram_idx * block_size,
            wgt_idx=b_sram_idx
        ))

    if (doGemm == True):
        # INSN - LOAD UOP
        insn_buffer.append(VTAMemInsn( 
            opcode=0, # 0-LOAD, 1-STORE, 3-FINISH
            # DEP FLAG
            pop_prev_dep=1 if (isFirstCompute == True) else 0, # Acknowledge LOAD ready signal (first load)
            pop_next_dep=0,
            push_prev_dep=0,
            push_next_dep=0,
            # Memory interaction
            buffer_id=0, # 0-UOP, 1-WGT, 2-INP, 3-ACC, 4-OUT, 5-ACC8bit
            sram_base=0x0000,
            dram_base=current_uop_addr,
            unused=0, # UNUSED
            # Operation over the data
            y_size=1,
            x_size=len(uop_buffer),
            x_stride=len(uop_buffer),
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
            push_prev_dep=1, # Ready signal to LOAD (last GeMM)
            push_next_dep=1 if (isLastCompute == True) else 0, # Ready signal to STORE (last compute)
            # Operations
            reset=0, # 0-no, 1-reset
            uop_bgn=0,
            uop_end=len(uop_buffer),
            loop_out=1,
            loop_in=block_size, # Compute a block
            # UNUSED
            unused=0, # UNUSED
            # Index factors
            dst_factor_out=0, 
            dst_factor_in=1, # Compute a block
            src_factor_out=0,
            src_factor_in=1,
            wgt_factor_out=0,
            wgt_factor_in=0
        ))

    # INSTRUCTION LOAD UOP + ALU
    isFirstCompute = False if (doLoadAcc == True or doGemm == True) else True
    to_store = []

    for alu_idx in range(nb_gemm, nb_gemm+nb_alu):
        alu = step[4][alu_idx]
        
        # Define the opcode
        if (alu[0].startswith("MAX") or alu[0] == "RELU" or alu[0] == "MAXPOOL"):
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
        if (alu[0].endswith("_IMM") or alu[0] == "RELU"):
            imm = alu[1][1]
            isImm = True

        # Get the current UOP DRAM address
        current_uop_addr = find_uop_addr(uop_addr, len(uop_buffer), uop_counter)

        # Generate the UOP for the current ALU
        for i, current_alu in enumerate(alu[2]):
            if (isImm == False):
                dst_block_idx = block_idx_in_sram(current_alu[0][0], memory_status) * block_size
                dst_vector_idx = current_alu[0][1] + dst_block_idx
                src_block_idx = block_idx_in_sram(current_alu[1][0], memory_status)
                src_vector_idx = current_alu[1][1] + src_block_idx
            else: 
                dst_block_idx = block_idx_in_sram(current_alu[0], memory_status) * block_size
                dst_vector_idx = current_alu[1] + dst_block_idx
            
            to_store.append( dst_vector_idx )

            # UOP
            uop_buffer.append(VTAUop( 
                dst_idx=dst_vector_idx, 
                src_idx=src_vector_idx if (isImm == False) else 0,
                wgt_idx=0
            ))
        
        # INSN - LOAD UOP
        insn_buffer.append(VTAMemInsn( 
            opcode=0, # 0-LOAD, 1-STORE, 3-FINISH
            # DEP FLAG
            pop_prev_dep=1 if (alu_idx == nb_gemm and isFirstCompute == True) else 0, # Acknowledge LOAD ready signal (first load)
            pop_next_dep=0,
            push_prev_dep=1 if (alu_idx == nb_gemm and isFirstCompute == True) else 0, # Ready signal to LOAD
            push_next_dep=0,
            # Memory interaction
            buffer_id=0, # 0-UOP, 1-WGT, 2-INP, 3-ACC, 4-OUT, 5-ACC8bit
            sram_base=0x0000, 
            dram_base=current_uop_addr,
            unused=0, # UNUSED
            # Operation over the data
            y_size=1,
            x_size=len(alu[2]),
            x_stride=len(alu[2]),
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
            push_next_dep=1 if (alu_idx == (nb_gemm+nb_alu) - 1) else 0, # Ready signal to STORE (last alu)
            # Operations
            reset=0, # 0-no, 1-reset
            uop_bgn=0,
            uop_end=len(alu[2]),
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
        # INSN - NOP-COMPUTE-STAGE (input: LD->CMP, output: CMP->LD & CMP->ST)
        insn_buffer.append( 
            nop_stage_instruction(module="COMPUTE", pop_prev_dep=1, pop_next_dep=0, push_prev_dep=1, push_next_dep=1)
        )


   # STORE MODULE (input: CMP->LD & CMP->ST, output: CMP->LD)
   # ------------
    nb_out = len(step[0])
    # INSN - STORE
    if (len(to_store) == 0 or isImm == True):
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
            base_addr = int( out_addr[0]["logical_base_address"], 16)
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
    
    # INSN - NOP-COMPUTE-STAGE (input: CMP->LD & ST->CMP, output: CMP->LD)
    insn_buffer.append( 
        nop_stage_instruction(module="COMPUTE", pop_prev_dep=0, pop_next_dep=1, push_prev_dep=0, push_next_dep=0)
    )

    # Return the sequences
    return insn_buffer, uop_buffer, uop_counter + len(uop_buffer)



###############################################

# NOP_STAGE_INSTRUCTION
# ---------------------
def nop_stage_instruction(module="COMPUTE", pop_prev_dep=0, pop_next_dep=0, push_prev_dep=0, push_next_dep=0):
    # Init
    opcode = 0
    buffer_id = 0

    # Check the type of module
    if (module == "LOAD"):
        opcode = 0 # LOAD
        buffer_id = 2 # INP BUFFER
    elif (module == "COMPUTE"):
        opcode = 0 # LOAD
        buffer_id = 0 # UOP BUFFER
    elif (module == "STORE"):
        opcode = 1 # STORE
        buffer_id = 4 # OUT BUFFER
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

    return nop_insn

# ---------------------------------------------

# LOAD_STORE_INSTRUCTION
# ----------------------
def load_store_instruction(buffer_type="UOP", pop_prev_dep=0, pop_next_dep=0, push_prev_dep=0, push_next_dep=0,
                           sram_base=0, dram_base=0,
                           y_size=0, x_size=0, x_stride=0):
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

    return load_store_insn  

