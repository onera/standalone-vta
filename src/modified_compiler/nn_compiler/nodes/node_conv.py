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


# MAIN FUNCTION
# -------------
def node_conv(node, param={}, node_mapping={}, node_info={}, filename='',
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
    if (op_type != 'MatMul'):
        attributes_dict = node['attributes']

    # Reset the node data
    # ---
    inp_tensor_shape = []
    inp_matrix_shape = []
    wgt_tensor_shape = []
    wgt_matrix_shape = []
    isBias = False
    out_tensor_shape = []
    out_matrix_shape = []

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

    out_shape = out_list[0]['shape']

    # If MatMul, the shape must be expanded
    if (op_type == 'MatMul'):
        if ( len(out_shape) != 2 ):
            raise Exception(f"ERROR (in {filename}): Wrong output shape ({len(out_shape)} dimensions when 2 are expected)! \n")
        out_tensor_shape = (out_shape[0], out_shape[1], 1, 1) 

    else: # 4 dimensions tensors
        if ( len(out_shape) != 4 ):
            raise Exception(f"ERROR (in {filename}): Wrong output shape ({len(out_shape)} dimensions when 4 are expected)! \n")
        out_tensor_shape = out_shape # NCHW


    # Get the input tensors
    # ---
    # Count the nodes
    isInpGet = False
    isWgtGet = False

    for j, inp in enumerate(inp_list):
        # Get the name
        inp_name = inp['name']
        inp_shape = inp['shape']

        # Get A
        if (inp_name in node_mapping):
            if (op_type == 'MatMul'):
                # Check there are 2 dimensions
                if ( len(inp_shape) != 2 ):
                    raise Exception(f"ERROR (in {filename}): Wrong input shape ({len(inp_shape)} dimensions when 2 are expected)! \n")
                # Get the shape
                if (isInpGet == False):
                    isInpGet = True
                    inp_tensor_shape = (inp_shape[0], inp_shape[1], 1, 1)
                else:
                    raise Exception(f"ERROR (in {filename}): Unexpected input ({inp_name})! \n")
            else:
                # Check there are 4 dimensions
                if ( len(inp_shape) != 4 ):
                    raise Exception(f"ERROR (in {filename}): Wrong input shape ({len(inp_shape)} dimensions when 4 are expected)! \n")
                # Get the shape
                if (isInpGet == False):
                    isInpGet = True
                    inp_tensor_shape = inp_shape # NCHW
                else:
                    raise Exception(f"ERROR (in {filename}): Unexpected input ({inp_name})! \n")

        
        # Get B or X
        elif (inp_name in param):
            # Empty field = metadata
            if (len(inp_shape) == 0):
                if (j == 1): # INP SCALE
                    A_scale = param[inp_name]
                elif (j == 2): # INP ZERO POINT
                    A_zp = param[inp_name]
                
                elif (j == 4): # WGT SCALE
                    B_scale = param[inp_name]
                elif (j == 5): # WGT ZERO POINT
                    B_zp = param[inp_name]
                
                elif (j == 6): # OUT SCALE
                    C_scale = param[inp_name]
                elif (j == 7): # OUT ZERO POINT
                    C_zp = param[inp_name]

            # X (bias)
            elif ( (len(inp_shape) == 1) and (isBias == False) ):
                isBias = True
                acc_tensor = param[inp_name]

            else: # B (weight)
                if (isWgtGet == True):
                    raise Exception(f"ERROR (in {filename}): Multiple weight tensors in the node! \n")

                elif (op_type == 'MatMul'):
                    # Check there are 2 dimensions
                    if ( len(inp_shape) != 2 ):
                        raise Exception(f"ERROR (in {filename}): Wrong input shape ({len(inp_shape)} dimensions when 2 are expected)! \n")
                    wgt_tensor_shape = (inp_shape[0], inp_shape[1], 1, 1)
                    wgt_tensor = param[inp_name]
                else:
                    # Check there are 4 dimensions
                    if ( len(inp_shape) != 4 ):
                        raise Exception(f"ERROR (in {filename}): Wrong input shape ({len(inp_shape)} dimensions when 4 are expected)! \n")
                    wgt_tensor_shape = inp_shape # NCHW
                    wgt_tensor = param[inp_name]
                isWgtGet = True
        
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
    if (op_type != 'MatMul'):
        # Check consistency
        if (fh != attributes_dict['kernel_shape'][0] or fw != attributes_dict['kernel_shape'][1]):
            raise Exception(f"ERROR (in {filename}): Kernel size not consistent! \n")

    if (op_type != 'MatMul'):
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

    else:
        sh = 1
        sw = 1
        ph = (0, 0)
        pw = (0, 0)

    
    # ---
    # DEFINE MATRICES
    # ---------------

    # Define the matrix dimensions
    # ---
    inp_matrix_shape, wgt_matrix_shape, out_matrix_shape = \
        TM.im2row_matrix_dimension(nc=nc, nh=nh, nw=nw,
                                   mc=mc, mh=mh, mw=mw,
                                   fh=fh, fw=fw,
                                   sh=sh, sw=sw,
                                   ph=ph, pw=pw,
                                   debug=False)

    Ah = inp_matrix_shape[0] #mh*mw
    Aw_Bh = inp_matrix_shape[1] #nc*fh*fw
    Bw = wgt_matrix_shape[1] #mc


    # Transform tensor in matrix
    # ---
    # WGT
    if (B_zp != 0):
        wgt_tensor = wgt_tensor - B_zp
    wgt_matrix = SD.ker2col(wgt_tensor)

    # BIAS
    acc_matrix = []
    if (isBias == True):
        acc_matrix = SD.expand_bias(acc_tensor, Ah)
    else:
        acc_matrix = np.zeros((Ah, Bw), dtype=np.int32)


    # ---
    # WRITE VTA IR
    # ------------
    # Define the VTA IR
    vta_ir = {
        "NAME": filename,
        "MATRICES": {
            "A": [Ah, Aw_Bh, "../compiler_output/"+filename+"input_"+str(Ah)+"x"+str(Aw_Bh)+".bin"],
            "B": [Aw_Bh, Bw, "../compiler_output/"+filename+"weight_"+str(Aw_Bh)+"x"+str(Bw)+".bin"],
            "X": [Ah, Bw, "../compiler_output/"+filename+"accumulator_"+str(Ah)+"x"+str(Bw)+".bin"],
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


    # ---
    # WRITE BINARIES
    # --------------
    output_dir = compiler_output_setup()
    # WGT
    file_wgt_path = filepath_definition(output_dir, filename+"weight_"+str(Aw_Bh)+"x"+str(Bw)+".bin")
    # ACC
    file_acc_path = filepath_definition(output_dir, filename+"accumulator_"+str(Ah)+"x"+str(Bw)+".bin")

    # WRITE
    with open(file_wgt_path, 'wb') as f:
        wgt_matrix.tofile(f)
    with open(file_acc_path, 'wb') as f:
        acc_matrix.tofile(f)


    # ---
    # RETURN
    # ------
    node_info.update({
        "matrix_shape": (Ah, Aw_Bh, Bw),
        "processor": "vta",
        "reshape": "im2row",
        "offsetA": A_zp,
        "offsetB": B_zp,
        "input_shape": inp_tensor_shape,
        "kernel": (fh, fw),
        "stride": (sh, sw),
        "padding": (ph[0], pw[0], ph[1], pw[1]),
        "output_shape": out_tensor_shape,
        "rescaling": (A_scale * B_scale)/C_scale,
        "offsetC": C_zp
    })

    return vta_ir, node_info



###############################################


# MUL CONSTANT
# ------------
def node_mulconstant(node, param={}, node_mapping={}, node_info={}, filename='',
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
    inp_tensor_shape = []
    inp_matrix_shape = []
    out_tensor_shape = []
    out_matrix_shape = []
    scalar = 0

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
    isScalarGet = False

    for j, inp in enumerate(inp_list):
        # Get the name
        inp_name = inp['name']
        inp_shape = inp['shape']

        # Get A
        if (inp_name in node_mapping):
            # Check there are 4 dimensions
            if ( len(inp_shape) != 4 ):
                raise Exception(f"ERROR (in {filename}): Wrong input shape ({len(inp_shape)} dimensions when 4 are expected)! \n")
            # Get the shape
            if (isInpGet == False):
                isInpGet = True
                inp_tensor_shape = inp_shape # NCHW
            else:
                raise Exception(f"ERROR (in {filename}): Unexpected input ({inp_name})! \n")
            
            # Check consistency between input and output
            if (inp_tensor_shape != out_tensor_shape):
                raise Exception(f"ERROR (in {filename}): MulConstant should not modify the shape, but inp_tensor_shape={inp_tensor_shape} and out_tensor_shape={out_tensor_shape}! \n")


        # Get scalar
        elif (inp_name in param):
            # Empty field = metadata
            if (len(inp_shape) == 0):
                if (j == 1): # WGT SCALE
                    B_scale = param[inp_name]
                elif (j == 2): # WGT ZERO POINT
                    B_zp = param[inp_name]
                
                elif (j == 4): # INP SCALE
                    A_scale = param[inp_name]
                elif (j == 5): # INP ZERO POINT
                    A_zp = param[inp_name]
                
                elif (j == 6): # OUT SCALE
                    C_scale = param[inp_name]
                elif (j == 7): # OUT ZERO POINT
                    C_zp = param[inp_name]
            
            # Scalar
            elif (len(inp['shape']) == 1 and isScalarGet == False):
                isScalarGet = True
                scalar = param[inp['name']][0]

            # Error on the shape
            else:
                raise Exception(f"ERROR (in {filename}): Wrong input shape ({len(inp['shape'])} dimensions when 1 is expected)! \n")


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

    fh = 1
    fw = 1

    if ('strides' in attributes_dict):
        sh = attributes_dict['strides'][0]
        sw = attributes_dict['strides'][1]
    else:
        sh = 1
        sw = 1

    # attributes_dict['pads'] = [TOP, LEFT, BOTTOM, RIGHT]
    if ('pads' in attributes_dict):
        ph = (attributes_dict['pads'][0], attributes_dict['pads'][2])
        pw = (attributes_dict['pads'][1], attributes_dict['pads'][3])
    else:
        ph = (0, 0)
        pw = (0, 0)

    
    # ---
    # DEFINE MATRICES
    # ---------------

    # Define the matrix dimensions
    # ---
    inp_matrix_shape, wgt_matrix_shape, out_matrix_shape = \
        TM.im2row_matrix_dimension(nc=nc, nh=nh, nw=nw,
                                   mc=mc, mh=mh, mw=mw,
                                   fh=fh, fw=fw,
                                   sh=sh, sw=sw,
                                   ph=ph, pw=pw,
                                   debug=False)

    Ah = inp_matrix_shape[0] #mh*mw
    Aw = inp_matrix_shape[1] #nc*fh*fw


    # Transform tensor in matrix
    # ---
    # WGT
    if (B_zp != 0):
        scalar = scalar - B_zp


    # ---
    # WRITE VTA IR
    # ------------
    # Define the VTA IR
    vta_ir = {
        "NAME": filename,
        "MATRICES": {
            "A": [Ah, Aw, "../compiler_output/"+filename+"input_"+str(Ah)+"x"+str(Aw)+".bin"],
            "C": [Ah, Aw, "output"]
        },
        "LOAD": {
            "INP": ["A"]
        },
        "GEMM": ["C", "A", int( scalar )],
        "STORE": {
            "C": ["C"]
        }
    }


    # ---
    # RETURN
    # ------
    node_info.update({
        "matrix_shape": (Ah, Aw),
        "processor": "vta",
        "reshape": "im2row",
        "offsetA": A_zp,
        "offsetB": B_zp,
        "input_shape": inp_tensor_shape,
        "kernel": (fh, fw),
        "stride": (sh, sw),
        "padding": (ph[0], pw[0], ph[1], pw[1]),
        "output_shape": out_tensor_shape,
        "rescaling": (A_scale * B_scale)/C_scale,
        "offsetC": C_zp
    })

    return vta_ir, node_info

