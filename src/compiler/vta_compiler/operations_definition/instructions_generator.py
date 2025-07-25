# IMPORT PACKAGES
# ---------------
try:
    from structures import *
    from instructions_template import *
except:
    from operations_definition.structures import *
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
                                lp_out=reset_size, dst_out=block_size, src_out=0, wgt_out=0,
                                lp_in=block_size, dst_in=1, src_in=0, wgt_in=0,
                                semaphore=semaphore)
    insn_buffer.append( new_insn )

    return insn_buffer, uop_buffer, semaphore, uop_counter + len(uop_buffer)


# ---------------------------------------------


# STRATEGY STEP
# -------------
def strategy_step(step, semaphore, dram_addresses, memory_status, uop_counter=0, block_size=16, uop_buffer_size=8192):
    # Init
    insn_buffer = []
    uop_buffer = []

    # DRAM addresses
    uop_addr = [addr for addr in dram_addresses if addr.get("type") == "UOP"]
    inp_addr = [addr for addr in dram_addresses if addr.get("type") == "INP"]
    wgt_addr = [addr for addr in dram_addresses if addr.get("type") == "WGT"]
    acc_addr = [addr for addr in dram_addresses if addr.get("type") == "ACC"]
    add_acc_addr = [addr for addr in dram_addresses if addr.get("type") == "ADD_ACC"]
    out_addr = [addr for addr in dram_addresses if addr.get("type") == "OUT"]


    # LOAD MODULE (input: CMP->LD, output: LD->CMP)
    # -----------
    # Check if INP and WGT must be loaded
    nb_inp = len(step[0])
    nb_wgt = len(step[1])
    doLoadInp = False if (nb_inp == 0) else True
    doLoadWgt = False if (nb_wgt == 0) else True

    # Set the dep flag
    ack_signal = 0 if (doLoadInp == True) else 1
    ready_signal = 0 if (doLoadWgt == True) else 1

    # INSN - LOAD INP
    # Check if the list has a constant gap
    idx_gap = check_constant_gap(step[0])
    if (idx_gap == -1):
        # Block wise load
        for i, block_idx in enumerate(step[0]):
            # Get the idx of the block in DRAM and the location in SRAM
            current_block_addr = find_logical_block_addr_by_idx(block_idx, inp_addr)
            current_sram_base=0x0000 + i*block_size

            # Acknowledge COMPUTE ready signal (first load)
            pop_next_dep = 1 if (i == 0) else 0 
            # Ready signal to COMPUTE if no WGT load (last load)
            push_next_dep = ready_signal if (i == nb_inp-1) else 0 

            # INSN LOAD INP - load a full block_size x block_size matrix
            new_insn, semaphore = load_store_instruction(buffer_type="INP", pop_prev_dep=0, pop_next_dep=pop_next_dep, push_prev_dep=0, push_next_dep=push_next_dep, sram_base=current_sram_base, dram_base=current_block_addr, y_size=1, x_size=block_size, x_stride=block_size, semaphore=semaphore)
            insn_buffer.append( new_insn )
    
    else: # Single load instructions
        # Get the first block address
        first_block_address = find_logical_block_addr_by_idx(step[0][0], inp_addr)
        # Sram is 0x0000
        sram_addr = 0x0000

        # Compute the parameters
        stride = idx_gap * block_size
        y_size = nb_inp

        # Acknowledge COMPUTE ready signal
        pop_next_dep = 1 
        # Ready signal to COMPUTE if no WGT load 
        push_next_dep = ready_signal  

        # INSN LOAD INP
        new_insn, semaphore = load_store_instruction(buffer_type="INP", pop_prev_dep=0, pop_next_dep=pop_next_dep, push_prev_dep=0, push_next_dep=push_next_dep, sram_base=sram_addr, dram_base=first_block_address, y_size=y_size, x_size=block_size, x_stride=stride, semaphore=semaphore)
        insn_buffer.append( new_insn )


    # INSN - LOAD WGT
    # Check if the list has a constant gap
    idx_gap = check_constant_gap(step[1])
    if (idx_gap == -1):
        # Block wise load
        for i, block_idx in enumerate(step[1]):
            # Get the idx of the block in DRAM and the location in SRAM
            current_block_addr = find_logical_block_addr_by_idx(block_idx, wgt_addr)
            current_sram_base=0x0000 + i

            # Acknowledge COMPUTE ready signal if no INP load (first load)
            pop_next_dep = ack_signal if (i == 0) else 0 
            # Ready signal to COMPUTE (last load)
            push_next_dep = 1 if (i == nb_wgt-1) else 0

            # INSN LOAD WGT - load a WGT matrix
            new_insn, semaphore = load_store_instruction(buffer_type="WGT", pop_prev_dep=0, pop_next_dep=pop_next_dep, push_prev_dep=0, push_next_dep=push_next_dep, sram_base=current_sram_base, dram_base=current_block_addr, y_size=1, x_size=1, x_stride=1, semaphore=semaphore)
            insn_buffer.append( new_insn )
    
    else: # Single load instructions
        # Get the first block address
        first_block_address = find_logical_block_addr_by_idx(step[1][0], wgt_addr)
        # Sram is 0x0000
        sram_addr = 0x0000

        # Compute the parameters
        stride = idx_gap
        y_size = nb_wgt

        # Acknowledge COMPUTE ready signal if no INP load 
        pop_next_dep = ack_signal
        # Ready signal to COMPUTE
        push_next_dep = 1

        # INSN LOAD WGT
        new_insn, semaphore = load_store_instruction(buffer_type="WGT", pop_prev_dep=0, pop_next_dep=pop_next_dep, push_prev_dep=0, push_next_dep=push_next_dep, sram_base=sram_addr, dram_base=first_block_address, y_size=y_size, x_size=1, x_stride=idx_gap, semaphore=semaphore)
        insn_buffer.append( new_insn )
    

    # Acknowledge and send ready if no load
    if (doLoadInp == False and doLoadWgt == False):
        # Acknowledge COMPUTE ready signal if no INP load (first load)
        pop_next_dep = 1 
        # Ready signal to COMPUTE if no WGT load (last load)
        push_next_dep = 1

        # INSN - NOP-MEMORY-STAGE (load) (input: CMP->LD, output: LD->CMP)
        new_insn, semaphore = nop_stage_instruction(module="LOAD", pop_prev_dep=0, pop_next_dep=pop_next_dep, push_prev_dep=0, push_next_dep=push_next_dep, semaphore=semaphore)
        insn_buffer.append( new_insn )


    # COMPUTE MODULE (input: LD->CMP, output: CMP->LD & CMP->ST)
    # --------------
    load_X = step[2]

    nbLoadAcc = len(load_X)
    nb_gemm = sum(1 for item in step[6] if item[0] == 'GeMM')
    nb_alu = len(step[6]) - nb_gemm

    doLoadAcc = False if (nbLoadAcc == 0) else True
    doGemm = False if (nb_gemm == 0) else True
    doAlu = False if (nb_alu == 0) else True

    # Check if we add two matrices
    doAddAcc = False if (len(add_acc_addr) == 0) else True

    # INSN - LOAD ACC
    isLastCompute = False if (doGemm == True or doAlu == True) else True
    # Check if the list has a constant gap
    idx_gap = check_constant_gap(load_X)
    if (idx_gap == -1):
        # Block wise load
        for i, block_idx in enumerate(load_X):
            # Acknowledge LOAD ready signal (first load)
            pop_prev_dep = 1 if (i == 0) else 0 
            # Ready signal to STORE (last load)
            push_next_dep = 1 if (i == nb_alu-1 and isLastCompute == True and doAddAcc == False) else 0 
            # Ready signal to LOAD (NO GeMM)
            push_prev_dep = 1 if (i == 0 and doGemm == False) else 0 
            # Nothing else
            pop_next_dep = 0

            # Check if block_idx is an int (i.e., a full block) or a tuple (i.e., a vector)
            if isinstance(block_idx, tuple):
                # Get the idx of the block in DRAM and the location in SRAM
                current_block_addr = find_logical_block_addr_by_idx(block_idx[0], acc_addr)
                current_dram = current_block_addr + block_idx[1]

                # Get the SRAM base find 
                sram_base = block_idx_in_sram(block_idx, memory_status)
                current_sram_base=sram_base

                # INSN LOAD ACC - load a full block_size x block_size matrix
                new_insn, semaphore = load_store_instruction(buffer_type="ACC", pop_prev_dep=pop_prev_dep, pop_next_dep=pop_next_dep, push_prev_dep=push_prev_dep, push_next_dep=push_next_dep, sram_base=current_sram_base, dram_base=current_dram, y_size=1, x_size=1, x_stride=1, semaphore=semaphore)
                insn_buffer.append( new_insn )

            else: # Full block
                # Get the idx of the block in DRAM and the location in SRAM
                current_block_addr = find_logical_block_addr_by_idx(block_idx, acc_addr)
                current_sram_base=0x0000 + i*block_size

                # INSN LOAD ACC - load a full block_size x block_size matrix
                new_insn, semaphore = load_store_instruction(buffer_type="ACC", pop_prev_dep=pop_prev_dep, pop_next_dep=pop_next_dep, push_prev_dep=push_prev_dep, push_next_dep=push_next_dep, sram_base=current_sram_base, dram_base=current_block_addr, y_size=1, x_size=block_size, x_stride=block_size, semaphore=semaphore)
                insn_buffer.append( new_insn )


    else: # Single load instruction
        # Get the first block address
        first_block_address = find_logical_block_addr_by_idx(load_X[0], acc_addr)
        # Sram is 0x0000
        sram_addr = 0x0000

        # Compute the parameters
        stride = idx_gap * block_size
        y_size = nbLoadAcc

        # Acknowledge LOAD ready signal
        pop_prev_dep = 1
        # Ready signal to STORE
        push_next_dep = 1 if (isLastCompute == True and doAddAcc == False) else 0 
        # Ready signal to LOAD (NO GeMM)
        push_prev_dep = 1 if (doGemm == False) else 0 
        # Nothing else
        pop_next_dep = 0

        # INSN LOAD ACC
        new_insn, semaphore = load_store_instruction(buffer_type="ACC", pop_prev_dep=pop_prev_dep, pop_next_dep=pop_next_dep, push_prev_dep=push_prev_dep, push_next_dep=push_next_dep, sram_base=sram_addr, dram_base=first_block_address, y_size=y_size, x_size=block_size, x_stride=stride, semaphore=semaphore)
        insn_buffer.append( new_insn )

    # Load the second accumulator
    if (doAddAcc == True):
        if (idx_gap == -1):
            # Block wise load
            for i, block_idx in enumerate(load_X):
                # Acknowledge LOAD ready signal (first load)
                pop_prev_dep = 0
                # Ready signal to STORE (last load)
                push_next_dep = 1 if (isLastCompute == True) else 0 
                # Ready signal to LOAD (NO GeMM)
                push_prev_dep = 0
                # Nothing else
                pop_next_dep = 0

                # Full block
                # Get the idx of the block in DRAM and the location in SRAM
                current_block_addr = find_logical_block_addr_by_idx(block_idx, add_acc_addr)
                current_sram_base=(nbLoadAcc + i) * block_size

                # INSN LOAD ACC - load a full block_size x block_size matrix
                new_insn, semaphore = load_store_instruction(buffer_type="ACC", pop_prev_dep=pop_prev_dep, pop_next_dep=pop_next_dep, push_prev_dep=push_prev_dep, push_next_dep=push_next_dep, sram_base=current_sram_base, dram_base=current_block_addr, y_size=1, x_size=block_size, x_stride=block_size, semaphore=semaphore)
                insn_buffer.append( new_insn )

        else: # Single load instruction
            # Get the first block address
            first_block_address = find_logical_block_addr_by_idx(load_X[0], add_acc_addr)
            # Sram is 0x0000
            sram_addr = nbLoadAcc * block_size

            # Compute the parameters
            stride = idx_gap * block_size
            y_size = nbLoadAcc

            # Acknowledge LOAD ready signal
            pop_prev_dep = 1
            # Ready signal to STORE
            push_next_dep = 1 if (isLastCompute == True) else 0 
            # Ready signal to LOAD (NO GeMM)
            push_prev_dep = 0 
            # Nothing else
            pop_next_dep = 0

            # INSN LOAD ACC
            new_insn, semaphore = load_store_instruction(buffer_type="ACC", pop_prev_dep=pop_prev_dep, pop_next_dep=pop_next_dep, push_prev_dep=push_prev_dep, push_next_dep=push_next_dep, sram_base=sram_addr, dram_base=first_block_address, y_size=y_size, x_size=block_size, x_stride=stride, semaphore=semaphore)
            insn_buffer.append( new_insn )



    # INSTRUCTION LOAD UOP + GEMM
    isFirstCompute = False if (doLoadAcc == True) else True
    isLastCompute = False if (doAlu == True) else True

    # Get the current uop DRAM address
    current_uop_addr = find_uop_addr(uop_addr, len(uop_buffer), uop_counter)

    # Generate all the UOP
    for gemm_idx in range(0, nb_gemm):
        gemm = step[6][gemm_idx]

        c_sram_idx = block_idx_in_sram(gemm[1], memory_status)
        a_sram_idx = block_idx_in_sram(gemm[2], step[0])
        b_sram_idx = block_idx_in_sram(gemm[3], step[1])

        # UOP
        uop_buffer.append(VTAUop( 
            dst_idx=c_sram_idx * block_size, 
            src_idx=a_sram_idx * block_size,
            wgt_idx=b_sram_idx
        ))

    if (doGemm == True):
        # Number of UOPs
        nb_uop = len(uop_buffer)

        # Check if it fit the UOP buffer
        if (nb_uop < uop_buffer_size):
            # Acknowledge LOAD ready signal (first load)
            pop_prev_dep = 1 if (isFirstCompute == True) else 0 
            # Nothing else
            pop_next_dep = 0
            push_prev_dep = 0
            push_next_dep = 0

            # INSN UOP
            new_insn, semaphore = load_store_instruction(buffer_type="UOP", pop_prev_dep=pop_prev_dep, pop_next_dep=pop_next_dep, push_prev_dep=push_prev_dep, push_next_dep=push_next_dep, sram_base=0, dram_base=current_uop_addr, y_size=1, x_size=nb_uop, x_stride=nb_uop, semaphore=semaphore)
            insn_buffer.append( new_insn )

            # Ready signal to STORE (last compute)
            push_next_dep = 1 if (isLastCompute == True) else 0
            # Ready signal to LOAD (last GeMM)
            push_prev_dep = 1
            # Nothing else
            pop_prev_dep = 0
            pop_next_dep = 0

            # INSN - GEMM
            new_insn, semaphore = gemm_instruction(reset=0, pop_prev_dep=pop_prev_dep, pop_next_dep=pop_next_dep, push_prev_dep=push_prev_dep, push_next_dep=push_next_dep,
                                                   uop_begin=0, uop_end=nb_uop,
                                                   lp_out=1, dst_out=0, src_out=0, wgt_out=0,
                                                   lp_in=block_size, dst_in=1, src_in=1, wgt_in=0,
                                                   semaphore=semaphore)
            insn_buffer.append( new_insn )

        # Else, there are too many UOP
        else: 
            # Define local_nb_uop and capacity
            local_nb_uop = 0
            capacity = uop_buffer_size
            # Iterate over the UOP
            for i, uop in enumerate(uop_buffer):
                # Define the DEP FLAG
                pop_prev_dep = 0
                pop_next_dep = 0
                push_prev_dep = 0
                push_next_dep = 0
                if (i == 0):
                    pop_prev_dep = 1 if (isFirstCompute == True) else 0
                elif (i == nb_uop - 1):
                    push_next_dep = 1 if (isLastCompute == True) else 0
                    push_prev_dep = 1

                # When full, perform the operations
                if (capacity == 0):
                    local_dram = current_uop_addr + (i - local_nb_uop)

                    # INSN UOP
                    new_insn, semaphore = load_store_instruction(buffer_type="UOP", pop_prev_dep=pop_prev_dep, pop_next_dep=0, push_prev_dep=0, push_next_dep=0, sram_base=0, dram_base=local_dram, y_size=1, x_size=local_nb_uop, x_stride=local_nb_uop, semaphore=semaphore)
                    insn_buffer.append( new_insn )

                    # INSN - GEMM
                    new_insn, semaphore = gemm_instruction(reset=0, pop_prev_dep=0, pop_next_dep=0, push_prev_dep=push_prev_dep, push_next_dep=push_next_dep,
                                                           uop_begin=0, uop_end=local_nb_uop,
                                                           lp_out=1, dst_out=0, src_out=0, wgt_out=0,
                                                           lp_in=block_size, dst_in=1, src_in=1, wgt_in=0,
                                                           semaphore={})
                    insn_buffer.append( new_insn )

                    # Reset capacity and local number of uop
                    local_nb_uop = 0
                    capacity = uop_buffer_size
                
                # Increment the capacity and local number of uop
                local_nb_uop = local_nb_uop + 1
                capacity = capacity - 1


    # INSTRUCTION LOAD UOP + ALU
    isFirstCompute = False if (doLoadAcc == True or doGemm == True) else True

    if (doAddAcc == True):
        # UOP
        uop_buffer.append(VTAUop( 
            dst_idx=0, 
            src_idx=nbLoadAcc*block_size,
            wgt_idx=0
        ))
        nb_uop = 1

        # Acknowledge LOAD ready signal (first load)
        pop_prev_dep = 1 if (isFirstCompute == True) else 0 
        # Ready signal to LOAD (first load)
        push_prev_dep = 1 if (isFirstCompute == True) else 0 
        # Nothing else
        pop_next_dep = 0
        push_next_dep = 0

        # INSN LOAD UOP
        new_insn, semaphore = load_store_instruction(buffer_type="UOP", pop_prev_dep=pop_prev_dep, pop_next_dep=pop_next_dep, push_prev_dep=push_prev_dep, push_next_dep=push_next_dep, sram_base=0, dram_base=current_uop_addr, y_size=1, x_size=nb_uop, x_stride=nb_uop, semaphore=semaphore)
        insn_buffer.append( new_insn )

        # Ready signal to STORE 
        push_next_dep = 1
        # Nothing else
        pop_prev_dep = 0
        pop_next_dep = 0
        push_prev_dep = 0

        # INSN - ALU
        alu_opcode = 2 # 0-MIN, 1-MAX, 2-ADD, 3-SHR, 4-MUL
        new_insn, semaphore = alu_instruction(alu_opcode=alu_opcode, pop_prev_dep=pop_prev_dep, pop_next_dep=pop_next_dep, push_prev_dep=push_prev_dep, push_next_dep=push_next_dep,
                                              uop_begin=0, uop_end=nb_uop,
                                              lp_out=nbLoadAcc, dst_out=block_size, src_out=block_size, 
                                              lp_in=block_size, dst_in=1, src_in=1, 
                                              use_imm=0, imm=0,
                                              semaphore=semaphore)
        insn_buffer.append( new_insn )


    else:
        for alu_idx in range(nb_gemm, nb_gemm+nb_alu):
            alu = step[6][alu_idx]
            nb_uop = 0
            
            # Define the opcode
            if (alu[0].startswith("MAX") or alu[0] == "RELU"):
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
                # Current alu: (dst_vector, [src_vector]) where dst_vector and src_vector are tuples
                #           or (block_idx, line)

                # Get dst_vector (tuple) and src_vector (list)
                dst_vector, src_vectors = get_dst_src_from_current_alu(current_alu=current_alu, alu=alu)

                # Check if memory_status is a tuple (vector-wise load)
                if (isinstance(memory_status[0], tuple)):
                    # There is one DST vector for a list of SRC vectors
                    dst_vector_idx = block_idx_in_sram(dst_vector, memory_status)
                    # Iterate on the SRC list
                    for vector in src_vectors:
                        src_vector_idx = block_idx_in_sram(vector, memory_status)
                        # UOP
                        uop_buffer.append(VTAUop( 
                            dst_idx=dst_vector_idx, 
                            src_idx=src_vector_idx,
                            wgt_idx=0
                        ))
                        nb_uop += 1

                # Else it is int -> a block is loaded
                else:
                    # There is one DST vector for a list of SRC vectors
                    dst_block_idx = block_idx_in_sram(dst_vector[0], memory_status) * block_size
                    dst_vector_idx = dst_vector[1] + dst_block_idx
                    # Iterate on the SRC list
                    for vector in src_vectors:
                        src_block_idx = block_idx_in_sram(vector[0], memory_status) * block_size
                        src_vector_idx = vector[1] + src_block_idx
                        # UOP
                        uop_buffer.append(VTAUop( 
                            dst_idx=dst_vector_idx, 
                            src_idx=src_vector_idx,
                            wgt_idx=0
                        ))
                        nb_uop += 1
                
                # If src_vectors is empty -> UOP
                if (len(src_vectors) == 0):
                    # UOP
                    uop_buffer.append(VTAUop( 
                        dst_idx=dst_vector_idx, 
                        src_idx=0,
                        wgt_idx=0
                    ))
                    nb_uop += 1

            # Check if it fit the UOP buffer
            if (nb_uop < uop_buffer_size):
                # Acknowledge LOAD ready signal (first load)
                pop_prev_dep = 1 if (alu_idx == nb_gemm and isFirstCompute == True) else 0 
                # Ready signal to LOAD (first load)
                push_prev_dep = 1 if (alu_idx == nb_gemm and isFirstCompute == True) else 0 
                # Nothing else
                pop_next_dep = 0
                push_next_dep = 0

                # INSN LOAD UOP
                new_insn, semaphore = load_store_instruction(buffer_type="UOP", pop_prev_dep=pop_prev_dep, pop_next_dep=pop_next_dep, push_prev_dep=push_prev_dep, push_next_dep=push_next_dep, sram_base=0, dram_base=current_uop_addr, y_size=1, x_size=nb_uop, x_stride=nb_uop, semaphore=semaphore)
                insn_buffer.append( new_insn )

                # Ready signal to STORE (last alu)
                push_next_dep = 1 if (alu_idx == (nb_gemm+nb_alu) - 1) else 0
                # Nothing else
                pop_prev_dep = 0
                pop_next_dep = 0
                push_prev_dep = 0
        
                # INSN - ALU
                use_imm=1 if (isImm == True) else 0
                imm=imm if (isImm == True) else 0
                new_insn, semaphore = alu_instruction(alu_opcode=alu_opcode, pop_prev_dep=pop_prev_dep, pop_next_dep=pop_next_dep, push_prev_dep=push_prev_dep, push_next_dep=push_next_dep,
                                                      uop_begin=0, uop_end=nb_uop,
                                                      lp_out=1, dst_out=0, src_out=0, 
                                                      lp_in=1, dst_in=0, src_in=0, 
                                                      use_imm=use_imm, imm=imm,
                                                      semaphore=semaphore)
                insn_buffer.append( new_insn )

            
            # Else, there are too many UOP
            else:
                # Define local_nb_uop and capacity
                local_nb_uop = 0
                capacity = uop_buffer_size
                # Iterate over the UOP
                for i in range(0, nb_uop):
                    # Define the DEP FLAG
                    pop_prev_dep = 0
                    pop_next_dep = 0
                    push_prev_dep = 0
                    push_next_dep = 0
                    if (i == 0):
                        pop_prev_dep = 1 if (alu_idx == nb_gemm and isFirstCompute == True) else 0
                        push_prev_dep = 1 if (alu_idx == nb_gemm and isFirstCompute == True) else 0
                    elif (i == nb_uop - 1):
                        push_next_dep = 1 if (alu_idx == (nb_gemm+nb_alu) - 1) else 0

                    # When full, perform the operations
                    if (capacity == 0):
                        local_dram = current_uop_addr + (i - local_nb_uop)

                        # INSN UOP
                        new_insn, semaphore = load_store_instruction(buffer_type="UOP", pop_prev_dep=pop_prev_dep, pop_next_dep=0, push_prev_dep=push_prev_dep, push_next_dep=0, sram_base=0, dram_base=local_dram, y_size=1, x_size=local_nb_uop, x_stride=local_nb_uop, semaphore=semaphore)
                        insn_buffer.append( new_insn )

                        # INSN - ALU
                        use_imm=1 if (isImm == True) else 0
                        imm=imm if (isImm == True) else 0
                        new_insn, semaphore = alu_instruction(alu_opcode=alu_opcode, pop_prev_dep=0, pop_next_dep=0, push_prev_dep=0, push_next_dep=push_next_dep,
                                                              uop_begin=0, uop_end=local_nb_uop,
                                                              lp_out=1, dst_out=0, src_out=0, 
                                                              lp_in=1, dst_in=0, src_in=0, 
                                                              use_imm=use_imm, imm=imm,
                                                              semaphore=semaphore)
                        insn_buffer.append( new_insn )

                        # Reset capacity and local number of uop
                        local_nb_uop = 0
                        capacity = uop_buffer_size
                    
                    # Increment the capacity and local number of uop
                    local_nb_uop = local_nb_uop + 1
                    capacity = capacity - 1



    # If no compute stage
    if (doLoadAcc == False and doGemm == False and doAlu == False):
        # Acknowledge LOAD ready signal
        pop_prev_dep = 1
        # Ready signal to LOAD
        push_prev_dep = 1
        # Ready signal to STORE
        push_next_dep = 1
        # Nothing else
        pop_next_dep = 0

        # INSN - NOP-COMPUTE-STAGE (input: LD->CMP, output: CMP->LD & CMP->ST)
        new_insn, semaphore = nop_stage_instruction(module="COMPUTE", pop_prev_dep=pop_prev_dep, pop_next_dep=pop_next_dep, push_prev_dep=push_prev_dep, push_next_dep=push_next_dep, semaphore=semaphore)
        insn_buffer.append( new_insn )


    # STORE MODULE (input: CMP->LD & CMP->ST, output: CMP->LD)
    # ------------
    to_store = step[5]
    dram_state = step[4]
    nb_out = len(to_store)

    # If nb_out > 0 -> Store
    if (nb_out > 0):
        # Check if to_store is composed of tuple (vector-wise) or integer (block)
        if (isinstance(to_store[0], tuple)):
            for i, dst_vector in enumerate(to_store):
                # Acknowledge COMPUTE ready signal (first store)
                pop_prev_dep = 1 if (i == 0) else 0
                # Ready signal to COMPUTE
                push_prev_dep = 1 if (i == nb_out - 1) else 0

                # Get the SRAM address
                if (isinstance(memory_status[0], tuple)):
                    dst_sram_addr = block_idx_in_sram(dst_vector, memory_status)
                else: 
                    dst_block_idx = block_idx_in_sram(dst_vector[0], memory_status)
                    dst_sram_addr = dst_vector[1] + dst_block_idx * block_size
                
                # Get the DRAM address
                out_dram_base = int( out_addr[0]['logical_base_address'], 16)
                dst_dram_addr = dram_state.index(dst_vector) + out_dram_base

                # INSN STORE OUT - store a vector
                new_insn, semaphore = load_store_instruction(buffer_type="OUT", pop_prev_dep=pop_prev_dep, pop_next_dep=0, push_prev_dep=push_prev_dep, push_next_dep=0, sram_base=dst_sram_addr, dram_base=dst_dram_addr, y_size=1, x_size=1, x_stride=1, semaphore=semaphore)
                insn_buffer.append( new_insn )

        else: 
            for i, block_idx in enumerate(to_store):
                # Get the idx of the block in DRAM and the location in SRAM
                current_block_addr = find_logical_block_addr_by_idx(block_idx, out_addr)
                current_sram_base=0x0000 + i*block_size

                # Acknowledge COMPUTE ready signal (first store)
                pop_prev_dep = 1 if (i == 0) else 0
                # Ready signal to COMPUTE
                push_prev_dep = 1 if (i == nb_out - 1) else 0

                # INSN STORE OUT - store a full block_size x block_size matrix
                new_insn, semaphore = load_store_instruction(buffer_type="OUT", pop_prev_dep=pop_prev_dep, pop_next_dep=0, push_prev_dep=push_prev_dep, push_next_dep=0, sram_base=current_sram_base, dram_base=current_block_addr, y_size=1, x_size=block_size, x_stride=block_size, semaphore=semaphore)
                insn_buffer.append( new_insn )
    
    # Nothing to store
    else: 
        # Acknowledge COMPUTE ready signal (first store)
        pop_prev_dep = 1
        # Ready signal to COMPUTE
        push_prev_dep = 1 

        # INSN - NOP-STORE-STAGE (input: CMP->LD & CMP->ST, output: CMP->LD & ST->CMP)
        new_insn, semaphore = nop_stage_instruction(module="STORE", pop_prev_dep=pop_prev_dep, pop_next_dep=0, push_prev_dep=push_prev_dep, push_next_dep=0, semaphore=semaphore)
        insn_buffer.append( new_insn )


    # COMPUTE MODULE (input: CMP->LD & ST->CMP, output: CMP->LD)
    # --------------
    # Acknowledge STORE ready signal
    pop_next_dep = 1
    # Nothing else
    pop_prev_dep = 0
    push_prev_dep = 0
    push_next_dep = 0

    # INSN - NOP-COMPUTE-STAGE (input: CMP->LD & ST->CMP, output: CMP->LD)
    new_insn, semaphore = nop_stage_instruction(module="COMPUTE", pop_prev_dep=pop_prev_dep, pop_next_dep=pop_next_dep, push_prev_dep=push_prev_dep, push_next_dep=push_next_dep, semaphore=semaphore)
    insn_buffer.append( new_insn )

    # Return the sequences
    return insn_buffer, uop_buffer, semaphore, uop_counter + len(uop_buffer)


