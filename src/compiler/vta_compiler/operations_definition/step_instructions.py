# IMPORT PACKAGES
# ---------------
try:
    from structures import *
    from utils_operations import *
    from instructions_template import *
except:
    from operations_definition.structures import *
    from operations_definition.utils_operations import *
    from operations_definition.instructions_template import *


###############################################


# STEP LOAD
# ---------
def step_load(load_A, load_B, inp_addr, wgt_addr, block_size, semaphore):
    # Init buffer 
    insn_buffer = []

    # Get the number of load
    nb_inp = len(load_A)
    nb_wgt = len(load_B)

    # Check the semaphore
    cmp_ld_signal = semaphore["CMP->LD"]
    ld_cmp_signal = semaphore["LD->CMP"]

    # Set the COMPUTE acknowledge signal
    if (cmp_ld_signal > 0): 
        # There is a signal to acknowledge
        ack_signal = 1
    else: 
        # Nothing to acknowledge
        ack_signal = 0

    # Set the LOAD ready signal to COMPUTE
    if (ld_cmp_signal > 0): 
        # The signal already exist
        ready_signal = 0
    else: 
        # Nothing to acknowledge
        ready_signal = 1
    

    # LOAD INP
    # ---
    # Get the gap between each idx
    idx_gap = check_constant_gap(load_A)
    # If the gap is not constant -> block wise load
    if (idx_gap == -1):
        for i, block_idx in enumerate(load_A):
            # Get the idx of the block in DRAM and the location in SRAM
            current_block_addr = find_logical_block_addr_by_idx(block_idx, inp_addr)
            current_sram_base = 0x0000 + i*block_size

            # Acknowledge COMPUTE ready signal (first load)
            pop_next_dep = ack_signal if (i == 0) else 0 
            # Ready signal to COMPUTE if no WGT load (last load)
            push_next_dep = ready_signal if (i == nb_inp-1 and nb_wgt == 0) else 0 

            # INSN LOAD INP - load a full block_size x block_size matrix
            new_insn, semaphore = load_store_instruction(buffer_type="INP", pop_prev_dep=0, pop_next_dep=pop_next_dep, push_prev_dep=0, push_next_dep=push_next_dep, sram_base=current_sram_base, dram_base=current_block_addr, y_size=1, x_size=block_size, x_stride=block_size, semaphore=semaphore)
            insn_buffer.append( new_insn )
    # If the gap is constant -> single load instruction
    else:
        # Get the first block address
        first_block_address = find_logical_block_addr_by_idx(load_A[0], inp_addr)
        # Sram is 0x0000
        sram_addr = 0x0000

        # Compute the parameters
        stride = idx_gap * block_size
        x_size = block_size
        y_size = nb_inp

        # Acknowledge COMPUTE ready signal
        pop_next_dep = ack_signal
        # Ready signal to COMPUTE if no WGT load 
        push_next_dep = ready_signal if (nb_wgt == 0) else 0  

        # INSN LOAD INP
        new_insn, semaphore = load_store_instruction(buffer_type="INP", pop_prev_dep=0, pop_next_dep=pop_next_dep, push_prev_dep=0, push_next_dep=push_next_dep, sram_base=sram_addr, dram_base=first_block_address, y_size=y_size, x_size=x_size, x_stride=stride, semaphore=semaphore)
        insn_buffer.append( new_insn )
    

    # LOAD WGT
    # ---
    # Get the gap between each idx
    idx_gap = check_constant_gap(load_B)
    # If the gap is not constant -> block wise load
    if (idx_gap == -1):
        for i, block_idx in enumerate(load_B):
            # Get the idx of the block in DRAM and the location in SRAM
            current_block_addr = find_logical_block_addr_by_idx(block_idx, wgt_addr)
            current_sram_base = 0x0000 + i

            # Acknowledge COMPUTE ready signal (first load)
            pop_next_dep = ack_signal if (i == 0 and nb_inp == 0) else 0 
            # Ready signal to COMPUTE if no WGT load (last load)
            push_next_dep = ready_signal if (i == nb_wgt-1) else 0 

            # INSN LOAD INP - load a full block_size x block_size matrix
            new_insn, semaphore = load_store_instruction(buffer_type="WGT", pop_prev_dep=0, pop_next_dep=pop_next_dep, push_prev_dep=0, push_next_dep=push_next_dep, sram_base=current_sram_base, dram_base=current_block_addr, y_size=1, x_size=1, x_stride=1, semaphore=semaphore)
            insn_buffer.append( new_insn )
    # If the gap is constant -> single load instruction
    else:
        # Get the first block address
        first_block_address = find_logical_block_addr_by_idx(load_B[0], wgt_addr)
        # Sram is 0x0000
        sram_addr = 0x0000

        # Compute the parameters
        stride = idx_gap
        x_size = 1
        y_size = nb_wgt

        # Acknowledge COMPUTE ready signal if no INP load
        pop_next_dep = ack_signal if (nb_inp == 0) else 0
        # Ready signal to COMPUTE 
        push_next_dep = ready_signal

        # INSN LOAD WGT
        new_insn, semaphore = load_store_instruction(buffer_type="WGT", pop_prev_dep=0, pop_next_dep=pop_next_dep, push_prev_dep=0, push_next_dep=push_next_dep, sram_base=sram_addr, dram_base=first_block_address, y_size=y_size, x_size=x_size, x_stride=stride, semaphore=semaphore)
        insn_buffer.append( new_insn )


    # Return
    # ---
    return insn_buffer, semaphore

