# IMPORT PACKAGES
# ---------------
import os
import sys
import numpy as np

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils.find_project_root import *
from utils.json_parser import *
import utils.configuration as conf

import vta_compiler.data_definition.data_definition as DD


###############################################

# MAIN FUNCTION (REFERENCE COMPUTATION)
# -------------
def reference_computation(vta_config_dict, operations_dict,
                          debug=True):
    
    if (debug):
        print(f"\nREFERENCE COMPUTATION..." + \
              f"\n\t {operations_dict} \n\t With: {vta_config_dict}\n")


    # GET CONFIGURATION
    # -----------------
    # Data type
    inp_dtype = conf.data_type(vta_config_dict["LOG_INP_WIDTH"])
    wgt_dtype = conf.data_type(vta_config_dict["LOG_WGT_WIDTH"])
    acc_dtype = conf.data_type(vta_config_dict["LOG_ACC_WIDTH"])
    # Block size (hardware constraint)
    block_size = 2**vta_config_dict["LOG_BLOCK"]


    # DECODE VTA IR (JSON file)
    # -------------------------
    # Filename
    name = operations_dict["NAME"]

    # Init some variables
    output_name = ''

    # Get the fields
    load_dict = operations_dict["LOAD"]
    matrices_dict = operations_dict["MATRICES"]
    for key in operations_dict["STORE"].keys():
        output_name = key
    store_list = operations_dict["STORE"][output_name]
    if "GEMM" in operations_dict:
        gemm_op = operations_dict["GEMM"]
    else:
        gemm_op = []
    if "ALU" in operations_dict:
        alu_list = operations_dict["ALU"][output_name]
    else:
        alu_list = []

    # Get the matrix
    isOutInit = False
    for key in matrices_dict.keys():
        # Define the type
        dtype = None

        # Get the dtype
        if (key == output_name and isOutInit == True):
            continue
        elif (key == output_name and isOutInit == False):
            dtype = acc_dtype
        else:
            for buffer in load_dict.keys():
                if (key == load_dict[buffer][0]):
                    if (buffer == "INP"):
                        dtype = inp_dtype
                    elif (buffer == "WGT"):
                        dtype = wgt_dtype
                    elif (buffer == "ACC"):
                        dtype = acc_dtype
                    break
                elif ( len(load_dict[buffer]) > 1 ):
                    if (key == load_dict[buffer][1] and buffer == "ACC"):
                        dtype = acc_dtype
                        break

        # Create the matrix
        m_row = matrices_dict[key][0]
        n_col = matrices_dict[key][1]

        # Get the raw file
        if (matrices_dict[key][2].endswith(".bin")):
            raw_file = matrices_dict[key][2]
            # Read the data (1D)
            flat_array = np.fromfile(raw_file, dtype=dtype)
            # Reshaphe the data in 2D (h, w)
            matrix = flat_array.reshape((m_row, n_col))  
        else: # No file
            matrix = np.zeros((m_row, n_col), dtype=dtype)

        # # Pad the column
        # target_cols = ((n_col - 1) // block_size + 1) * block_size
        # # Pad the matrix with 0 (pad = target - n)
        # matrix = np.pad(matrix, ((0, 0), (0, target_cols-n_col)), mode='constant')
        
        # Update the value of matrices_dict
        if (key != output_name):
            matrices_dict[key] = matrix.copy()
        # If ACC, update the output value
        if (dtype == acc_dtype and isOutInit == False):
            matrices_dict[output_name] = matrix.copy()
            isOutInit = True
    
    # Local save of matrices_dict
    init_matrices_dict = matrices_dict.copy()


    # PERFORM OPERATIONS 
    # ------------------
    # GEMM
    if "GEMM" in operations_dict:
        if ( type(gemm_op[2]) == int ):
            matrices_dict[output_name] = matrices_dict[gemm_op[0]] + \
                (matrices_dict[gemm_op[1]].astype(acc_dtype) * gemm_op[2])
        else:
            matrices_dict[output_name] = matrices_dict[gemm_op[0]] + \
                np.matmul(matrices_dict[gemm_op[1]].astype(acc_dtype), matrices_dict[gemm_op[2]].astype(acc_dtype))
    
    # Local save of matrices_dict[output_name] after GEMM
    gemm_out_matrix = matrices_dict[output_name].copy()
    

    # ALU
    for alu in alu_list:
        # Get the operator
        alu_op = alu[0]

        # Check if it is ADD_ACC (A + B) or classic ALU
        if (alu_op == "ADD_ACC"):
            matrices_dict[output_name] = \
                matrices_dict[alu[1][0]] + matrices_dict[alu[1][1]]
            
        else: # ALU( X(a), X(b) ) or ALU( X(a), b )
            # Get the ALU information
            dst_idx = alu[1][0][0]
            dst_step = alu[1][0][1]
            nb_loop = alu[1][2]

            # Check if it is immediate: ALU( X(a), b )
            if (alu_op.endswith("_IMM")):
                isIMM = True
                src_idx = alu[1][1]
                src_step = 0
            else: # ALU( X(a), X(b) )
                isIMM = False
                src_idx = alu[1][1][0]
                src_step = alu[1][1][1]
            
            # Loop
            for i in range(0, nb_loop):
                # Update the element
                current_dst = dst_idx + dst_step * i
                current_src = src_idx + src_step * i

                # Perform the current operation
                matrices_dict[output_name] = \
                    perform_alu_operations(matrices_dict[output_name], alu_operation=alu_op, 
                                           dst_idx=current_dst, elem2=current_src, isIMM=isIMM)

 
    # SET THE OUTPUT MATRIX
    # ---------------------
    if (store_list[0] == output_name):
        final_acc_matrix = matrices_dict[output_name].copy()

    else: # Flatten the store
        flat_store_list = []
        for store in store_list:
            dst_idx, dst_step = store[0]
            nb_loop = store[1]
            for i in range(0, nb_loop):
                flat_store_list.append( dst_idx + dst_step * i )
        # Copy the element
        final_acc_matrix = matrices_dict[output_name][flat_store_list]

    # Truncated result
    if (dtype == np.int8):
        out_matrix = truncate_to_int8(final_acc_matrix.copy())
    else:
        out_matrix = final_acc_matrix.copy()
    
    # Setup the output folder (standalone-vta/compiler_output/)
    output_dir = compiler_output_setup()
    # Binarise the result
    file_path = filepath_definition(output_dir, 'reference'+name+'.bin')
    with open(file_path, 'wb') as f:
        out_matrix.tofile(f)


    # ---------------------------------------------
    # DEBUG
    if (debug):
        print(f"\nREFERENCE COMPUTATION: {name} ")

        print(f"Initial matrices:")
        for key in init_matrices_dict.keys():
            print(f"Matrix {key}: \n{init_matrices_dict[key]} \n")

        print(f"\n\nGEMM ({gemm_op}) results in: \n{gemm_out_matrix} \n")
        
        print(f"\n\nUpdated {output_name} (after ALU): \n{matrices_dict[output_name]} \n")
        print(f"\n\nThen final_acc_matrix in {acc_dtype} (vectors are filtered): \n{final_acc_matrix} \n")
        print(f"\n\nThen out_matrix in {inp_dtype}: \n{out_matrix}")

    # ---------------------------------------------
    # RETURN new base_address
    return 0

