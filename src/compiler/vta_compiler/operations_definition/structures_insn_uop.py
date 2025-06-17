# PACKAGE IMPORT
# --------------
import ctypes
from ctypes import Structure, c_uint64, LittleEndianStructure

# -----------------------------------------------------------

# STRUCTURES DEFINITION
# ---------------------
# Create the UOP structure
class VTAUop(LittleEndianStructure):
    """UOP structure (32-bit)."""
    _fields_ = [
        ("dst_idx", ctypes.c_uint32, 11), 
        ("src_idx", ctypes.c_uint32, 11), 
        ("wgt_idx", ctypes.c_uint32, 10) 
    ]


# Create the instruction structures
class VTAMemInsn(LittleEndianStructure):
    """Memory instruction structure (128-bit)."""
    _pack_ = 1
    _fields_ = [
        ("opcode", c_uint64, 3),
        ("pop_prev_dep", c_uint64, 1),
        ("pop_next_dep", c_uint64, 1),
        ("push_prev_dep", c_uint64, 1),
        ("push_next_dep", c_uint64, 1),
        ("buffer_id", c_uint64, 3),
        ("sram_base", c_uint64, 16),
        ("dram_base", c_uint64, 32),
        ("unused", c_uint64, 6),
        ("y_size", c_uint64, 16),
        ("x_size", c_uint64, 16),
        ("x_stride", c_uint64, 16),
        ("y_pad_top", c_uint64, 4),
        ("y_pad_bottom", c_uint64, 4),
        ("x_pad_left", c_uint64, 4),
        ("x_pad_right", c_uint64, 4)
    ]

class VTAGemInsn(LittleEndianStructure):
    """GeMM instruction structure (128-bit)."""
    _pack_ = 1
    _fields_ = [
        ("opcode", c_uint64, 3),
        ("pop_prev_dep", c_uint64, 1),
        ("pop_next_dep", c_uint64, 1),
        ("push_prev_dep", c_uint64, 1),
        ("push_next_dep", c_uint64, 1),
        ("reset", c_uint64, 1),
        ("uop_bgn", c_uint64, 13),
        ("uop_end", c_uint64, 14),
        ("loop_out", c_uint64, 14),
        ("loop_in", c_uint64, 14),
        ("unused", c_uint64, 1),
        ("dst_factor_out", c_uint64, 11),
        ("dst_factor_in", c_uint64, 11),
        ("src_factor_out", c_uint64, 11),
        ("src_factor_in", c_uint64, 11),
        ("wgt_factor_out", c_uint64, 10),
        ("wgt_factor_in", c_uint64, 10)
    ]

class VTAAluInsn(LittleEndianStructure):
    """ALU instruction structure (128-bit)."""
    _pack_ = 1
    _fields_ = [
        ("opcode", c_uint64, 3),
        ("pop_prev_dep", c_uint64, 1),
        ("pop_next_dep", c_uint64, 1),
        ("push_prev_dep", c_uint64, 1),
        ("push_next_dep", c_uint64, 1),
        ("reset", c_uint64, 1),
        ("uop_bgn", c_uint64, 13),
        ("uop_end", c_uint64, 14),
        ("loop_out", c_uint64, 14),
        ("loop_in", c_uint64, 14),
        ("unused", c_uint64, 1),
        ("dst_factor_out", c_uint64, 11),
        ("dst_factor_in", c_uint64, 11),
        ("src_factor_out", c_uint64, 11),
        ("src_factor_in", c_uint64, 11),
        ("alu_opcode", c_uint64, 3), # 0-MIN, 1-MAX, 2-ADD, 3-SHR, 4-MUL/SHL
        ("use_imm", c_uint64, 1), # 0-NO, 1-YES
        ("imm", c_uint64, 16)
    ]


# FUNCTION TO PRINT INSTRUCTION IN HEXADECIMAL
# --------------------------------------------
# Print function
def print_hex_128bit(insn):
    """Print the instruction in hexadecimal (to be used in CHISEL simulation)."""
    # Convert structure in Bytes
    raw_bytes = ctypes.string_at(ctypes.byref(insn), ctypes.sizeof(insn))

    # Convert Bytes in hexadecimal chain
    hex_string = raw_bytes[::-1].hex().upper()

    # Print group of 8 characters (4 Bytes = 32 bits)
    print("0x" + " ".join([hex_string[i:i+8] for i in range(0, 32, 8)]))


# INSTRUCTION DECODER
# -------------------
def decode_vta_insn(hex_string):
    """Decode a given instruction in hexadecimal."""
    # Convert hexadecimal string to bytes, reversing the order
    insn_bytes = bytes.fromhex(hex_string.replace(" ", ""))[::-1]
    
    # Create instances of the different types of instructions
    mem_insn = VTAMemInsn.from_buffer_copy(insn_bytes)
    gem_insn = VTAGemInsn.from_buffer_copy(insn_bytes)
    alu_insn = VTAAluInsn.from_buffer_copy(insn_bytes)
    
    # Determine the instruction type based on opcode
    if mem_insn.opcode in [0, 1, 3]:
        insn = mem_insn
        insn_type = "VTAMemInsn"
    elif gem_insn.opcode == 2:
        insn = gem_insn
        insn_type = "VTAGemInsn"
    elif alu_insn.opcode == 4:
        insn = alu_insn
        insn_type = "VTAAluInsn"
    else:
        raise ValueError("Unknown opcode")
    
    # Print each field with its value
    print(f"Instruction type: {insn_type}")
    for field in insn._fields_:
        field_name = field[0]
        field_value = getattr(insn, field_name)
        print(f"{field_name}: {field_value}")

# Decode the instruction
if __name__ == '__main__':
    print("\n\n\nINSTRUCTION DECODER:\n")
    decode_vta_insn("00000000000000000000000000000003")
