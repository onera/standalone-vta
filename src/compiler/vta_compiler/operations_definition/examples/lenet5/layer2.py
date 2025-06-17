# PACKAGE IMPORT
# --------------
import os
import sys

# Parent folder
current_dir = os.path.dirname(os.path.abspath(__file__))
source_dir = os.path.join(current_dir, '../../')
sys.path.insert(0, source_dir)

from structures_insn_uop import *

# -----------------------------------------------------------

# FILENAME
# --------
file_uop_path = filepath_definition("uop_L2.bin")
file_insn_path = filepath_definition("instructions_L2.bin")

# -----------------------------------------------------------

# UOP DEFINITION
# --------------
# Define empty UOP buffer
uop_buffer = []

# Append the buffer with the UOPs
uop_buffer.append(VTAUop( # UOP 0 - reset
    dst_idx=0, 
    src_idx=0,
    wgt_idx=0
))

# UOP 1 -> 10 GEMM
for i in range (0, 10):
    uop_buffer.append(VTAUop(
        dst_idx=0, 
        src_idx=i*16,
        wgt_idx=i
    ))

uop_buffer.append(VTAUop( # UOP 11 - ALU (relu)
    dst_idx=0, 
    src_idx=0,
    wgt_idx=0
))

uop_buffer.append(VTAUop( # UOP 12 - ALU (first add)
    dst_idx=0, 
    src_idx=1, # To add 0x0 with 0x1 and so on
    wgt_idx=0
))

uop_buffer.append(VTAUop( # UOP 13 - ALU (second add)
    dst_idx=0, 
    src_idx=10, # The second line in the tensor
    wgt_idx=0
))

uop_buffer.append(VTAUop( # UOP 14 - ALU (shift right)
    dst_idx=0, 
    src_idx=0,
    wgt_idx=0
))

# Write the UOP in the binary file
with open(file_uop_path, "wb") as f:
    for uop in uop_buffer:
        f.write(uop)

# -----------------------------------------------------------

# INSTRUCTION DEFINITION
# ----------------------
# Define empty instruction buffer
insn_buffer = []

# Append the buffer with the instructions
insn_buffer.append(VTAMemInsn( # I0: LOAD UOP
    opcode=0, # 0-LOAD, 1-STORE, 3-FINISH
    # DEP FLAG
    pop_prev_dep=0,
    pop_next_dep=0,
    push_prev_dep=0,
    push_next_dep=0,
    # Memory interaction
    buffer_id=0, # 0-UOP, 1-WGT, 2-INP, 3-ACC, 4-OUT, 5-ACC8bit
    sram_base=0x0000,
    dram_base=0x00007400, # TODO: modify to implement full LeNet-5
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
    uop_bgn=0, # UOP 0
    uop_end=1,
    loop_out=7,
    loop_in=16,
    # UNUSED
    unused=0, # UNUSED
    # Index factors
    dst_factor_out=16,
    dst_factor_in=1,
    src_factor_out=0,
    src_factor_in=0,
    wgt_factor_out=0,
    wgt_factor_in=0
))

insn_buffer.append(VTAMemInsn( # I2: LOAD INP
    opcode=0, # 0-LOAD, 1-STORE, 3-FINISH
    # DEP FLAG
    pop_prev_dep=0,
    pop_next_dep=1, # Acknowledge COMPUTE ready signal
    push_prev_dep=0,
    push_next_dep=0,
    # Memory interaction
    buffer_id=2, # 0-UOP, 1-WGT, 2-INP, 3-ACC, 4-OUT, 5-ACC8bit
    sram_base=0x0000,
    dram_base=0x00000100,
    unused=0, # UNUSED
    # Operation over the data
    y_size=1,
    x_size=70*16, 
    x_stride=70*16,
    y_pad_top=0,
    y_pad_bottom=0,
    x_pad_left=0,
    x_pad_right=0
))