###############################################

# TRUNCATE
# --------
def truncate_to_int8(x):
    """Truncate a value or matrix into int8 (keep the LSB)."""
    return np.bitwise_and(x, 0xFF).astype(np.int8)


# PERFORM ALU OPERATIONS
# ----------------------
def perform_alu_operations(matrix, alu_operation="MAX_IMM", dst_idx=0, elem2=0, isIMM=True):
    """
    Perform an alu_operation on the matrix on the line index dst_idx.
    If isIMM: operand = elem2 else operand = matrix[elem2]
    The operations is matrix[dst_idx] = ALU(matrix[dst_idx], operand)

    Inputs:
        - matrix (matrix): a numpy matrix
        - alu_operation (str): a string for the operation to perform
        - dst_idx (int): the line index on which perform the operation
        - elem2 (int): the line index or imm_value to use for the operation
        - isIMM (bool): boolean to identify if it is vector-vector operation or vector-scalar
    Result:
        - matrix: the updated numpy matrix
    """
    operand = elem2 if isIMM else matrix[elem2]

    if (alu_operation.startswith("MAX")):
        matrix[dst_idx] = np.maximum(matrix[dst_idx], operand)
    elif (alu_operation.startswith("MIN")):
        matrix[dst_idx] = np.minimum(matrix[dst_idx], operand)
    elif (alu_operation.startswith("ADD")):
        matrix[dst_idx] = np.add(matrix[dst_idx], operand)
    elif (alu_operation.startswith("MUL")):
        matrix[dst_idx] = np.multiply(matrix[dst_idx], operand)
    elif (alu_operation.startswith("SHR")):
        matrix[dst_idx] = np.right_shift(matrix[dst_idx], operand)
    else:
        raise Exception(f"ERROR: ALU non-supported operations ({alu_operation})! \n\n")

    return matrix

###############################################

# EXECUTE MAIN FUNCTION
# ---------------------
if __name__ == "__main__": 
    """
    To execute: 
        > python main_vta_compiler.py 
            <debug>
            <config_file> 
            [<vta_ir>] 
    """
    
    # Need 3: script_name, debug, config_file, vta_ir
    if len(sys.argv) < 3:
        raise Exception("ERROR: The arguments must be <config_file> <json_file> ... \n\n")

    # Set debug
    debug = True if (sys.argv[1] == "True" or sys.argv[1] == "true") else False
    # Config file
    vta_config_file = sys.argv[2]
    vta_config_dict = parse_json_to_dict(vta_config_file)

    # VTA IR
    for vta_ir in sys.argv[3:]:
        operations_dict = parse_json_to_dict(vta_ir)

        # Execute the main function
        reference_computation(vta_config_dict, operations_dict,
                              debug=debug)

    # END!
