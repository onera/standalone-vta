# IMPORT PACKAGES
# ---------------
import os
import sys

import numpy as np

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils.find_project_root import *
import utils.tensor_matrix_converter as TM
import nn_compiler.shape_data.shape_data as SD



###############################################


# ADD
# ---
def node_add(node, param={}, node_mapping={}, node_info={}, filename='', 
             inp_dtype=np.int8, wgt_dtype=np.int8, acc_dtype=np.int32,
             debug=False):
    # Reset the vta_ir
    vta_ir = {}

    # ---
    # PARSE METADATA
    # --------------

    # Get the metadata
    # ---
    op_type = node['op_type']
    inp_list = node['inputs']
    out_list = node['outputs']
    attributes_dict = node['attributes']

    # Reset the node data
    # ---
    acc_tensor_shape = []
    out_tensor_shape = []
    isBias = False
    isFlat = False

    # For Quantisation
    A_scale = 1.
    A_zp = 0
    B_scale = 1.
    B_zp = 0
    C_scale = 1.
    C_zp = 0


    # Get the output tensors
    # ---
    # A single output is expected
    if ( len(out_list) != 1 ):
        raise Exception(f"ERROR (in {filename}): There are {len(out_list)} dimensions when only 1 is expected! \n")

    out_tensor_shape = out_list[0]['shape']

    # The output must have 4 dimensions
    if ( len(out_tensor_shape) != 4 ):
        raise Exception(f"ERROR (in {filename}): Wrong output shape ({len(out_tensor_shape)} dimensions when 4 are expected)! \n")


    # Get the input tensors
    # ---
    # Count the nodes
    isAcc1Get = -1
    isAcc2Get = -1
    initAccBis = -1

    for j, inp in enumerate(inp_list):
        # Get the name
        inp_name = inp['name']
        inp_shape = inp['shape']

        # Get X and Y (be careful, it is in int32) -> X.shape = Y.shape
        if (inp_name in node_mapping):
            # Check there are 4 dimensions
            if ( len(inp_shape) != 4 ):
                raise Exception(f"ERROR (in {filename}): Wrong input shape ({len(inp_shape)} dimensions when 4 are expected)! \n")

            # Get the shape
            elif (isAcc1Get < 0):
                isAcc1Get = j
                acc_tensor_shape = inp_shape # NCHW
            
            elif (isAcc2Get < 0):
                isAcc2Get = j
                # Check the consistency between both inputs
                if (inp_shape != acc_tensor_shape):
                    raise Exception(f"ERROR (in {filename}): Add must add 2 same shape tensors! \n")
            
            # Else problem
            else:
                raise Exception(f"ERROR (in {filename}): Unexpected input ({inp_name})! \n")


        # Get param
        elif (inp_name in param):
            # Empty field = metadata
            if (len(inp_shape) == 0):
                if (j == isAcc1Get+1): # ACC1 SCALE
                    A_scale = param[inp_name]
                elif (j == isAcc1Get+2): # ACC1 ZERO POINT
                    A_zp = param[inp_name]
                
                elif (j == isAcc2Get+1): # ACC2 SCALE
                    B_scale = param[inp_name]
                elif (j == isAcc2Get+2): # ACC2 ZERO POINT
                    B_zp = param[inp_name]
                
                elif (j == 6): # OUT SCALE
                    C_scale = param[inp_name]
                elif (j == 7): # OUT ZERO POINT
                    C_zp = param[inp_name]

            # It is bias
            elif (len(inp_shape) == 4):
                if (inp_shape != acc_tensor_shape):
                    raise Exception(f"ERROR (in {filename}): Add must add 2 same shape tensors! \n")
                if (j != 0 and j != 3):
                    raise Exception(f"ERROR (in {filename}): Bias is not in the expected position (j={j})! \n")
                initAccBis = j
                init_tensor = param[inp_name].astype(acc_dtype)

            # There is a problem
            else:
                raise Exception(f"ERROR (in {filename}): Unexpected parameter ({inp_name})! \n")


        # Else problem 
        else:
            raise Exception(f"ERROR (in {filename}): Unexpected input ({inp_name}) which does not come from another node nor parameters! \n")



    # Get the attributes
    # ---
    nc = acc_tensor_shape[1]
    nh = acc_tensor_shape[2]
    nw = acc_tensor_shape[3]

    mc = out_tensor_shape[1]
    mh = out_tensor_shape[2]
    mw = out_tensor_shape[3]

    if (len(attributes_dict) > 0):
        raise Exception(f"ERROR (in {filename}): Add should not have attributes but have attributes_dict={attributes_dict}! \n")


    # ---
    # DEFINE MATRICES
    # ---------------

    # Define the matrix dimensions
    # ---
    Xh = nh*nw
    Xw = nc

    Ch = mh*mw
    Cw = mc

    # # Manage the bias
    # if (initAccBis != False):
    #     if (B_zp != 0):
    #         init_tensor = init_tensor - B_zp 
    #     init_matrix = SD.flatten_conv_output(init_tensor)

    #     # Write the binary
    #     output_dir = compiler_output_setup()
    #     # WGT
    #     file_bias_path = filepath_definition(output_dir, filename+"accbis_"+str(Xh)+"x"+str(Xw)+".bin")

    #     # WRITE
    #     with open(file_bias_path, 'wb') as f:
    #         init_matrix.tofile(f)


    # ---
    # DEFINE ALU OPERATIONS
    # ---------------------
    # C = Sa/Sc * (A - Za) + Sb/Sc * (B - Zb)
    # -> Ma = Sa/Sc, Mb = Sb/Sc
    # -> Pa = round(Ma) * 2^n, Pb = round(Mb) * 2^n
    n = 20 # The point precision
    # Compute Pa
    Ma = A_scale / C_scale
    Pa = round(Ma * (2**n))

    # Compute Pb
    Mb = B_scale / C_scale
    Pb = round(Mb * (2**n))

    # Rescaling bias
    bias = 2**(n - 1)

    # Size
    block_size = 16
    size = Xh + (block_size - Xh%block_size) - 1

    # ALU OPERATION
    alu_operations = [
        ["MUL_IMM", [[0,1], Pa, Xh]], # Factor to X
        ["MUL_IMM", [[size,1], Pb, Xh]], # Factor to Y
        ["ADD", [[0,1], [size,1], Xh]], # X + Y
        ["ADD_IMM", [[0,1], bias, Xh]], # bias
        ["SHR_IMM", [[0,1], n, Xh]] # Remove factors
    ]

        
    # ---
    # WRITE VTA IR
    # ------------
    # Define the VTA IR
    vta_ir = {
        "NAME": filename,
        "MATRICES": {
            "X": [Xh, Xw, "../compiler_output/"+filename+"accumulator_"+str(Xh)+"x"+str(Xw)+".bin"],
            "Y": [Xh, Xw, "../compiler_output/"+filename+"accbis_"+str(Xh)+"x"+str(Xw)+".bin"],
            "C": [Xh, Xw, "output"]
        },
        "LOAD": {
            "ACC": ["X", "Y"]
        },
        "ALU" : {
            "C": alu_operations
            # [
            #     ["ADD_ACC", ["X", "Y"]]
            # ]

        },
        "STORE": {
            "C": ["C"]
        }
    }


    # ---
    # RETURN
    # ------
    node_info.update({
        "matrix_shape": (Xh, Xw),
        "processor": "qadd",
        "reshape": "int32",
        "offsetA": A_zp,
        "scaleA": A_scale,
        "offsetB": B_zp,
        "scaleB": B_scale,
        "input_shape": acc_tensor_shape,
        "kernel": (1, 1),
        "stride": (1, 1),
        "padding": (0, 0, 0, 0),
        "output_shape": out_tensor_shape,
        "offsetC": C_zp,
        "scaleC": C_scale,
        "rescaling": 1.,
        "initAccBis": initAccBis
    })

    return vta_ir, node_info