insn_buffer.append(VTAMemInsn( # I3: LOAD WGT
    opcode=0, # 0-LOAD, 1-STORE, 3-FINISH
    # DEP FLAG
    pop_prev_dep=0,
    pop_next_dep=0,
    push_prev_dep=0,
    push_next_dep=1, # Ready signal to COMPUTE
    # Memory interaction
    buffer_id=1, # 0-UOP, 1-WGT, 2-INP, 3-ACC, 4-OUT, 5-ACC8bit
    sram_base=0x0000,
    dram_base=0x00000090, # TODO: modify to implement full LeNet-5
    unused=0, # UNUSED
    # Operation over the data
    y_size=1,
    x_size=10, 
    x_stride=10,
    y_pad_top=0,
    y_pad_bottom=0,
    x_pad_left=0,
    x_pad_right=0
))

insn_buffer.append(VTAMemInsn( # I4: LOAD UOP
    opcode=0, # 0-LOAD, 1-STORE, 3-FINISH
    # DEP FLAG
    pop_prev_dep=1, # Acknowledge LOAD ready signal
    pop_next_dep=0, 
    push_prev_dep=0,
    push_next_dep=0,
    # Memory interaction
    buffer_id=0, # 0-UOP, 1-WGT, 2-INP, 3-ACC, 4-OUT, 5-ACC8bit
    sram_base=0x0001,
    dram_base=0x00007401, # TODO: modify to implement full LeNet-5
    unused=0, # UNUSED
    # Operation over the data
    y_size=1,
    x_size=14, # Load 11 UOP (10 GEMM + 1 RELU + 3 AvgPool)
    x_stride=14,
    y_pad_top=0,
    y_pad_bottom=0,
    x_pad_left=0,
    x_pad_right=0
))

insn_buffer.append(VTAGemInsn( # I5: GEMM
    opcode=2, # 2-GEMM
    # DEP FLAG
    pop_prev_dep=0,
    pop_next_dep=0,
    push_prev_dep=0,
    push_next_dep=0, 
    # Operations
    reset=0, # 0-no, 1-reset
    uop_bgn=1, # UOP 1 -> 10
    uop_end=11,
    loop_out=7, # 7 out blocks
    loop_in=16,
    # UNUSED
    unused=0, # UNUSED
    # Index factors
    dst_factor_out=16,
    dst_factor_in=1,
    src_factor_out=10*16, # Number of UOP * 16
    src_factor_in=1,
    wgt_factor_out=0,
    wgt_factor_in=0
))

insn_buffer.append(VTAAluInsn( # I6: ALU - MAX IMM 0 (relu)
    opcode=4, # 4-ALU
    # DEP FLAG
    pop_prev_dep=0,
    pop_next_dep=0,
    push_prev_dep=0,
    push_next_dep=0,
    # Operations
    reset=0, # 0-no, 1-reset
    uop_bgn=11, # UOP 11
    uop_end=12,
    loop_out=7,
    loop_in=16,
    # UNUSED
    unused=0, # UNUSED
    # Index factors
    dst_factor_out=16,
    dst_factor_in=1, # ACC incremented by 1
    src_factor_out=16,
    src_factor_in=1, # INP incremented by 1
    alu_opcode=1, # 0-MIN, 1-MAX, 2-ADD, 3-SHR, 4-MUL
    use_imm=1, # 0-no, 1-yes
    imm=0
))

insn_buffer.append(VTAAluInsn( # I7: ALU - ADD (Average Pooling 1/3)
    opcode=4, # 4-ALU
    # DEP FLAG
    pop_prev_dep=0,
    pop_next_dep=0,
    push_prev_dep=0,
    push_next_dep=0,
    # Operations
    reset=0, # 0-no, 1-reset
    uop_bgn=12, # UOP 12
    uop_end=13,
    loop_out=1,
    loop_in=25*2, # The number of out elements by the number of required addition (kernel // 2)
    # UNUSED
    unused=0, # UNUSED
    # Index factors
    dst_factor_out=0,
    dst_factor_in=2, 
    src_factor_out=0,
    src_factor_in=2, 
    alu_opcode=2, # 0-MIN, 1-MAX, 2-ADD, 3-SHR, 4-MUL
    use_imm=0, # 0-no, 1-yes
    imm=0
))