# ---------------------------------------------


# TERMINATION SEQUENCE (input: CMP->LD, output: /)
# --------------------
def termination_sequence(semaphore):
    # Init
    insn_buffer = []

    # INSN - NOP-MEMORY-STAGE (LOAD) (input: CMP->LD, output: LD->CMP)
    new_insn,semaphore = nop_stage_instruction(module="LOAD", pop_prev_dep=0, pop_next_dep=1, push_prev_dep=0, push_next_dep=1, semaphore=semaphore)
    insn_buffer.append( new_insn )


    # INSN -  NOP-COMPUTE-STAGE (input: LD->CMP, output: /)
    new_insn, semaphore = nop_stage_instruction(module="COMPUTE", pop_prev_dep=1, pop_next_dep=0, push_prev_dep=0, push_next_dep=0, semaphore=semaphore)
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

# FIND_BLOCK_ADDR_BY_IDX
# ----------------------
def find_logical_block_addr_by_idx(block_idx, addr_dict):
    block_addr_list = addr_dict[0]['blocks_addresses']
    tuple_addr = next(t for t in block_addr_list if t[0] == block_idx)
    return int( tuple_addr[2], 16)

# ---------------------------------------------

# FIND_UOP_ADDR
# -------------
def find_uop_addr(uop_addr, uop_buffer_size, uop_counter):
    uop_logic_addr = int( uop_addr[0]["logical_base_address"], 16)
    current_uop_addr = uop_logic_addr + uop_counter + uop_buffer_size
    return current_uop_addr

