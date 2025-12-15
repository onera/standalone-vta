# IMPORT PACKAGES
# ---------------
import os
import sys

import numpy as np

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import utils.tensor_matrix_converter as TM



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
    isAcc1Get = False
    isAcc2Get = False

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
            elif (isAcc1Get == False):
                isAcc1Get = True
                acc_tensor_shape = inp_shape # NCHW
            
            elif (isAcc2Get == False):
                isAcc2Get = True
                # Check the consistency between both inputs
                if (inp['shape'] != acc_tensor_shape):
                    raise Exception(f"ERROR (in {filename}): Add must add 2 same shape tensors! \n")
            
            # Else problem
            else:
                raise Exception(f"ERROR (in {filename}): Unexpected input ({inp_name})! \n")


        # Get param
        elif (inp_name in param):
            # Empty field = metadata
            if (len(inp_shape) == 0):
                if (j == 1): # ACC1 SCALE
                    A_scale = param[inp_name]
                elif (j == 2): # ACC1 ZERO POINT
                    A_zp = param[inp_name]
                
                elif (j == 4): # ACC2 SCALE
                    B_scale = param[inp_name]
                elif (j == 5): # ACC2 ZERO POINT
                    B_zp = param[inp_name]
                
                elif (j == 6): # OUT SCALE
                    C_scale = param[inp_name]
                elif (j == 7): # OUT ZERO POINT
                    C_zp = param[inp_name]

            # It is bias
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
            "C": [
                ["ADD_ACC", ["X", "Y"]]
            ]
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
        "processor": "vta",
        "reshape": "int32",
        "offsetA": A_zp,
        "offsetB": B_zp,
        "input_shape": acc_tensor_shape,
        "kernel": (1, 1),
        "stride": (1, 1),
        "padding": (0, 0, 0, 0),
        "output_shape": out_tensor_shape,
        "rescaling": (A_scale * B_scale)/C_scale,
        "offsetC": C_zp
    })

    return vta_ir, node_info