insn_buffer.append(VTAAluInsn( # I8: ALU - ADD (Average Pooling 2/3)
    opcode=4, # 4-ALU
    # DEP FLAG
    pop_prev_dep=0,
    pop_next_dep=0,
    push_prev_dep=0,
    push_next_dep=0,
    # Operations
    reset=0, # 0-no, 1-reset
    uop_bgn=13, # UOP 13
    uop_end=14,
    loop_out=5, # Output tensor size
    loop_in=5,
    # UNUSED
    unused=0, # UNUSED
    # Index factors
    dst_factor_out=20, # Sixth elements index
    dst_factor_in=2, 
    src_factor_out=20,
    src_factor_in=2, 
    alu_opcode=2, # 0-MIN, 1-MAX, 2-ADD, 3-SHR, 4-MUL
    use_imm=0, # 0-no, 1-yes
    imm=0
))

insn_buffer.append(VTAAluInsn( # I9: ALU - SHR (Average Pooling 3/3)
    opcode=4, # 4-ALU
    # DEP FLAG
    pop_prev_dep=0,
    pop_next_dep=0,
    push_prev_dep=0,
    push_next_dep=1, # Ready signal to STORE
    # Operations
    reset=0, # 0-no, 1-reset
    uop_bgn=14, # UOP 14
    uop_end=15,
    loop_out=5,
    loop_in=5,
    # UNUSED
    unused=0, # UNUSED
    # Index factors
    dst_factor_out=20,
    dst_factor_in=2, 
    src_factor_out=20,
    src_factor_in=2, 
    alu_opcode=3, # 0-MIN, 1-MAX, 2-ADD, 3-SHR, 4-MUL
    use_imm=1, # 0-no, 1-yes
    imm=2 # Division by 4 (rounded down)
))

insn_buffer.append(VTAMemInsn( # I10: NOP-MEMORY-STAGE (STORE)
    opcode=1, # 0-LOAD, 1-STORE, 3-FINISH
    # DEP FLAG
    pop_prev_dep=1, # Acknowledge COMPUTE ready signal
    pop_next_dep=0,
    push_prev_dep=0, 
    push_next_dep=0,
    # Memory interaction
    buffer_id=4, # 0-UOP, 1-WGT, 2-INP, 3-ACC, 4-OUT, 5-ACC8bit
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
# I11 -> I206: STORE
for outer_loop in range(0,5):
    for inner_loop in range(0, 5):
        insn_buffer.append(VTAMemInsn( # I10: STORE
            opcode=1, # 0-LOAD, 1-STORE, 3-FINISH
            # DEP FLAG
            pop_prev_dep=0,
            pop_next_dep=0,
            push_prev_dep=0,
            push_next_dep=0,
            # Memory interaction
            buffer_id=4, # 0-UOP, 1-WGT, 2-INP, 3-ACC, 4-OUT, 5-ACC8bit
            sram_base=0x0000 + 2*inner_loop + (10*2)*outer_loop, 
            dram_base=0x00002100 + inner_loop + 5*outer_loop, # TODO: modify to implement full LeNet-5 # TODO: 0x00002100
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
insn_buffer.append(VTAMemInsn( # I207: NOP-MEMORY-STAGE (STORE)
    opcode=1, # 0-LOAD, 1-STORE, 3-FINISH
    # DEP FLAG
    pop_prev_dep=0,
    pop_next_dep=0,
    push_prev_dep=1, # Ready signal to COMPUTE
    push_next_dep=0,
    # Memory interaction
    buffer_id=4, # 0-UOP, 1-WGT, 2-INP, 3-ACC, 4-OUT, 5-ACC8bit
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

insn_buffer.append(VTAMemInsn( # I208: NOP-MEMORY-STAGE (LOAD)
    opcode=0, # 0-LOAD, 1-STORE, 3-FINISH
    # DEP FLAG
    pop_prev_dep=0,
    pop_next_dep=0,
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

# -----------------------------------------------------------

# WRITE INSTRUCTIONS IN BINARY FILE
# ---------------------------------
# Write the instructions in the binary file
with open(file_insn_path, "wb") as f:
    for insn in insn_buffer:
        f.write(insn)

# -----------------------------------------------------------

# PRINT INSTRUCTIONS IN HEXADECIMAL (for CHISEL simulation)
# ---------------------------------
i = 0
for insn in insn_buffer:
    print(f"\nI{i}:")
    print_hex_128bit(insn)
    i = i + 1
