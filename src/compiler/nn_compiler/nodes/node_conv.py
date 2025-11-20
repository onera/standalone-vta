# IMPORT PACKAGES
# ---------------
import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import utils.tensor_matrix_converter as TM



###############################################


# MAIN FUNCTION
# -------------
def node_conv(node, filename='', 
              debug=False):
    # Reset the vta_ir
    vta_ir = {}

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
                raise Exception(f"ERROR: No consistency between the output shape! \n")


    # Get the input tensors
    # ---
    for j, inp in enumerate(inp_list):
        # Get A
        if (j == 0):
            if (op_type == 'MatMul'):
                inp_tensor_shape = (inp['shape'][0], inp['shape'][1], 1, 1)
            else:
                # Check there are 4 dimensions
                if ( len(inp['shape']) != 4 ):
                    raise Exception(f"ERROR: Wrong input shape ({len(inp['shape'])} dimensions when 4 are expected)! \n")
                inp_tensor_shape = inp['shape'] # NCHW
        # Get B
        elif (j == 1):
            if (op_type == 'MatMul'):
                wgt_tensor_shape = (inp['shape'][0], inp['shape'][1], 1, 1)
            else:
                # Check there are 4 dimensions
                if ( len(inp['shape']) != 4 ):
                    raise Exception(f"ERROR: Wrong input shape ({len(inp['shape'])} dimensions when 4 are expected)! \n")
                wgt_tensor_shape = inp['shape'] # NCHW
        # Get C
        elif (j == 2):
            # Check there is only 1 dimension
            if ( len(inp['shape']) != 1 ):
                raise Exception(f"ERROR: Wrong input shape ({len(inp['shape'])} dimensions when 1 is expected)! \n")
            isBias = True
        else:
            raise Exception(f"ERROR: More inputs than expected! \n")


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
            raise Exception(f"ERROR: Kernel size not consistent! \n")

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


    # Check if there is a biais
    if (isBias == True):
        # Define the VTA IR
        vta_ir = {
            "NAME": "",
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
    else:
        # Define the VTA IR
        vta_ir = {
            "NAME": "",
            "MATRICES": {
                "A": [Ah, Aw_Bh, "../compiler_output/"+filename+"input_"+str(Ah)+"x"+str(Aw_Bh)+".bin"],
                "B": [Aw_Bh, Bw, "../compiler_output/"+filename+"weight_"+str(Aw_Bh)+"x"+str(Bw)+".bin"],
                "C": [Ah, Bw, "output"]
            },
            "LOAD": {
                "INP": ["A"],
                "WGT": ["B"]
            },
            "GEMM": ["C", "A", "B"],
            "STORE": {
                "C": ["C"]
            }
        }


    # Return
    # ---
    return vta_ir, (Ah, Aw_Bh, Bw), isBias



###############################################


# MUL CONSTANT
# ------------
def node_mulconstant(node, filename='', 
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
                raise Exception(f"ERROR: No consistency between the output shape! \n")


    # Get the input tensors
    # ---
    if ( len(inp_list) > 2 ):
        raise Exception(f"ERROR: There are {len(inp_list)} when 2 are expected! \n")
    for j, inp in enumerate(inp_list):
        # Get A
        if ( len(inp['shape']) == 4 ):
            inp_tensor_shape = inp['shape'] # NCHW
            # Check consistency between input and output
            if (inp_tensor_shape != out_tensor_shape):
                raise Exception(f"ERROR: MulConstant should not modify the shape, but inp_tensor_shape={inp_tensor_shape} and out_tensor_shape={out_tensor_shape}! \n")

        # Get scalar
        elif ( len(inp['shape']) == 1 ):
            scalar = inp['shape'][0] # TODO: take the initialiser and not the shape...
        # Else problem # TODO: Check for bias
        else:
            raise Exception(f"ERROR: Input {inp} was not expected! \n")


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
            "NAME": "",
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
            "NAME": "",
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
    return vta_ir, (Ah, Aw), isBias

