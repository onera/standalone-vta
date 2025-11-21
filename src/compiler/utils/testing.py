# IMPORT PACKAGES
# ---------------
import os
import sys 

import json
import random

import random_raw_binary_generator as RBG 
from find_project_root import *

###############################################

# TESTING MATMUL
# --------------
def generate_vta_ir_matmul(filename="matmul", debug=False):
    # Manage the path
    output_dir = compiler_output_setup()
    file_path = filepath_definition(output_dir, filename+'.json')

    # Generate random values for dimension, keeping the consistency for C = X + A*B
    Ah = random.randint(1, 2048) # 8192
    Aw_Bh = random.randint(1, 2048) # 8192
    Bw = random.randint(1, 2048) # 8192

    # Create a python dictionnary
    vta_ir = {
        "NAME": filename,
        "MATRICES": {
            "A": [Ah, Aw_Bh, "../compiler_output/input_"+str(Ah)+"x"+str(Aw_Bh)+".bin"],
            "B": [Aw_Bh, Bw, "../compiler_output/weight_"+str(Aw_Bh)+"x"+str(Bw)+".bin"],
            "X": [Ah, Bw, "../compiler_output/accumulator_"+str(Ah)+"x"+str(Bw)+".bin"],
            "C": [Ah, Bw, "output"]
        },
        "LOAD": {
            "INP": ["A"],
            "WGT": ["B"],
            "ACC": ["X"]
        },
        "GEMM": ["C", "A", "B"],
        "STORE": {
            "C": ["C"]
        }
    }

    # Write dict in a JSON
    with open(file_path, 'w') as f:
        json.dump(vta_ir, f, indent=2) # indent=2 for better readibility

    # Create binary files
    RBG.random_raw_binary_generator(m_rows=Ah, n_columns=Aw_Bh, filename="input", dtype='int8', debug=False)
    RBG.random_raw_binary_generator(m_rows=Aw_Bh, n_columns=Bw, filename="weight", dtype='int8', debug=False)
    RBG.random_raw_binary_generator(m_rows=Ah, n_columns=Bw, filename="accumulator", dtype='int32', debug=False)

    if (debug):
        print(f"File '{filename}' is successfully generated! \
                \n\t A = {Ah}x{Aw_Bh} \
                \n\t B = {Aw_Bh}x{Bw} \
                \n\t X = {Ah}x{Bw} \
                \n\t Total multiplied elements = {Ah * Aw_Bh + Aw_Bh * Bw} \n")

###############################################

# TESTING MATMUL+RELU
# -------------------
def generate_vta_ir_matmul_relu(filename="matmul_relu", debug=False):
    # Manage the path
    output_dir = compiler_output_setup()
    file_path = filepath_definition(output_dir, filename+'.json')

    # Generate random values for dimension, keeping the consistency for C = X + A*B
    Ah = random.randint(1, 2048) # 8192
    Aw_Bh = random.randint(1, 2048) # 8192
    Bw = random.randint(1, 2048) # 8192


    # Create a python dictionnary
    vta_ir = {
        "NAME": filename,
        "MATRICES": {
            "A": [Ah, Aw_Bh, "../compiler_output/input_"+str(Ah)+"x"+str(Aw_Bh)+".bin"],
            "B": [Aw_Bh, Bw, "../compiler_output/weight_"+str(Aw_Bh)+"x"+str(Bw)+".bin"],
            "X": [Ah, Bw, "../compiler_output/accumulator_"+str(Ah)+"x"+str(Bw)+".bin"],
            "C": [Ah, Bw, "output"]
        },
        "LOAD": {
            "INP": ["A"],
            "WGT": ["B"],
            "ACC": ["X"]
        },
        "GEMM": ["C", "A", "B"],
        "ALU" : {
            "C": [
                ["MAX_IMM", [[0,1], 0, Ah]]
            ]
        },
        "STORE": {
            "C": ["C"]
        }
    }

    # Write dict in a JSON
    with open(file_path, 'w') as f:
        json.dump(vta_ir, f, indent=2) # indent=2 for better readibility

    # Create binary files
    RBG.random_raw_binary_generator(m_rows=Ah, n_columns=Aw_Bh, filename="input", dtype='int8', debug=False)
    RBG.random_raw_binary_generator(m_rows=Aw_Bh, n_columns=Bw, filename="weight", dtype='int8', debug=False)
    RBG.random_raw_binary_generator(m_rows=Ah, n_columns=Bw, filename="accumulator", dtype='int32', debug=False)

    if (debug):
        print(f"File '{filename}' is successfully generated! \
                \n\t A = {Ah}x{Aw_Bh} \
                \n\t B = {Aw_Bh}x{Bw} \
                \n\t X = {Ah}x{Bw} \
                \n\t Total multiplied elements = {Ah * Aw_Bh + Aw_Bh * Bw} \n")

###############################################

