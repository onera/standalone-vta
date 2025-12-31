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

# QuantizeLinear
# --------------
def quantizelinear(node, param={}, node_mapping={}, node_info={}, filename='', 
                  inp_dtype=np.int8, wgt_dtype=np.int8, acc_dtype=np.int32,
                  debug=False):

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
    inp_tensor_shape = []
    out_tensor_shape = []

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
    isInpGet = False

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
            elif (isInpGet == False):
                isInpGet = True
                inp_tensor_shape = inp_shape # NCHW
            
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

            # There is a problem
            else:
                raise Exception(f"ERROR (in {filename}): Unexpected parameter ({inp_name})! \n")


        # Else problem 
        else:
            raise Exception(f"ERROR (in {filename}): Unexpected input ({inp_name}) which does not come from another node nor parameters! \n")



    # Get the attributes
    # ---
    nc = inp_tensor_shape[1]
    nh = inp_tensor_shape[2]
    nw = inp_tensor_shape[3]

    mc = out_tensor_shape[1]
    mh = out_tensor_shape[2]
    mw = out_tensor_shape[3]

    if (len(attributes_dict) > 0):
        raise Exception(f"ERROR (in {filename}): QuantizeLinear should not have attributes but have attributes_dict={attributes_dict}! \n")


    # ---
    # DEFINE MATRICES
    # ---------------

    # Define the matrix dimensions
    # ---
    Xh = nh*nw
    Xw = nc

    Ch = mh*mw
    Cw = mc

    if (Xh != Ch or Xw != Cw):
        raise Exception(f"ERROR (in {filename}): QuantizeLinear should not modify the shape: input shape=({Xh}, {Xw}) != output shape = ({Ch}, {Cw})! \n")


    # ---
    # RETURN
    # ------
    node_info.update({
        "matrix_shape": (Xh, Xw),
        "processor": "quantise",
        "reshape": False,
        "offsetA": A_zp,
        "scaleA": A_scale,
        "offsetB": 1.,
        "scaleB": 0,
        "input_shape": inp_tensor_shape,
        "kernel": (1, 1),
        "stride": (1, 1),
        "padding": (0, 0, 0, 0),
        "output_shape": out_tensor_shape,
        "offsetC": 0,
        "scaleC": 1.,
        "rescaling": 1.
    })

    return node_info


###############################################

# QLinearConcat
# --------------
def qlinearconcat(node, param={}, node_mapping={}, node_info={}, filename='', 
                  inp_dtype=np.int8, wgt_dtype=np.int8, acc_dtype=np.int32,
                  debug=False):

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
    inpA_tensor_shape = []
    inpB_tensor_shape = []
    out_tensor_shape = []

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
    isAGet = False
    isBGet = False

    for j, inp in enumerate(inp_list):
        # Get the name
        inp_name = inp['name']
        inp_shape = inp['shape']

        # Get X and Y 
        if (inp_name in node_mapping):
            # Check there are 4 dimensions
            if ( len(inp_shape) != 4 ):
                raise Exception(f"ERROR (in {filename}): Wrong input shape ({len(inp_shape)} dimensions when 4 are expected)! \n")

            # Get the shape
            elif (isAGet == False):
                isAGet = True
                inpA_tensor_shape = inp_shape # NCHW

            elif (isBGet == False):
                isBGet = True
                inpB_tensor_shape = inp_shape # NCHW

                if (inpB_tensor_shape != inpA_tensor_shape):
                    raise Exception(f"ERROR (in {filename}): A and B have different shape! \n")
            
            # Else problem
            else:
                raise Exception(f"ERROR (in {filename}): Unexpected input ({inp_name})! \n")


        # Get param
        elif (inp_name in param):
            # Empty field = metadata
            if (len(inp_shape) == 0):
                if (j == 0): # OUT SCALE
                    C_scale = param[inp_name]
                elif (j == 1): # OUT ZERO POINT
                    C_zp = param[inp_name]

                elif (j == 3): # A SCALE
                    A_scale = param[inp_name]
                elif (j == 4): # A ZERO POINT
                    A_zp = param[inp_name]

                elif (j == 6): # B SCALE
                    B_scale = param[inp_name]
                elif (j == 7): # B ZERO POINT
                    B_zp = param[inp_name]

            # There is a problem
            else:
                raise Exception(f"ERROR (in {filename}): Unexpected parameter ({inp_name})! \n")


        # Else problem 
        else:
            raise Exception(f"ERROR (in {filename}): Unexpected input ({inp_name}) which does not come from another node nor parameters! \n")



    # Get the attributes
    # ---
    # nc = inpA_tensor_shape[1]
    # nh = inpA_tensor_shape[2]
    # nw = inpA_tensor_shape[3]

    mc = out_tensor_shape[1]
    mh = out_tensor_shape[2]
    mw = out_tensor_shape[3]

    if (len(attributes_dict) > 1):
        raise Exception(f"ERROR (in {filename}): QLinearConcat should have AXIS attribute only but have attributes_dict={attributes_dict}! \n")

    axis = attributes_dict['axis']

    if (axis != 1):
        raise Exception(f"ERROR (in {filename}): We expect AXIS=1 whereas axis={axis} ! \n")


    # ---
    # DEFINE MATRICES
    # ---------------

    # Define the matrix dimensions
    # ---
    Ch = mh*mw
    Cw = mc


    # ---
    # RETURN
    # ------
    node_info.update({
        "matrix_shape": (Ch, Cw),
        "processor": "concat",
        "reshape": False,
        "offsetA": A_zp,
        "scaleA": A_scale,
        "offsetB": B_zp,
        "scaleB": B_scale,
        "input_shape": inpA_tensor_shape,
        "kernel": (1, 1),
        "stride": (1, 1),
        "padding": (0, 0, 0, 0),
        "output_shape": out_tensor_shape,
        "offsetC": C_zp,
        "scaleC": C_scale,
        "rescaling": 1.
    })

    return node_info
