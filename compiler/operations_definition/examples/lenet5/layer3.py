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

# FILE PATH
# ---------
# Define the files to write 
output_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))), 'compiler_output')
file_uop_path = os.path.join(output_dir, "uop_L3.bin")
file_insn_path = os.path.join(output_dir, "instructions_L3.bin")

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
uop_buffer.append(VTAUop( # UOP 0 - reset
    dst_idx=0, 
    src_idx=0,
    wgt_idx=0
))

uop_buffer.append(VTAUop( # UOP 1 - GeMM
    dst_idx=0, 
    src_idx=0,
    wgt_idx=0
))

uop_buffer.append(VTAUop( # UOP 2 - ALU
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
    dram_base=0x00007800, # TODO: modify to implement full LeNet-5
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
    loop_out=8,
    loop_in=1,
    # UNUSED
    unused=0, # UNUSED
    # Index factors
    dst_factor_out=1,
    dst_factor_in=0,
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
    x_size=25,
    x_stride=25,
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
    dram_base=0x000000a0, # TODO: modify to implement full LeNet-5
    unused=0, # UNUSED
    # Operation over the data
    y_size=1,
    x_size=200, 
    x_stride=200,
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
    dram_base=0x00007801, # TODO: modify to implement full LeNet-5
    unused=0, # UNUSED
    # Operation over the data
    y_size=1,
    x_size=2, # 2 UOP (1 GEMM + 1 ALU)
    x_stride=2,
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
    uop_bgn=1, # UOP 1
    uop_end=2,
    loop_out=8,
    loop_in=25,
    # UNUSED
    unused=0, # UNUSED
    # Index factors
    dst_factor_out=1,
    dst_factor_in=0,
    src_factor_out=0,
    src_factor_in=1,
    wgt_factor_out=1,
    wgt_factor_in=8
))

insn_buffer.append(VTAAluInsn( # I6: ALU - MAX IMM 0 (relu)
    opcode=4, # 4-ALU
    # DEP FLAG
    pop_prev_dep=0,
    pop_next_dep=0,
    push_prev_dep=0,
    push_next_dep=1,
    # Operations
    reset=0, # 0-no, 1-reset
    uop_bgn=2, # UOP 2
    uop_end=3,
    loop_out=8,
    loop_in=1,
    # UNUSED
    unused=0, # UNUSED
    # Index factors
    dst_factor_out=1,
    dst_factor_in=0,
    src_factor_out=1,
    src_factor_in=0,
    alu_opcode=1, # 0-MIN, 1-MAX, 2-ADD, 3-SHR, 4-MUL
    use_imm=1, # 0-no, 1-yes
    imm=0
))

insn_buffer.append(VTAMemInsn( # I7: STORE
    opcode=1, # 0-LOAD, 1-STORE, 3-FINISH
    # DEP FLAG
    pop_prev_dep=1, # Acknowledge COMPUTE ready signal
    pop_next_dep=0,
    push_prev_dep=1, # Ready signal to COMPUTE
    push_next_dep=0,
    # Memory interaction
    buffer_id=4, # 0-UOP, 1-WGT, 2-INP, 3-ACC, 4-OUT, 5-ACC8bit
    sram_base=0x0000,
    dram_base=0x00000100, # TODO: modify to implement full LeNet-5
    unused=0, # UNUSED
    # Operation over the data
    y_size=1,
    x_size=8,
    x_stride=8,
    y_pad_top=0,
    y_pad_bottom=0,
    x_pad_left=0,
    x_pad_right=0
))

insn_buffer.append(VTAMemInsn( # I8: NOP-MEMORY-STAGE (LOAD)
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

insn_buffer.append(VTAMemInsn( # I9: NOP-COMPUTE-STAGE
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

insn_buffer.append(VTAMemInsn( # I10: FINISH
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
