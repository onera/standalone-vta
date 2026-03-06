# IMPORT PACKAGES
# ---------------
import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.find_project_root import *
from vta_compiler.operations_definition.structures import *


###############################################

# LOOP vs UOP on 16x16 matrices
# ------------------------------
def test_gemm(doLoop=False, loadAllUop=False, doReset=False, doPrint=False):
    # Init buffer
    uop_buffer = []
    insn_buffer = []

    # Write UOP
    for i in range(0, 16):
        uop = VTAUop( 
            dst_idx=i, # ACC
            src_idx=i, # INP (gemm) / ACC (alu)
            wgt_idx=0  # WGT 
        )
        uop_buffer.append(uop)

    # Write INSN
    # 0 - LOAD INP
    I0 = VTAMemInsn(
        opcode=0, # 0-LOAD, 1-STORE, 3-FINISH
        # DEP FLAG (0:False, 1: True)
        pop_prev_dep=0,
        pop_next_dep=0,
        push_prev_dep=0, 
        push_next_dep=0, 
        # Memory interaction
        buffer_id=2, # 0-UOP, 1-WGT, 2-INP, 3-ACC, 4-OUT, 5-ACC8bit
        sram_base=0,
        dram_base=0x40,
        unused=0, # UNUSED
        # Operation over the data
        y_size=1,
        x_size=16,
        x_stride=16,
        y_pad_top=0,
        y_pad_bottom=0,
        x_pad_left=0,
        x_pad_right=0
    )
    insn_buffer.append(I0)

    # 1- LOAD WGT
    I1 = VTAMemInsn(
        opcode=0, # 0-LOAD, 1-STORE, 3-FINISH
        # DEP FLAG (0:False, 1: True)
        pop_prev_dep=0,
        pop_next_dep=0,
        push_prev_dep=0, 
        push_next_dep=1, 
        # Memory interaction
        buffer_id=1, # 0-UOP, 1-WGT, 2-INP, 3-ACC, 4-OUT, 5-ACC8bit
        sram_base=0,
        dram_base=0x8,
        unused=0, # UNUSED
        # Operation over the data
        y_size=1,
        x_size=1,
        x_stride=1,
        y_pad_top=0,
        y_pad_bottom=0,
        x_pad_left=0,
        x_pad_right=0
    )
    insn_buffer.append(I1)

    # 2- LOAD UOP
    if (doLoop == True and loadAllUop == False):
        I2 = VTAMemInsn(
            opcode=0, # 0-LOAD, 1-STORE, 3-FINISH
            # DEP FLAG (0:False, 1: True)
            pop_prev_dep=0,
            pop_next_dep=0,
            push_prev_dep=0, 
            push_next_dep=0, 
            # Memory interaction
            buffer_id=0, # 0-UOP, 1-WGT, 2-INP, 3-ACC, 4-OUT, 5-ACC8bit
            sram_base=0,
            dram_base=0x1400,
            unused=0, # UNUSED
            # Operation over the data
            y_size=1,
            x_size=1,
            x_stride=1,
            y_pad_top=0,
            y_pad_bottom=0,
            x_pad_left=0,
            x_pad_right=0
        )
    else:
        I2 = VTAMemInsn(
            opcode=0, # 0-LOAD, 1-STORE, 3-FINISH
            # DEP FLAG (0:False, 1: True)
            pop_prev_dep=0,
            pop_next_dep=0,
            push_prev_dep=0, 
            push_next_dep=0, 
            # Memory interaction
            buffer_id=0, # 0-UOP, 1-WGT, 2-INP, 3-ACC, 4-OUT, 5-ACC8bit
            sram_base=0,
            dram_base=0x1400,
            unused=0, # UNUSED
            # Operation over the data
            y_size=1,
            x_size=16,
            x_stride=16,
            y_pad_top=0,
            y_pad_bottom=0,
            x_pad_left=0,
            x_pad_right=0
        )
    insn_buffer.append(I2)

    # x - RESET
    if (doReset == True):
        Ireset = VTAGemInsn( 
            opcode=2, # 2-GEMM
            # DEP FLAG (0:False, 1: True)
            pop_prev_dep=0,
            pop_next_dep=0,
            push_prev_dep=0,
            push_next_dep=0,
            # Operations
            reset=1, # 0-no, 1-reset
            uop_bgn=0,
            uop_end=1,
            loop_out=1,
            loop_in=16, 
            # UNUSED
            unused=0, # UNUSED
            # Index factors
            dst_factor_out=0, 
            dst_factor_in=1, 
            src_factor_out=0,
            src_factor_in=1,
            wgt_factor_out=0,
            wgt_factor_in=0
        )
        insn_buffer.append(Ireset)

    # 3 - GEMM
    if (doLoop == True):
        I3 = VTAGemInsn( 
            opcode=2, # 2-GEMM
            # DEP FLAG (0:False, 1: True)
            pop_prev_dep=1,
            pop_next_dep=0,
            push_prev_dep=0,
            push_next_dep=1,
            # Operations
            reset=0, # 0-no, 1-reset
            uop_bgn=0,
            uop_end=1,
            loop_out=1,
            loop_in=16, 
            # UNUSED
            unused=0, # UNUSED
            # Index factors
            dst_factor_out=0, 
            dst_factor_in=1, 
            src_factor_out=0,
            src_factor_in=1,
            wgt_factor_out=0,
            wgt_factor_in=0
        )
    else:
        I3 = VTAGemInsn( 
            opcode=2, # 2-GEMM
            # DEP FLAG (0:False, 1: True)
            pop_prev_dep=1,
            pop_next_dep=0,
            push_prev_dep=0,
            push_next_dep=1,
            # Operations
            reset=0, # 0-no, 1-reset
            uop_bgn=0,
            uop_end=16,
            loop_out=1,
            loop_in=1, 
            # UNUSED
            unused=0, # UNUSED
            # Index factors
            dst_factor_out=0, 
            dst_factor_in=0, 
            src_factor_out=0,
            src_factor_in=0,
            wgt_factor_out=0,
            wgt_factor_in=0
        )
    insn_buffer.append(I3)

    # 4- STORE
    I4 = VTAMemInsn(
        opcode=1, # 0-LOAD, 1-STORE, 3-FINISH
        # DEP FLAG (0:False, 1: True)
        pop_prev_dep=1,
        pop_next_dep=0,
        push_prev_dep=1, 
        push_next_dep=0, 
        # Memory interaction
        buffer_id=4, # 0-UOP, 1-WGT, 2-INP, 3-ACC, 4-OUT, 5-ACC8bit
        sram_base=0,
        dram_base=0x100,
        unused=0, # UNUSED
        # Operation over the data
        y_size=1,
        x_size=16,
        x_stride=16,
        y_pad_top=0,
        y_pad_bottom=0,
        x_pad_left=0,
        x_pad_right=0
    )
    insn_buffer.append(I4)

    # 5- LOAD UOP
    I5 = VTAMemInsn(
        opcode=0, # 0-LOAD, 1-STORE, 3-FINISH
        # DEP FLAG (0:False, 1: True)
        pop_prev_dep=0,
        pop_next_dep=1,
        push_prev_dep=0, 
        push_next_dep=0, 
        # Memory interaction
        buffer_id=0, # 0-UOP, 1-WGT, 2-INP, 3-ACC, 4-OUT, 5-ACC8bit
        sram_base=0,
        dram_base=0,
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
    insn_buffer.append(I5)

    # 6- FINISH
    I6 = VTAMemInsn(
        opcode=3, # 0-LOAD, 1-STORE, 3-FINISH
        # DEP FLAG (0:False, 1: True)
        pop_prev_dep=0,
        pop_next_dep=0,
        push_prev_dep=0, 
        push_next_dep=0, 
        # Memory interaction
        buffer_id=0, # 0-UOP, 1-WGT, 2-INP, 3-ACC, 4-OUT, 5-ACC8bit
        sram_base=0,
        dram_base=0,
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
    insn_buffer.append(I6)


    # Print, binarise
    # ---
    if (doPrint):
        # Print the UOP
        for i, uop in enumerate(uop_buffer):
            print(f"UOP {i}:")
            _, string_uop = hex_32bit(uop, debug=False)
            decode_uop(string_uop)
            print("\n")

        # Print the instruction
        for i, insn in enumerate(insn_buffer):
            print(f"I {i}:")
            _, string_insn = hex_128bit(insn, debug=False)
            decode_vta_insn(string_insn)
            print("\n")
    
    
    # Set the path
    output_dir = compiler_output_setup()
    insn_filepath = filepath_definition(output_dir, 'instructions.bin')
    uop_filepath = filepath_definition(output_dir, 'uop.bin')

    # Binarise UOP
    with open(uop_filepath, "wb") as f:
        for uop in uop_buffer:
            f.write(uop)
    
    # Binarise INSN
    with open(insn_filepath, "wb") as f:
        for insn in insn_buffer:
            f.write(insn)
       
    print(f"\nFiles generated: \n\t {uop_filepath} \n\t {insn_filepath} \n")
 
    # Return
    # ---
    return 0


###

def test_alu(doLoop=False, loadAllUop=False, doReset=False, doPrint=False):
    # Init buffer
    uop_buffer = []
    insn_buffer = []

    # Write UOP
    for i in range(0, 16):
        uop = VTAUop( 
            dst_idx=i, # ACC
            src_idx=0, # INP (gemm) / ACC (alu)
            wgt_idx=0  # WGT 
        )
        uop_buffer.append(uop)

    # Write INSN
    # 0 - LOAD UOP
    if (doLoop == True and loadAllUop == False):
        I0 = VTAMemInsn(
            opcode=0, # 0-LOAD, 1-STORE, 3-FINISH
            # DEP FLAG (0:False, 1: True)
            pop_prev_dep=0,
            pop_next_dep=0,
            push_prev_dep=0, 
            push_next_dep=0, 
            # Memory interaction
            buffer_id=0, # 0-UOP, 1-WGT, 2-INP, 3-ACC, 4-OUT, 5-ACC8bit
            sram_base=0,
            dram_base=0xc00,
            unused=0, # UNUSED
            # Operation over the data
            y_size=1,
            x_size=1,
            x_stride=1,
            y_pad_top=0,
            y_pad_bottom=0,
            x_pad_left=0,
            x_pad_right=0
        )
    else:
        I0 = VTAMemInsn(
            opcode=0, # 0-LOAD, 1-STORE, 3-FINISH
            # DEP FLAG (0:False, 1: True)
            pop_prev_dep=0,
            pop_next_dep=0,
            push_prev_dep=0, 
            push_next_dep=0, 
            # Memory interaction
            buffer_id=0, # 0-UOP, 1-WGT, 2-INP, 3-ACC, 4-OUT, 5-ACC8bit
            sram_base=0,
            dram_base=0xc00,
            unused=0, # UNUSED
            # Operation over the data
            y_size=1,
            x_size=16,
            x_stride=16,
            y_pad_top=0,
            y_pad_bottom=0,
            x_pad_left=0,
            x_pad_right=0
        )
    insn_buffer.append(I0)

    # 1 - LOAD ACC
    I1 = VTAMemInsn(
        opcode=0, # 0-LOAD, 1-STORE, 3-FINISH
        # DEP FLAG (0:False, 1: True)
        pop_prev_dep=0,
        pop_next_dep=0,
        push_prev_dep=0, 
        push_next_dep=0, 
        # Memory interaction
        buffer_id=3, # 0-UOP, 1-WGT, 2-INP, 3-ACC, 4-OUT, 5-ACC8bit
        sram_base=0,
        dram_base=0x40,
        unused=0, # UNUSED
        # Operation over the data
        y_size=1,
        x_size=16,
        x_stride=16,
        y_pad_top=0,
        y_pad_bottom=0,
        x_pad_left=0,
        x_pad_right=0
    )
    insn_buffer.append(I1)

    # x - RESET (reset ALU does not work)
    if (doReset == True):
        Ireset = VTAGemInsn( 
            opcode=2, # 2-GEMM
            # DEP FLAG (0:False, 1: True)
            pop_prev_dep=0,
            pop_next_dep=0,
            push_prev_dep=0,
            push_next_dep=0,
            # Operations
            reset=1, # 0-no, 1-reset
            uop_bgn=0,
            uop_end=1,
            loop_out=1,
            loop_in=16, 
            # UNUSED
            unused=0, # UNUSED
            # Index factors
            dst_factor_out=0, 
            dst_factor_in=1, 
            src_factor_out=0,
            src_factor_in=1,
            wgt_factor_out=0,
            wgt_factor_in=0
        )
        insn_buffer.append(Ireset)

    # 2 - ALU
    if (doLoop == True):
        I2 = VTAAluInsn( 
            opcode=4, # 4-ALU
            # DEP FLAG (0:False, 1: True)
            pop_prev_dep=0,
            pop_next_dep=0,
            push_prev_dep=0,
            push_next_dep=1,
            # Operations
            reset=0, # 0-no, 1-reset
            uop_bgn=0,
            uop_end=1,
            loop_out=1,
            loop_in=16,
            # UNUSED
            unused=0, # UNUSED
            # Index factors
            dst_factor_out=0,
            dst_factor_in=1, 
            src_factor_out=0,
            src_factor_in=0, 
            alu_opcode=2, # 0-MIN, 1-MAX, 2-ADD, 3-SHR, 4-MUL
            use_imm=1, # 0-no, 1-yes
            imm=3
        )
    else:
        I2 = VTAAluInsn( 
            opcode=4, # 4-ALU
            # DEP FLAG (0:False, 1: True)
            pop_prev_dep=0,
            pop_next_dep=0,
            push_prev_dep=0,
            push_next_dep=1,
            # Operations
            reset=0, # 0-no, 1-reset
            uop_bgn=0,
            uop_end=16,
            loop_out=1,
            loop_in=1,
            # UNUSED
            unused=0, # UNUSED
            # Index factors
            dst_factor_out=0,
            dst_factor_in=0, 
            src_factor_out=0,
            src_factor_in=0, 
            alu_opcode=2, # 0-MIN, 1-MAX, 2-ADD, 3-SHR, 4-MUL
            use_imm=1, # 0-no, 1-yes
            imm=3
        )
    insn_buffer.append(I2)

    # 3- STORE
    I3 = VTAMemInsn(
        opcode=1, # 0-LOAD, 1-STORE, 3-FINISH
        # DEP FLAG (0:False, 1: True)
        pop_prev_dep=1,
        pop_next_dep=0,
        push_prev_dep=1, 
        push_next_dep=0, 
        # Memory interaction
        buffer_id=4, # 0-UOP, 1-WGT, 2-INP, 3-ACC, 4-OUT, 5-ACC8bit
        sram_base=0,
        dram_base=0x80,
        unused=0, # UNUSED
        # Operation over the data
        y_size=1,
        x_size=16,
        x_stride=16,
        y_pad_top=0,
        y_pad_bottom=0,
        x_pad_left=0,
        x_pad_right=0
    )
    insn_buffer.append(I3)

    # 4- LOAD UOP
    I4 = VTAMemInsn(
        opcode=0, # 0-LOAD, 1-STORE, 3-FINISH
        # DEP FLAG (0:False, 1: True)
        pop_prev_dep=0,
        pop_next_dep=1,
        push_prev_dep=0, 
        push_next_dep=0, 
        # Memory interaction
        buffer_id=0, # 0-UOP, 1-WGT, 2-INP, 3-ACC, 4-OUT, 5-ACC8bit
        sram_base=0,
        dram_base=0,
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
    insn_buffer.append(I4)

    # 5- FINISH
    I5 = VTAMemInsn(
        opcode=3, # 0-LOAD, 1-STORE, 3-FINISH
        # DEP FLAG (0:False, 1: True)
        pop_prev_dep=0,
        pop_next_dep=0,
        push_prev_dep=0, 
        push_next_dep=0, 
        # Memory interaction
        buffer_id=0, # 0-UOP, 1-WGT, 2-INP, 3-ACC, 4-OUT, 5-ACC8bit
        sram_base=0,
        dram_base=0,
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
    insn_buffer.append(I5)


    # Print, binarise
    # ---
    if (doPrint):
        # Print the UOP
        for i, uop in enumerate(uop_buffer):
            print(f"UOP {i}:")
            _, string_uop = hex_32bit(uop, debug=False)
            decode_uop(string_uop)
            print("\n")

        # Print the instruction
        for i, insn in enumerate(insn_buffer):
            print(f"I {i}:")
            _, string_insn = hex_128bit(insn, debug=False)
            decode_vta_insn(string_insn)
            print("\n")
    
    
    # Set the path
    output_dir = compiler_output_setup()
    insn_filepath = filepath_definition(output_dir, 'instructions.bin')
    uop_filepath = filepath_definition(output_dir, 'uop.bin')

    # Binarise UOP
    with open(uop_filepath, "wb") as f:
        for uop in uop_buffer:
            f.write(uop)
    
    # Binarise INSN
    with open(insn_filepath, "wb") as f:
        for insn in insn_buffer:
            f.write(insn)
       
    print(f"\nFiles generated: \n\t {uop_filepath} \n\t {insn_filepath} \n")
 
    # Return
    # ---
    return 0


###############################################


# EXECUTE MAIN FUNCTION
# ---------------------
if __name__ == "__main__": 
    # User settings
    doLoop=False
    loadAllUop=True
    doReset=True
    doPrint=True

    # ["gemm", "alu"]
    select = "alu"

    # Call the function
    if (select == "gemm"):
        test_gemm(doLoop=doLoop, loadAllUop=loadAllUop, doReset=doReset, doPrint=doPrint)
    elif (select == "alu"):
        test_alu(doLoop=doLoop, loadAllUop=loadAllUop, doReset=doReset, doPrint=doPrint)
    else:
        print("\nNOTHING DONE! \n\n")

    # END
