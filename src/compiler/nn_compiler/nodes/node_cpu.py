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
    scale = 1.
    zp = 0


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
    isInpGet = -1

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
            elif (isInpGet < 0):
                isInpGet = j
                inp_tensor_shape = inp_shape # NCHW
            
            # Else problem
            else:
                raise Exception(f"ERROR (in {filename}): Unexpected input ({inp_name})! \n")


        # Get param
        elif (inp_name in param):
            # Empty field = metadata
            if (len(inp_shape) == 0):
                if (j == 1): # SCALE
                    scale = param[inp_name]
                elif (j == 2): # ZERO POINT
                    zp = param[inp_name]

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
    if (op_type == 'QuantizeLinear'):
        node_info["processor"] = "quant"
    else:
        node_info["processor"] = "dequant"

    node_info.update({
        "matrix_shape": (Xh, Xw),
        "reshape": False,
        "offsetA": zp,
        "scaleA": scale,
        "offsetB": 0,
        "scaleB": 1.,
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
    U_scale = 1.
    U_zp = 0
    V_scale = 1.
    V_zp = 0
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
    isAGet = -1
    isBGet = -1
    isUGet = -1
    isVGet = -1

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
            elif (isAGet < 0):
                isAGet = j
                inpA_tensor_shape = inp_shape # NCHW

            elif (isBGet < 0 or isUGet < 0 or isVGet < 0):
                if (isBGet < 0):
                    isBGet = j
                elif (isUGet < 0):
                    isUGet = j
                elif (isVGet < 0):
                    isVGet = j

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

                elif (j == isAGet+1): # A SCALE
                    A_scale = param[inp_name]
                elif (j == isAGet+2): # A ZERO POINT
                    A_zp = param[inp_name]

                elif (j == isBGet+1): # B SCALE
                    B_scale = param[inp_name]
                elif (j == isBGet+2): # B ZERO POINT
                    B_zp = param[inp_name]

                elif (j == isUGet+1): # U SCALE
                    U_scale = param[inp_name]
                elif (j == isUGet+2): # U ZERO POINT
                    U_zp = param[inp_name]

                elif (j == isVGet+1): # V SCALE
                    V_scale = param[inp_name]
                elif (j == isVGet+2): # V ZERO POINT
                    V_zp = param[inp_name]

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
        "offsetU": U_zp,
        "scaleU": U_scale,
        "offsetV": V_zp,
        "scaleV": V_scale,
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



###############################################

# ConvTranspose
# -------------
def convtranspose(node, param={}, node_mapping={}, node_info={}, filename='', 
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
    wgt_tensor_shape = []
    acc_tensor_shape = []
    out_tensor_shape = []
    
    wgt_tensor = []
    acc_tensor = []


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
    isInpGet = -1
    isWgtGet = -1
    isBias = -1

    for j, inp in enumerate(inp_list):
        # Get the name
        inp_name = inp['name']
        inp_shape = inp['shape']

        # Get tensors
        if (inp_name in node_mapping):
            # Check there are 4 dimensions
            if ( len(inp_shape) != 4 ):
                raise Exception(f"ERROR (in {filename}): Wrong input shape ({len(inp_shape)} dimensions when 4 are expected)! \n")

            # Get the shape
            elif (isInpGet < 0):
                isInpGet = j
                inp_tensor_shape = inp_shape # NCHW

            # Else problem
            else:
                raise Exception(f"ERROR (in {filename}): Unexpected input ({inp_name})! \n")


        # Get param
        elif (inp_name in param):
            # X (bias)
            if ( (len(inp_shape) == 1) and (isBias < 0) ):
                isBias = j
                acc_tensor_shape = [1, inp_shape[0], 1, 1]
                acc_tensor = param[inp_name].astype(np.float32)

            elif ( len(inp_shape) == 4 and isWgtGet < 0):
                isWgtGet = j 
                wgt_tensor_shape = inp_shape # NCHW
                wgt_tensor = param[inp_name].astype(np.float32)

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

    fh = wgt_tensor_shape[2]
    fw = wgt_tensor_shape[3]
    # Check consistency
    if (fh != attributes_dict['kernel_shape'][0] or fw != attributes_dict['kernel_shape'][1]):
        raise Exception(f"ERROR (in {filename}): Kernel size not consistent! \n")

    sh = attributes_dict['strides'][0]
    sw = attributes_dict['strides'][1]

    # attributes_dict['pads'] = [TOP, LEFT, BOTTOM, RIGHT]
    if ('pads' in attributes_dict):
        ph = (attributes_dict['pads'][0], attributes_dict['pads'][2])
        pw = (attributes_dict['pads'][1], attributes_dict['pads'][3])
    elif ('auto_pad' in attributes_dict):
        if ( attributes_dict['auto_pad'].startswith("SAME") and sh == 1 and sw == 1):
            phtotal = fh - 1
            pwtotal = fw - 1
            ph = (phtotal//2, phtotal//2)
            pw = (pwtotal//2, pwtotal//2)
    else:
        ph = (0, 0)
        pw = (0, 0)


    # ---
    # DEFINE MATRICES
    # ---------------

    # Define the matrix dimensions
    # ---
    Ch = mh*mw
    Cw = mc

    # BIAS
    if (isBias < 0):
        acc_tensor = np.zeros((1, accX_tensor_shape[2]), dtype=np.float32)

    
    # ---
    # WRITE BINARIES
    # --------------
    output_dir = compiler_output_setup()
    # WGT
    file_wgt_path = filepath_definition(output_dir, "weight"+filename+".bin")
    # ACC
    file_acc_path = filepath_definition(output_dir, "accumulator"+filename+".bin")

    # WRITE
    with open(file_wgt_path, 'wb') as f:
        wgt_tensor.tofile(f)
    with open(file_acc_path, 'wb') as f:
        acc_tensor.tofile(f)
    
    
    # # DEBUG
    # file_debug_wgt_path = filepath_definition(output_dir, "debug_weight"+filename+".bin")
    # file_debug_acc_path = filepath_definition(output_dir, "debug_acc"+filename+".bin")
    # with open(file_debug_wgt_path, 'wb') as f:
    #     wgt_tensor.tofile(f)
    # if (isBias == True):
    #     with open(file_debug_acc_path, 'wb') as f:
    #         acc_tensor.tofile(f)


    # ---
    # RETURN
    # ------
    node_info.update({
        "matrix_shape": (Ch, Cw),
        "processor": "convtranspose",
        "reshape": False,
        "offsetA": 0,
        "scaleA": 1.,
        "offsetB": 0,
        "scaleB": 1.,
        "offsetU": 0,
        "scaleU": 1.,
        "offsetV": 0,
        "scaleV": 1.,
        "input_shape": inp_tensor_shape,
        "kernel": (fh, fw),
        "stride": (sh, sw),
        "padding": (ph[0], pw[0], ph[1], pw[1]),
        "output_shape": out_tensor_shape,
        "offsetC": 0,
        "scaleC": 1.,
        "rescaling": 1.
    })

    return node_info