# ---------------------------------------------

# STEP LOAD ACC
# -------------
def step_load_acc(load_X, sram_state, acc_addr, acc_bis_addr, block_size, semaphore):
    # Init the buffer
    insn_buffer = []

    # Get the number of load
    nb_acc = len(load_X)

    # Check the semaphore
    cmp_ld_signal = semaphore["CMP->LD"]
    ld_cmp_signal = semaphore["LD->CMP"]
    cmp_st_signal = semaphore["CMP->ST"]
    st_cmp_signal = semaphore["ST->CMP"]

    # Set the COMPUTE ready signal to LOAD -> never (done by operational core)
    prev_ready_signal = 0

    # Set the LOAD acknowledge signal
    if (ld_cmp_signal > 0): 
        # Acknowledge
        prev_ack_signal = 1
    else: 
        # Nothing to acknowledge
        prev_ack_signal = 0

    # Set the COMPUTE ready signal to STORE -> never (done by operational core)
    next_ready_signal = 0

    # Set the STORE acknowledge signal
    if (st_cmp_signal > 0): 
        # Acknowledge
        next_ack_signal = 1
    else: 
        # Nothing to acknowledge
        next_ack_signal = 0
    

    # LOAD ACC
    # ---
    # Get the gap between each idx
    idx_gap = check_constant_gap(load_X)
    if (idx_gap == -1):
        # Block wise load
        for i, block_idx in enumerate(load_X):
            # Semaphore
            pop_prev_dep = prev_ack_signal if (i == 0) else 0 
            pop_next_dep = next_ack_signal if (i == 0) else 0
            push_next_dep = next_ready_signal # -> 0
            push_prev_dep = prev_ready_signal # -> 0

            # Check if block_idx is a tuple (i.e., a vector)
            if isinstance(block_idx, tuple):
                # Get the idx of the block in DRAM and the location in SRAM
                current_block_addr = find_logical_block_addr_by_idx(block_idx[0], acc_addr)
                current_dram = current_block_addr + block_idx[1]

                # Get the SRAM base find 
                sram_base = block_idx_in_sram(block_idx, sram_state)
                current_sram_base=sram_base

                # INSN LOAD ACC - load a full block_size x block_size matrix
                new_insn, semaphore = load_store_instruction(buffer_type="ACC", pop_prev_dep=pop_prev_dep, pop_next_dep=pop_next_dep, push_prev_dep=push_prev_dep, push_next_dep=push_next_dep, sram_base=current_sram_base, dram_base=current_dram, y_size=1, x_size=1, x_stride=1, semaphore=semaphore)
                insn_buffer.append( new_insn )

            # Or an int (i.e., a full block)
            else: 
                # Get the idx of the block in DRAM and the location in SRAM
                current_block_addr = find_logical_block_addr_by_idx(block_idx, acc_addr)
                current_sram_base=0x0000 + i*block_size

                # INSN LOAD ACC - load a full block_size x block_size matrix
                new_insn, semaphore = load_store_instruction(buffer_type="ACC", pop_prev_dep=pop_prev_dep, pop_next_dep=pop_next_dep, push_prev_dep=push_prev_dep, push_next_dep=push_next_dep, sram_base=current_sram_base, dram_base=current_block_addr, y_size=1, x_size=block_size, x_stride=block_size, semaphore=semaphore)
                insn_buffer.append( new_insn )

    # If the gap is constant (i.e., load blocks) -> single load instruction
    else:
        # Get the first block address
        first_block_address = find_logical_block_addr_by_idx(load_X[0], acc_addr)
        # Sram is 0x0000
        sram_addr = 0x0000

        # Compute the parameters
        stride = idx_gap * block_size
        x_size = block_size
        y_size = nb_acc

        # Semaphore
        pop_prev_dep = prev_ack_signal
        pop_next_dep = next_ack_signal
        push_next_dep = next_ready_signal # -> 0
        push_prev_dep = prev_ready_signal # -> 0

        # INSN LOAD ACC
        new_insn, semaphore = load_store_instruction(buffer_type="ACC", pop_prev_dep=pop_prev_dep, pop_next_dep=pop_next_dep, push_prev_dep=push_prev_dep, push_next_dep=push_next_dep, sram_base=sram_addr, dram_base=first_block_address, y_size=y_size, x_size=x_size, x_stride=stride, semaphore=semaphore)
        insn_buffer.append( new_insn )
 

    # LOAD ACC BIS
    # ---
    if (len(acc_bis_addr) > 0):
        # Semaphore (nothing)
        pop_prev_dep = 0
        pop_next_dep = 0
        push_prev_dep = 0
        push_next_dep = 0

        if (idx_gap == -1):
            # Block wise load
            for i, block_idx in enumerate(load_X):

                # Full block
                # Get the idx of the block in DRAM and the location in SRAM
                current_block_addr = find_logical_block_addr_by_idx(block_idx, acc_bis_addr)
                current_sram_base=(nb_acc + i) * block_size

                # INSN LOAD ACC - load a full block_size x block_size matrix
                new_insn, semaphore = load_store_instruction(buffer_type="ACC", pop_prev_dep=pop_prev_dep, pop_next_dep=pop_next_dep, push_prev_dep=push_prev_dep, push_next_dep=push_next_dep, sram_base=current_sram_base, dram_base=current_block_addr, y_size=1, x_size=block_size, x_stride=block_size, semaphore=semaphore)
                insn_buffer.append( new_insn )

        else: # Single load instruction
            # Get the first block address
            first_block_address = find_logical_block_addr_by_idx(load_X[0], acc_bis_addr)
            # Sram is 0x0000
            sram_addr = nb_acc * block_size

            # Compute the parameters
            stride = idx_gap * block_size
            x_size = block_size
            y_size = nb_acc

            # INSN LOAD ACC
            new_insn, semaphore = load_store_instruction(buffer_type="ACC", pop_prev_dep=pop_prev_dep, pop_next_dep=pop_next_dep, push_prev_dep=push_prev_dep, push_next_dep=push_next_dep, sram_base=sram_addr, dram_base=first_block_address, y_size=y_size, x_size=x_size, x_stride=stride, semaphore=semaphore)
            insn_buffer.append( new_insn )


    # Return
    # ---
    return insn_buffer, semaphore