# ---------------------------------------------

# BLOCK_IDX_IN_SRAM
# -----------------
def block_idx_in_sram(block_idx, memory_status):
    return memory_status.index(block_idx)

# ---------------------------------------------

# GET_DST_SRC_FROM_CURRENT_ALU
# ----------------------------
def get_dst_src_from_current_alu(current_alu, alu):
    """
    Obtain the DST vector and the SRC vector from an ALU operations
    Input:
        - current_alu (tuple): Either (block_idx, vector_idx) or ((block_idx, vector_idx), [list of src vectors])
        - alu (list): The ALU definition ['OP_NAME', [param], [list of tuples]]
    Output:
        - dst_vector (tuple): The DST vector extracted from the list of vectors
        - src_vector (list): The list of SRC vector extracted from the list of vectors
    """
    # If it is a vector-scalar operation: just a DST vector
    if (alu[0].endswith("_IMM") or alu[0] == "RELU"):
        dst_vector = current_alu
        src_vector = []
    
    # If vector-vector operation: [dst_vector, [src_vectors]]
    else:
        dst_vector = current_alu[0]
        src_vector = current_alu[1]

    return dst_vector, src_vector

# ---------------------------------------------

# HECK_CONSTANT_GAP
# -----------------
def check_constant_gap(numbers: list) -> int:
    """
    Checks if the gap between consecutive elements in a list is constant.
    Args:
        numbers: A list of integers.
    Returns:
        The value of the constant gap if it exists, otherwise -1.
    """
    # A gap cannot be calculated on a list with fewer than 2 elements.
    if len(numbers) < 2:
        return -1
    
    # If it is a tuple, return 1
    if isinstance(numbers[0], tuple):
        return -1

    # Calculate the reference gap using the first two elements.
    expected_gap = numbers[1] - numbers[0]

    # Loop through the rest of the list starting from the third element.
    for i in range(2, len(numbers)):
        # If the current gap is different from the expected one, return -1.
        if numbers[i] - numbers[i-1] != expected_gap:
            return -1

    # If the loop finishes, all gaps are constant.
    return expected_gap
