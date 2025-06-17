# PACKAGE IMPORT
# --------------
import os
import sys

# Parent folder
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from structures_insn_uop import *

# -----------------------------------------------------------

# FILE PATH
# ---------
# Define the files to write 
output_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))), 'compiler_output')
file_uop_path = os.path.join(output_dir, "uop.bin")
file_insn_path = os.path.join(output_dir, "instructions.bin")

# Create the path if it does not exist
def create_output_directory(path):
    os.makedirs(path, exist_ok=True)
create_output_directory(output_dir)

# -----------------------------------------------------------

# UOP DEFINITION
# --------------
# Define empty UOP buffer
uop_buffer = []

# Append the buffer with the UOPs
uop_buffer.append(VTAUop( # UOP 0
    dst_idx=0, 
    src_idx=1,
    wgt_idx=0
))

uop_buffer.append(VTAUop( # UOP 1
    dst_idx=0, 
    src_idx=4,
    wgt_idx=0
))

uop_buffer.append(VTAUop( # UOP 2
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
    opcode=0,  # 0-LOAD, 1-STORE, 3-FINISH
    # DEP FLAG
    pop_prev_dep=0,
    pop_next_dep=0,
    push_prev_dep=0,
    push_next_dep=0,
    # Memory interaction
    buffer_id=0,  # 0-UOP, 1-WGT, 2-INP, 3-ACC, 4-OUT, 5-ACC8bit
    sram_base=0x0000,
    dram_base=0x00001000,
    unused=0,  # UNUSED
    # Operation over the data
    y_size=1,
    x_size=3, # Load 3 UOP
    x_stride=3,
    y_pad_top=0,
    y_pad_bottom=0,
    x_pad_left=0,
    x_pad_right=0
))

insn_buffer.append(VTAMemInsn( # I1: LOAD ACC
    opcode=0,  # 0-LOAD, 1-STORE, 3-FINISH
    # DEP FLAG
    pop_prev_dep=0,
    pop_next_dep=0,
    push_prev_dep=0,
    push_next_dep=0,
    # Memory interaction
    buffer_id=3,  # 0-UOP, 1-WGT, 2-INP, 3-ACC, 4-OUT, 5-ACC8bit
    sram_base=0x0000,
    dram_base=0x00000140,
    unused=0,  # UNUSED
    # Operation over the data
    y_size=1,
    x_size=16, # Load 16 ACC
    x_stride=16,
    y_pad_top=0,
    y_pad_bottom=0,
    x_pad_left=0,
    x_pad_right=0
))

insn_buffer.append(VTAAluInsn( # I2: ALU - ADD
    opcode=4,  # 4-ALU
    # DEP FLAG
    pop_prev_dep=0,
    pop_next_dep=0,
    push_prev_dep=0,
    push_next_dep=0,
    # Operations
    reset=0, # 0-no, 1-reset
    uop_bgn=0, # UOP 0
    uop_end=1,
    loop_out=1,
    loop_in=8,
    # UNUSED
    unused=0,  # UNUSED
    # Index factors
    dst_factor_out=0,
    dst_factor_in=2,
    src_factor_out=0,
    src_factor_in=2,
    alu_opcode=2, # 0-MIN, 1-MAX, 2-ADD, 3-SHR, 4-MUL
    use_imm=0, # 0-no, 1-yes
    imm=0
))

insn_buffer.append(VTAAluInsn( # I3: ALU - ADD
    opcode=4,  # 4-ALU
    # DEP FLAG
    pop_prev_dep=0,
    pop_next_dep=0,
    push_prev_dep=0,
    push_next_dep=0,
    # Operations
    reset=0, # 0-no, 1-reset
    uop_bgn=1, # UOP 1
    uop_end=2,
    loop_out=2,
    loop_in=2,
    # UNUSED
    unused=0,  # UNUSED
    # Index factors
    dst_factor_out=8,
    dst_factor_in=2,
    src_factor_out=8,
    src_factor_in=2,
    alu_opcode=2, # 0-MIN, 1-MAX, 2-ADD, 3-SHR, 4-MUL
    use_imm=0, # 0-no, 1-yes
    imm=0
))

insn_buffer.append(VTAAluInsn( # I4: ALU - SHR 2
    opcode=4,  # 4-ALU
    # DEP FLAG
    pop_prev_dep=0,
    pop_next_dep=0,
    push_prev_dep=0,
    push_next_dep=1, # Ready signal to STORE
    # Operations
    reset=0, # 0-no, 1-reset
    uop_bgn=2, # UOP 2
    uop_end=3,
    loop_out=2,
    loop_in=2,
    # UNUSED
    unused=0,  # UNUSED
    # Index factors
    dst_factor_out=8,
    dst_factor_in=2,
    src_factor_out=8,
    src_factor_in=2,
    alu_opcode=3, # 0-MIN, 1-MAX, 2-ADD, 3-SHR, 4-MUL
    use_imm=1, # 0-no, 1-yes
    imm=2 # Divide by 4
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
for outer_loop in range(0, 2):
    for inner_loop in range(0, 2):
        insn_buffer.append(VTAMemInsn( # I10: STORE
            opcode=1, # 0-LOAD, 1-STORE, 3-FINISH
            # DEP FLAG
            pop_prev_dep=0,
            pop_next_dep=0,
            push_prev_dep=0,
            push_next_dep=0,
            # Memory interaction
            buffer_id=4, # 0-UOP, 1-WGT, 2-INP, 3-ACC, 4-OUT, 5-ACC8bit
            sram_base=0x0000 + 2*inner_loop + 8*outer_loop, 
            dram_base=0x00000300 + inner_loop + 2*outer_loop, # TODO
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

insn_buffer.append(VTAMemInsn( # I6: NOP-COMPUTE-STAGE
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

insn_buffer.append(VTAMemInsn( # I7: FINISH
    opcode=3,  # 0-LOAD, 1-STORE, 3-FINISH
    # DEP FLAG
    pop_prev_dep=0,
    pop_next_dep=0,
    push_prev_dep=0,
    push_next_dep=0,
    # Memory interaction
    buffer_id=0,  # 0-UOP, 1-WGT, 2-INP, 3-ACC, 4-OUT, 5-ACC8bit
    sram_base=0x0000,
    dram_base=0x00000000,
    unused=0,  # UNUSED
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