# ---------------------------------------------

# STEP COMPUTE
# ------------
def step_compute(ops, load_A, load_B, load_X, sram_state, uop_addr, uop_buffer_size, uop_counter, doStore, block_size, semaphore):
    # Init the buffers
    insn_buffer = []
    uop_buffer = []

    # Get the number of ops
    nb_ops = len(ops)

    # Check the semaphore
    cmp_ld_signal = semaphore["CMP->LD"]
    ld_cmp_signal = semaphore["LD->CMP"]
    cmp_st_signal = semaphore["CMP->ST"]
    st_cmp_signal = semaphore["ST->CMP"]

    # Set the COMPUTE ready signal to LOAD 
    if (cmp_ld_signal > 0): 
        # Already send (nothing to send)
        prev_ready_signal = 0
    else: 
        # Send ready signal
        prev_ready_signal = 1

    # Set the LOAD acknowledge signal
    if (ld_cmp_signal > 0): 
        # Acknowledge
        prev_ack_signal = 1
    else: 
        # Nothing to acknowledge
        prev_ack_signal = 0

    # Set the COMPUTE ready signal to STORE
    if (cmp_st_signal < 1 and doStore == True): 
        # Send ready signal
        next_ready_signal = 1
    else: 
        # Nothing to do
        next_ready_signal = 0

    # Set the STORE acknowledge signal
    if (st_cmp_signal > 0): 
        # Acknowledge
        next_ack_signal = 1
    else: 
        # Nothing to acknowledge
        next_ack_signal = 0


    # ITERATE OVER THE OPS
    # ---
    # GeMM instructions (UOP + INSN)
    nb_gemm = 0
    for idx_op, op in enumerate(ops):
        # Check if it is a GeMM
        if (op[0] == "GeMM"):
            nb_gemm += 1

            # Define the UOP idx
            c_sram_idx = block_idx_in_sram(op[1], sram_state)
            a_sram_idx = block_idx_in_sram(op[2], load_A)
            if (len(load_B) > 0):
                b_sram_idx = block_idx_in_sram(op[3], load_B)
            else:
                # Multiply with a constant (B0 diagonal matrix)
                b_sram_idx = 0

            # UOP
            uop_buffer.append(VTAUop( 
                dst_idx=c_sram_idx * block_size, 
                src_idx=a_sram_idx * block_size,
                wgt_idx=b_sram_idx
            ))
            continue
        # Else it is ALU
        else:
            nb_gemm = idx_op
            break

    # INSN - GEMM
    if (nb_gemm > 0):
        # Manage the semaphore
        pop_prev_dep = prev_ack_signal
        pop_next_dep = next_ack_signal
        push_prev_dep = prev_ready_signal

        if (nb_gemm >= nb_ops):
            push_next_dep = next_ready_signal
        else: 
            push_next_dep = 0

        # Get the current uop address
        current_uop_addr = find_uop_addr(uop_addr, 0, uop_counter)

        # GeMM instructions
        new_insn, semaphore = compute_core(submodule="GEMM", nb_uop=nb_gemm, current_uop_addr=current_uop_addr, 
                                           uop_buffer_size=uop_buffer_size, block_size=block_size,
                                           alu_opcode=0, use_imm=0, imm=0,
                                           pop_prev_dep=pop_prev_dep, pop_next_dep=pop_next_dep, push_prev_dep=push_prev_dep, push_next_dep=push_next_dep,
                                           semaphore=semaphore)
        insn_buffer = insn_buffer + new_insn


    # INSN - ALU
    if (nb_ops > nb_gemm):
        for idx_op in range(nb_gemm, nb_ops):
            op = ops[idx_op]

            # Manage the semaphore
            if (idx_op == 0):
                pop_prev_dep = prev_ack_signal
                pop_next_dep = next_ack_signal
                push_prev_dep = prev_ready_signal
            else: 
                pop_prev_dep = 0
                pop_next_dep = 0
                push_prev_dep = 0

            if (idx_op == nb_ops - 1):
                push_next_dep = next_ready_signal
            else: 
                push_next_dep = 0


            # Get the ALU opcode
            op_name = op[0]
            if (op_name.startswith("MAX") or op_name == "RELU"):
                alu_opcode = 1
            elif (op_name.startswith("MIN")):
                alu_opcode = 0
            elif (op_name.startswith("ADD")):
                alu_opcode = 2
            elif (op_name.startswith("MUL")):
                alu_opcode = 4
            elif (op_name.startswith("SHR")):
                alu_opcode = 3
            else:
                raise Exception(f"ERROR: ALU non-supported operations ({op_name})! \n\n")
            
            # Define if it is immediate
            imm = 0
            use_imm = 0
            if (op_name.endswith("_IMM") or op_name == "RELU"):
                imm = op[1][1]
                use_imm = 1

            # Get the current uop address
            current_uop_addr = find_uop_addr(uop_addr, len(uop_buffer), uop_counter)

            # Set the nb of uop
            nb_uop = 0

            # Check if we perform operations over 2 matrices
            if (op_name == "ADD_ACC"):
                # Get the len of load_X
                nb_acc = len(load_X)

                # Create the UOP
                uop_buffer.append(VTAUop( 
                    dst_idx=0, 
                    src_idx=nb_acc * block_size,
                    wgt_idx=0
                ))
                nb_uop = 1

                new_insn, semaphore = compute_core(submodule="ALU", nb_acc=nb_acc, nb_uop=nb_uop, current_uop_addr=current_uop_addr, 
                                                uop_buffer_size=uop_buffer_size, block_size=block_size,
                                                alu_opcode=alu_opcode, use_imm=0, imm=0,
                                                pop_prev_dep=pop_prev_dep, pop_next_dep=pop_next_dep, push_prev_dep=push_prev_dep, push_next_dep=push_next_dep,
                                                semaphore=semaphore)
                insn_buffer = insn_buffer + new_insn

                # Pass to the next loop
                continue

            # Else, perform vector operations

            # Get the lists of tuples (Either (block_idx, vector_idx) or ((block_idx, vector_idx), [list of src vectors]))
            alu_ops = op[2]

            # Create the UOP (iterate over the tuple)
            for alu_idx, current_alu in enumerate(alu_ops):
                # Current alu: (dst_vector, [src_vector]) where dst_vector and src_vector are tuples
                #           or (block_idx, line)

                # Get dst_vector (tuple) and src_vector (list)
                dst_vector, src_vectors = get_dst_src_from_current_alu(current_alu=current_alu, alu=op)

               

                # Check if memory_status is a tuple (vector-wise load)
                if (isinstance(sram_state[0], tuple)):
                    # There is one DST vector for a list of SRC vectors
                    dst_vector_idx = block_idx_in_sram(dst_vector, sram_state)
                    # Iterate on the SRC list
                    for vector in src_vectors:
                        src_vector_idx = block_idx_in_sram(vector, sram_state)
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
                    dst_block_idx = block_idx_in_sram(dst_vector[0], sram_state) * block_size
                    dst_vector_idx = dst_vector[1] + dst_block_idx
                    # Iterate on the SRC list
                    for vector in src_vectors:
                        src_block_idx = block_idx_in_sram(vector[0], sram_state) * block_size
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

            # ALU instructions
            new_insn, semaphore = compute_core(submodule="ALU", nb_acc=0, nb_uop=nb_uop, current_uop_addr=current_uop_addr, 
                                            uop_buffer_size=uop_buffer_size, block_size=block_size,
                                            alu_opcode=alu_opcode, use_imm=use_imm, imm=imm,
                                            pop_prev_dep=pop_prev_dep, pop_next_dep=pop_next_dep, push_prev_dep=push_prev_dep, push_next_dep=push_next_dep,
                                            semaphore=semaphore)
            insn_buffer = insn_buffer + new_insn

    # Return
    # ---
    return insn_buffer, uop_buffer, semaphore

