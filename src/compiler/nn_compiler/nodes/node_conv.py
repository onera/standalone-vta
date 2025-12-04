# IMPORT PACKAGES
# ---------------
import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils.find_project_root import *
import utils.tensor_matrix_converter as TM

import nn_compiler.shape_data.shape_data as SD



###############################################


# MAIN FUNCTION
# -------------
def node_conv(node, param={}, node_mapping={}, filename='',
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
    for j, out in enumerate(out_list):
        # Get the output tensor shape
        if (j == 0):
            if (op_type == 'MatMul'):
                out_tensor_shape = (out['shape'][0], out['shape'][1], 1, 1) 
            else:
                out_tensor_shape = out['shape'] # NCHW
        else: # if multiple output, all must have the same shape
            if (out['shape'] != out_tensor_shape):
                raise Exception(f"ERROR (in {filename}): No consistency between the output shape! \n")


    # Get the input tensors
    # ---
    # Count the nodes
    idx_nodes = 0

    for j, inp in enumerate(inp_list):
        # Get the name
        inp_name = inp['name']

        # Get A
        if (inp_name in node_mapping):
            if (op_type == 'MatMul'):
                # Check there are 2 dimensions
                if ( len(inp['shape']) != 2 ):
                    raise Exception(f"ERROR (in {filename}): Wrong input shape ({len(inp['shape'])} dimensions when 2 are expected)! \n")
                # Get the shape
                if (idx_nodes == 0):
                    inp_tensor_shape = (inp['shape'][0], inp['shape'][1], 1, 1)
                elif (idx_nodes == 1):
                    wgt_tensor_shape = (inp['shape'][0], inp['shape'][1], 1, 1)
                else:
                    raise Exception(f"ERROR (in {filename}): Unexpected input ({inp_name})! \n")
            else:
                # Check there are 4 dimensions
                if ( len(inp['shape']) != 4 ):
                    raise Exception(f"ERROR (in {filename}): Wrong input shape ({len(inp['shape'])} dimensions when 4 are expected)! \n")
                # Get the shape
                if (idx_nodes == 0):
                    inp_tensor_shape = inp['shape'] # NCHW
                elif (idx_nodes == 1):
                    wgt_tensor_shape = inp['shape'] # NCHW
                else:
                    raise Exception(f"ERROR (in {filename}): Unexpected input ({inp_name})! \n")

            # Increment idx
            idx_nodes = idx_nodes + 1
        
        # Get B or X
        elif (inp_name in param):
            # Empty field = metadata
            if (len(inp['shape']) == 0):
                if (j == 1): # INP SCALE
                    A_scale = param[inp['name']]
                elif (j == 2): # INP ZERO POINT
                    A_zp = param[inp['name']]
                
                elif (j == 4): # WGT SCALE
                    B_scale = param[inp['name']]
                elif (j == 5): # WGT ZERO POINT
                    B_zp = param[inp['name']]
                
                elif (j == 6): # OUT SCALE
                    C_scale = param[inp['name']]
                elif (j == 7): # OUT ZERO POINT
                    C_zp = param[inp['name']]

            # X (bias)
            elif (len(inp['shape']) == 1):
                isBias = True
                acc_tensor = param[inp['name']]

            else: # B (weight)
                if (op_type == 'MatMul'):
                    # Check there are 2 dimensions
                    if ( len(inp['shape']) != 2 ):
                        raise Exception(f"ERROR (in {filename}): Wrong input shape ({len(inp['shape'])} dimensions when 2 are expected)! \n")
                    wgt_tensor_shape = (inp['shape'][0], inp['shape'][1], 1, 1)
                    wgt_tensor = param[inp['name']]
                else:
                    # Check there are 4 dimensions
                    if ( len(inp['shape']) != 4 ):
                        raise Exception(f"ERROR (in {filename}): Wrong input shape ({len(inp['shape'])} dimensions when 4 are expected)! \n")
                    wgt_tensor_shape = inp['shape'] # NCHW
                    wgt_tensor = param[inp['name']]
        
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
    if (isBias == True):
        acc_matrix = SD.expand_bias(acc_tensor, Ah)
    else:
        acc_matrix = np.zeros((n, m), dtype=np.int32)


    # ---
    # WRITE VTA IR
    # ------------
    # Check if there is a biais
    if (op_type == 'QLinearConv'):
        # Compute rescale factor
        M = (A_scale * B_scale) / C_scale
        n = 16
        P = round( M * (2**n) )
        print(f"\nDEBUG: P={P}, {M * (2**n)} \n\n")
        rescaling_bias = int( (2**(n-1)) )

        # Define ALU
        if (C_zp != 0):
            alu_operations = [
                ["MUL_IMM", [[0,1], P, Ah]],
                ["ADD_IMM", [[0,1], rescaling_bias, Ah]],
                ["SHR_IMM", [[0,1], n, Ah]],
                ["ADD_IMM", [[0,1], int( C_zp + 1 ), Ah]],
                ["MAX_IMM", [[0,1], -128, Ah]],
                ["MIN_IMM", [[0,1], 127, Ah]]
            ]
        else:
            alu_operations = [
                ["MUL_IMM", [[0,1], P, Ah]],
                ["ADD_IMM", [[0,1], rescaling_bias, Ah]],
                ["SHR_IMM", [[0,1], n, Ah]],
                ["MAX_IMM", [[0,1], -128, Ah]],
                ["MIN_IMM", [[0,1], 127, Ah]]
            ]

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
            "ALU" : {
                "C": alu_operations
            },
            "STORE": {
                "C": ["C"]
            }
        }

    else:
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
    info = {
        "matrix_shape": (Ah, Aw_Bh, Bw),
        "tensor_shape": (inp_tensor_shape, out_tensor_shape),
        "padding": (ph[0], pw[0], ph[1], pw[1]),
        "stride": (sh, sw),
        "kernel": (fh, fw)
    }

    return vta_ir, info, isBias



