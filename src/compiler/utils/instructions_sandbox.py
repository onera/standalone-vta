# IMPORT PACKAGES
# ---------------
import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.find_project_root import *
from vta_compiler.operations_definition.structures import *


###############################################


# MAIN FUNCTION
# -------------
def instructions_sandbox(instruction=None, uop=None,
                         whichInsn="mem", 
                         doPrint=False, 
                         doInsnBinary=False, doUopBinary=False, doAppend=False):
    # Write Instruction
    #---
    if (instruction != None):
        print(f"DECODE instruction! \n")
        doPrint = True

    elif (whichInsn == "mem"):
        # Write a memory instruction
        mem_insn = VTAMemInsn(
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
        instruction = mem_insn

    elif (whichInsn == "gemm"):
        # Write a GEMM instruction
        gemm_insn = VTAGemInsn( 
            opcode=2, # 2-GEMM
            # DEP FLAG (0:False, 1: True)
            pop_prev_dep=0,
            pop_next_dep=0,
            push_prev_dep=0,
            push_next_dep=0,
            # Operations
            reset=0, # 0-no, 1-reset
            uop_bgn=0,
            uop_end=1,
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
        instruction = gemm_insn

    elif (whichInsn == "alu"):
        # Write an ALU instruction
        alu_insn = VTAAluInsn( 
            opcode=4, # 4-ALU
            # DEP FLAG (0:False, 1: True)
            pop_prev_dep=0,
            pop_next_dep=0,
            push_prev_dep=0,
            push_next_dep=0,
            # Operations
            reset=0, # 0-no, 1-reset
            uop_bgn=0,
            uop_end=1,
            loop_out=1,
            loop_in=1,
            # UNUSED
            unused=0, # UNUSED
            # Index factors
            dst_factor_out=0,
            dst_factor_in=0, 
            src_factor_out=0,
            src_factor_in=0, 
            alu_opcode=0, # 0-MIN, 1-MAX, 2-ADD, 3-SHR, 4-MUL
            use_imm=0, # 0-no, 1-yes
            imm=0
        )
        instruction = alu_insn
    
    else:
        raise Exception(f"\nERROR: whichInsn={whichInsn} when expected: 'mem', 'gemm', or 'alu'! \n\n")

    # Write UOP
    # ---
    if (uop != None):
        print(f"DECODE UOP! \n")
        doPrint = True

    else:
        uop = VTAUop( 
            dst_idx=0, # ACC
            src_idx=0, # INP (gemm) / ACC (alu)
            wgt_idx=0  # WGT 
        )


    # Print, binarise
    # ---
    if (doPrint):
        # Print the instruction
        if (isinstance(instruction, str)):
            string_insn = instruction
        else:
            _, string_insn = hex_128bit(instruction, debug=False)
        decode_vta_insn(string_insn)

        print("\n")

        # Print the UOP
        if (isinstance(uop, str)):
            string_uop = uop
        else:
            _, string_uop = hex_32bit(uop, debug=False)
        decode_uop(string_uop)
    
    if (doInsnBinary or doUopBinary):
        # Set the path
        output_dir = compiler_output_setup()
        insn_filepath = filepath_definition(output_dir, 'instructions.bin')
        uop_filepath = filepath_definition(output_dir, 'uop.bin')

        # Set the file mode (append or write)
        if (doAppend):
            param = "ab"
        else:
            param = "wb"

        if (doInsnBinary):
            if (isinstance(instruction, str)):
                raise Exception(f"\nERROR: Instruction is a string! \n\n")

            # Write in the binary file
            with open(insn_filepath, param) as f:
                f.write(instruction)
            
            print(f"\nFile ({param}): {insn_filepath}\n")
        
        elif (doUopBinary):
            if (isinstance(uop, str)):
                raise Exception(f"\nERROR: UOP is a string! \n\n")

            # Write in the binary file
            with open(uop_filepath, param) as f:
                f.write(uop)
            
            print(f"\nFile ({param}): {uop_filepath}\n")
        
        else:
            pass


    # Return
    # ---
    return 0




###############################################


# EXECUTE MAIN FUNCTION
# ---------------------
if __name__ == "__main__": 
    # User settings
    instruction = "00000000000000000000000000000003" # String, None
    uop =  "00000000" # String, None
    whichInsn = "mem" # "mem", "gemm", "alu"
    doPrint = True # True, False
    doInsnBinary = False # True, False
    doUopBinary = False # True, False
    doAppend = False # True, False

    # Call the function
    instructions_sandbox(
        instruction=instruction,
        uop=uop,
        whichInsn=whichInsn,
        doPrint=doPrint,
        doInsnBinary=doInsnBinary,
        doUopBinary=doUopBinary,
        doAppend=doAppend
        )
    # END