# TESTING MULCONSTANT+RELU
# ------------------------
def generate_vta_ir_mulconstant(filename="mulconstant", debug=False):
    # Manage the path
    output_dir = compiler_output_setup()
    file_path = filepath_definition(output_dir, filename+'.json')

    # Generate random values for dimension, keeping the consistency for C = X + A*b
    Ah = random.randint(1, 2048) # 8192
    Aw = random.randint(1, 2048) # 8192
    scalar = random.randint(-128, 127)


    # Create a python dictionnary
    vta_ir = {
        "NAME": filename,
        "MATRICES": {
            "A": [Ah, Aw, "../compiler_output/input_"+str(Ah)+"x"+str(Aw)+".bin"],
            "X": [Ah, Aw, "../compiler_output/accumulator_"+str(Ah)+"x"+str(Aw)+".bin"],
            "C": [Ah, Aw, "output"]
        },
        "LOAD": {
            "INP": ["A"],
            "ACC": ["X"]
        },
        "GEMM": ["C", "A", scalar],
        "ALU" : {
            "C": [
                ["MAX_IMM", [[0,1], 0, Ah]]
            ]
        },
        "STORE": {
            "C": ["C"]
        }
    }

    # Write dict in a JSON
    with open(file_path, 'w') as f:
        json.dump(vta_ir, f, indent=2) # indent=2 for better readibility

    # Create binary files
    RBG.random_raw_binary_generator(m_rows=Ah, n_columns=Aw, filename="input", dtype='int8', debug=False)
    RBG.random_raw_binary_generator(m_rows=Ah, n_columns=Aw, filename="accumulator", dtype='int32', debug=False)

    if (debug):
        print(f"File '{filename}' is successfully generated! \
                \n\t A = {Ah}x{Aw} \
                \n\t B = {scalar} \
                \n\t Total multiplied elements = {Ah * Aw} \n")


###############################################

# TESTING MAXPOOL
# ---------------
def generate_vta_ir_maxpool(filename="maxpool", debug=False):
    # Manage the path
    output_dir = compiler_output_setup()
    file_path = filepath_definition(output_dir, filename+'.json')

    # Generate random values for dimension
    Xh = random.randint(8, 2048) # 8192
    Xw = random.randint(1, 2048) # 8192

    # Define the number of ALU
    nb_alu = random.randint(1, Xh//4)
    kernel_size = Xh // nb_alu

    # Create the ALU operations
    operations_alu = []
    store_list = []
    for i in range(0, nb_alu):
        dst_idx = i*kernel_size
        src_idx = dst_idx + 1
        iteration = kernel_size-1
        operations_alu.append(
            ["MAX", [[dst_idx,0], [src_idx,1], iteration]]
        )
        store_list.append( [[dst_idx, 0], 1] )


    # Create a python dictionnary
    vta_ir = {
        "NAME": filename,
        "MATRICES": {
            "X": [Xh, Xw, "../compiler_output/accumulator_"+str(Xh)+"x"+str(Xw)+".bin"],
            "C": [Xh, Xw, "output"]
        },
        "LOAD": {
            "ACC": ["X"]
        },
        "ALU" : {
            "C": operations_alu
        },
        "STORE": {
            "C": store_list
        }
    }

    # Write dict in a JSON
    with open(file_path, 'w') as f:
        json.dump(vta_ir, f, indent=2) # indent=2 for better readibility

    # Create binary files
    RBG.random_raw_binary_generator(m_rows=Xh, n_columns=Xw, filename="accumulator", dtype='int32', debug=False)

    if (debug):
        print(f"File '{filename}' is successfully generated! \
                \n\t X = {Xh}x{Xw} \
                \n\t nb_alu = {nb_alu} \n")




###############################################

# TESTING ADD_ACC
# ---------------
def generate_vta_ir_add_acc(filename="add_acc", debug=False):
    # Manage the path
    output_dir = compiler_output_setup()
    file_path = filepath_definition(output_dir, filename+'.json')

    # Generate random values for dimension
    Xh = random.randint(8, 2048) # 8192
    Xw = random.randint(1, 2048) # 8192


    # Create a python dictionnary
    vta_ir = {
        "NAME": filename,
        "MATRICES": {
            "X": [Xh, Xw, "../compiler_output/accumulator_"+str(Xh)+"x"+str(Xw)+".bin"],
            "Y": [Xh, Xw, "../compiler_output/accbis_"+str(Xh)+"x"+str(Xw)+".bin"],
            "C": [Xh, Xw, "output"]
        },
        "LOAD": {
            "ACC": ["X", "Y"]
        },
        "ALU" : {
            "C": [
                ["ADD_ACC", ["X", "Y"]]
            ]
        },
        "STORE": {
            "C": ["C"]
        }
    }

    # Write dict in a JSON
    with open(file_path, 'w') as f:
        json.dump(vta_ir, f, indent=2) # indent=2 for better readibility

    # Create binary files
    RBG.random_raw_binary_generator(m_rows=Xh, n_columns=Xw, filename="accumulator", dtype='int32', debug=False)
    RBG.random_raw_binary_generator(m_rows=Xh, n_columns=Xw, filename="accbis", dtype='int32', debug=False)

    if (debug):
        print(f"File '{filename}' is successfully generated! \
                \n\t X = {Xh}x{Xw} \
                \n\t XY= {Xh}x{Xw} \n")


###############################################
###############################################


# EXECUTE MAIN FUNCTION
# ---------------------
if __name__ == "__main__": 
    """
    To execute: 
        > python testing.py 
            <function>
    """
    if (sys.argv[1] == "matmul"):
        generate_vta_ir_matmul(filename="matmul")
    elif (sys.argv[1] == "matmul_relu"):
        generate_vta_ir_matmul_relu(filename="matmul_relu")
    elif (sys.argv[1] == "mulconstant"):
        generate_vta_ir_mulconstant(filename="mulconstant")
    elif (sys.argv[1] == "maxpool"):
        generate_vta_ir_maxpool(filename="maxpool")
    elif (sys.argv[1] == "add_acc"):
        generate_vta_ir_add_acc(filename="add_acc")
    else:
        print("\nNothing done! \n")
        pass