###############################################


# MUL CONSTANT
# ------------
def node_mulconstant(node, param={}, node_mapping={}, filename='',
                     debug=False):
    # Reset the vta_ir
    vta_ir = {}

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
    isBias = False


    # Get the output tensors
    # ---
    for j, out in enumerate(out_list):
        # Get the output tensor shape
        if (j == 0):
            out_tensor_shape = out['shape'] # NCHW
        else: # if multiple output, all must have the same shape
            if (out['shape'] != out_tensor_shape):
                raise Exception(f"ERROR (in {filename}): No consistency between the output shape! \n")


    # Get the input tensors
    # ---
    for j, inp in enumerate(inp_list):
        # Get the name
        inp_name = inp['name']

        # Get A
        if (inp_name in node_mapping):
            # Check there are 4 dimensions
            if ( len(inp['shape']) != 4 ):
                raise Exception(f"ERROR (in {filename}): Wrong input shape ({len(inp['shape'])} dimensions when 4 are expected)! \n")
            # Get the shape
            inp_tensor_shape = inp['shape'] # NCHW
            # Check consistency between input and output
            if (inp_tensor_shape != out_tensor_shape):
                raise Exception(f"ERROR (in {filename}): MulConstant should not modify the shape, but inp_tensor_shape={inp_tensor_shape} and out_tensor_shape={out_tensor_shape}! \n")

        # Get scalar
        elif (inp_name in param):
            # Empty field
            if (len(inp['shape']) == 0):
                pass
            
            # Scalar
            elif (len(inp['shape']) == 1):
                scalar = round( param[inp['name']][0] )

            # Error on the shape
            else:
                raise Exception(f"ERROR (in {filename}): Wrong input shape ({len(inp['shape'])} dimensions when 1 is expected)! \n")
                
            # TODO: Check for bias

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


    # Check if there is a biais
    if (isBias == True):
        # Define the VTA IR
        vta_ir = {
            "NAME": filename,
            "MATRICES": {
                "A": [Ah, Aw, "../compiler_output/"+filename+"input_"+str(Ah)+"x"+str(Aw)+".bin"],
                "X": [Ah, Aw, "../compiler_output/"+filename+"accumulator_"+str(Ah)+"x"+str(Aw)+".bin"],
                "C": [Ah, Aw, "output"]
            },
            "LOAD": {
                "INP": ["A"],
                "ACC": ["X"]
            },
            "GEMM": ["C", "A", scalar],
            "STORE": {
                "C": ["C"]
            }
        }
    else:
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
            "GEMM": ["C", "A", scalar],
            "STORE": {
                "C": ["C"]
            }
        }


    # Return
    # ---
    info = {
        "matrix_shape": (Ah, Aw),
        "tensor_shape": (inp_tensor_shape, out_tensor_shape),
        "padding": (ph[0], pw[0], ph[1], pw[1]),
        "stride": (sh, sw),
        "kernel": (fh, fw)
    }

    return vta_ir, info, isBias

