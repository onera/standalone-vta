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
output_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))), 'OUTPUT')
file_uop_path = os.path.join(output_dir, "uop_batches_1uop_2loops.bin")
file_insn_path = os.path.join(output_dir, "instructions_batches_1uop_2loops.bin")

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
uop_buffer.append(VTAUop(
    dst_idx=0, 
    src_idx=1,
    wgt_idx=2
))
uop_buffer.append(VTAUop(
    dst_idx=3, 
    src_idx=4,
    wgt_idx=5
))
uop_buffer.append(VTAUop(
    dst_idx=6, 
    src_idx=7,
    wgt_idx=8
))
uop_buffer.append(VTAUop(
    dst_idx=9, 
    src_idx=10,
    wgt_idx=11
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
    dram_base=0x00001000,
    unused=0, # UNUSED
    # Operation over the data
    y_size=1,
    x_size=4, # Load 4 UOP
    x_stride=4,
    y_pad_top=0,
    y_pad_bottom=0,
    x_pad_left=0,
    x_pad_right=0
))

insn_buffer.append(VTAMemInsn( # I1: FINISH
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