# ---------------------------------------------

# STEP STORE
# ----------
def step_store(store_C, sram_state, dram_state, out_addr, block_size, semaphore):
    # Init the buffer
    insn_buffer = []

    # Get the number of elements to store
    nb_out = len(store_C)

    # Get the addr

    # Check the semaphore
    cmp_st_signal = semaphore["CMP->ST"]
    st_cmp_signal = semaphore["ST->CMP"]

    # Set the COMPUTE acknowledge signal
    if (cmp_st_signal > 0): 
        # There is a signal to acknowledge
        ack_signal = 1
    else: 
        # Nothing to acknowledge
        ack_signal = 0

    # Set the LOAD ready signal to COMPUTE
    if (st_cmp_signal > 0): 
        # The signal already exist
        ready_signal = 0
    else: 
        # Nothing to acknowledge
        ready_signal = 1

    # STORE OUT
    # ---
    # If nb_out > 0 -> Store
    if (nb_out > 0):
        # Check if to_store is composed of tuple (vector-wise) or integer (block)
        if (isinstance(store_C[0], tuple)):
            for i, dst_vector in enumerate(store_C):
                # Acknowledge COMPUTE ready signal (first store)
                pop_prev_dep = ack_signal if (i == 0) else 0
                # Ready signal to COMPUTE
                push_prev_dep = ready_signal if (i == nb_out - 1) else 0

                # Get the SRAM address
                if (isinstance(sram_state[0], tuple)):
                    dst_sram_addr = block_idx_in_sram(dst_vector, sram_state)
                else: 
                    dst_block_idx = block_idx_in_sram(dst_vector[0], sram_state)
                    dst_sram_addr = dst_vector[1] + dst_block_idx * block_size
                
                # Get the DRAM address
                out_dram_base = int( out_addr[0]['logical_base_address'], 16)
                dst_dram_addr = dram_state.index(dst_vector) + out_dram_base

                # INSN STORE OUT - store a vector
                new_insn, semaphore = load_store_instruction(buffer_type="OUT", pop_prev_dep=pop_prev_dep, pop_next_dep=0, push_prev_dep=push_prev_dep, push_next_dep=0, sram_base=dst_sram_addr, dram_base=dst_dram_addr, y_size=1, x_size=1, x_stride=1, semaphore=semaphore)
                insn_buffer.append( new_insn )

        else: 
            for i, block_idx in enumerate(store_C):
                # Get the idx of the block in DRAM and the location in SRAM
                current_block_addr = find_logical_block_addr_by_idx(block_idx, out_addr)
                current_sram_base=0x0000 + i*block_size

                # Acknowledge COMPUTE ready signal (first store)
                pop_prev_dep = ack_signal if (i == 0) else 0
                # Ready signal to COMPUTE
                push_prev_dep = ready_signal if (i == nb_out - 1) else 0

                # INSN STORE OUT - store a full block_size x block_size matrix
                new_insn, semaphore = load_store_instruction(buffer_type="OUT", pop_prev_dep=pop_prev_dep, pop_next_dep=0, push_prev_dep=push_prev_dep, push_next_dep=0, sram_base=current_sram_base, dram_base=current_block_addr, y_size=1, x_size=block_size, x_stride=block_size, semaphore=semaphore)
                insn_buffer.append( new_insn )
    

    # Return
    # ---
    return insn_buffer, semaphore


###############################################


# COMPUTE_CORE
# ------------
def compute_core(submodule="GEMM", nb_acc=0, nb_uop=1, current_uop_addr=0, 
                 uop_buffer_size=8192, block_size=16,
                 alu_opcode=0, use_imm=0, imm=0,
                 pop_prev_dep=0, pop_next_dep=0, push_prev_dep=0, push_next_dep=0,
                 semaphore={}):
    # Init
    insn_buffer = []

    # Check if it fit the UOP buffer
    if (nb_uop < uop_buffer_size):

        # INSN UOP
        new_insn, semaphore = load_store_instruction(buffer_type="UOP", pop_prev_dep=pop_prev_dep, pop_next_dep=pop_next_dep, push_prev_dep=0, push_next_dep=0, sram_base=0, dram_base=current_uop_addr, y_size=1, x_size=nb_uop, x_stride=nb_uop, semaphore=semaphore)
        insn_buffer.append( new_insn )

        # Check the submodule
        if (submodule == "GEMM"):
            # INSN - GEMM
            new_insn, semaphore = gemm_instruction(reset=0, pop_prev_dep=0, pop_next_dep=0, push_prev_dep=push_prev_dep, push_next_dep=push_next_dep,
                                                  uop_begin=0, uop_end=nb_uop,
                                                  lp_out=1, dst_out=0, src_out=0, wgt_out=0,
                                                  lp_in=block_size, dst_in=1, src_in=1, wgt_in=0,
                                                  semaphore=semaphore)
        elif (submodule == "ALU"):
            # Check if it is two matrices
            if (nb_acc > 0): 
                # INSN - ALU
                new_insn, semaphore = alu_instruction(alu_opcode=alu_opcode, pop_prev_dep=0, pop_next_dep=0, push_prev_dep=push_prev_dep, push_next_dep=push_next_dep,
                                                      uop_begin=0, uop_end=nb_uop,
                                                      lp_out=nb_acc, dst_out=block_size, src_out=block_size, 
                                                      lp_in=block_size, dst_in=1, src_in=1, 
                                                      use_imm=use_imm, imm=imm,
                                                      semaphore=semaphore)

            # Else, single ACC matrix
            else: 
                # INSN - ALU
                new_insn, semaphore = alu_instruction(alu_opcode=alu_opcode, pop_prev_dep=0, pop_next_dep=0, push_prev_dep=push_prev_dep, push_next_dep=push_next_dep,
                                                      uop_begin=0, uop_end=nb_uop,
                                                      lp_out=1, dst_out=0, src_out=0, 
                                                      lp_in=1, dst_in=0, src_in=0, 
                                                      use_imm=use_imm, imm=imm,
                                                      semaphore=semaphore)
        else:
            raise Exception(f"ERROR: Non-supported compute submodule ({submodule}), can accept only 'GEMM' or 'ALU'! \n\n")
        
        # Append the INSN buffer
        insn_buffer.append( new_insn )

    # Else, there are too many UOP
    else: 
        # Define local_nb_uop and capacity
        local_nb_uop = 0
        capacity = uop_buffer_size
        
        # Iterate over the UOP
        for i in range(0, nb_uop):
            # Manage the semaphore
            if (i == 0):
                pop_prev_flag = pop_prev_dep
                pop_next_flag = pop_next_dep
            else:
                pop_prev_flag = 0
                pop_next_flag = 0

            if (i == nb_uop - 1):
                push_prev_flag = push_prev_dep
                push_next_flag = push_next_dep
            else:
                push_prev_flag = 0
                push_next_flag = 0
            

            # When full, perform the operations
            if (capacity == 0):
                local_dram = current_uop_addr + (i - local_nb_uop)

                # INSN UOP
                new_insn, semaphore = load_store_instruction(buffer_type="UOP", pop_prev_dep=pop_prev_flag, pop_next_dep=pop_next_flag, push_prev_dep=0, push_next_dep=0, sram_base=0, dram_base=local_dram, y_size=1, x_size=local_nb_uop, x_stride=local_nb_uop, semaphore=semaphore)
                insn_buffer.append( new_insn )
                
                # Check the submodule
                if (submodule == "GEMM"):
                    # INSN - GEMM
                    new_insn, semaphore = gemm_instruction(reset=0, pop_prev_dep=0, pop_next_dep=0, push_prev_dep=push_prev_flag, push_next_dep=push_next_flag,
                                                           uop_begin=0, uop_end=local_nb_uop,
                                                           lp_out=1, dst_out=0, src_out=0, wgt_out=0,
                                                           lp_in=block_size, dst_in=1, src_in=1, wgt_in=0,
                                                           semaphore={})
                elif (submodule == "ALU"):
                    # Check if it is two matrices
                    if (nb_acc > 0): 
                        # INSN - ALU
                        new_insn, semaphore = alu_instruction(alu_opcode=alu_opcode, pop_prev_dep=0, pop_next_dep=0, push_prev_dep=push_prev_flag, push_next_dep=push_next_flag,
                                                            uop_begin=0, uop_end=local_nb_uop,
                                                            lp_out=nb_acc, dst_out=block_size, src_out=block_size, 
                                                            lp_in=block_size, dst_in=1, src_in=1, 
                                                            use_imm=use_imm, imm=imm,
                                                            semaphore=semaphore)

                    # Else, single ACC matrix
                    else: 
                        # INSN - ALU
                        new_insn, semaphore = alu_instruction(alu_opcode=alu_opcode, pop_prev_dep=0, pop_next_dep=0, push_prev_dep=push_prev_flag, push_next_dep=push_next_flag,
                                                              uop_begin=0, uop_end=local_nb_uop,
                                                              lp_out=1, dst_out=0, src_out=0, 
                                                              lp_in=1, dst_in=0, src_in=0, 
                                                              use_imm=use_imm, imm=imm,
                                                              semaphore=semaphore)
                else:
                    raise Exception(f"ERROR: Non-supported compute submodule ({submodule}), can accept only 'GEMM' or 'ALU'! \n\n")
                
                # Append the INSN buffer
                insn_buffer.append( new_insn )

                # Reset capacity and local number of uop
                local_nb_uop = 0
                capacity = uop_buffer_size
            
            # Increment the capacity and local number of uop
            local_nb_uop = local_nb_uop + 1
            capacity = capacity - 1

    return insn_buffer, semaphore

