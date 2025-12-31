# IMPORT PACKAGES
# ---------------
import os
import sys

import numpy as np

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import utils.tensor_matrix_converter as TM



###############################################


# MAIN FUNCTION
# -------------
def node_pool(node, param={}, node_mapping={}, node_info={}, filename='', 
              inp_dtype=np.int8, wgt_dtype=np.int8, acc_dtype=np.int32,
              debug=False):
    # Reset the vta_ir
    vta_ir = {}

    # Get the metadata
    # ---
    op_type = node['op_type']
    inp_list = node['inputs']
    out_list = node['outputs']
    attributes_dict = node['attributes']

    # Protect against other pooling
    if (op_type != "MaxPool"):
        raise Exception(f"ERROR (in {filename}): {op_type} not supported yet, only MaxPool! \n")

    # Reset the node data
    # ---
    acc_tensor_shape = []
    out_tensor_shape = []


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
    if ( len(inp_list) > 1 ):
        raise Exception(f"ERROR (in {filename}): There are {len(inp_list)} when 1 is expected! \n")

    for j, inp in enumerate(inp_list):
        # Get the name
        inp_name = inp['name']

        # Get X (be careful, it is in int32)
        if (inp_name in node_mapping):
            # Check there are 4 dimensions
            if ( len(inp['shape']) != 4 ):
                raise Exception(f"ERROR (in {filename}): Wrong input shape ({len(inp['shape'])} dimensions when 4 are expected)! \n")
            # Get the shape
            acc_tensor_shape = inp['shape'] # NCHW

        # Else problem 
        else:
            raise Exception(f"ERROR (in {filename}): Unexpected input ({inp_name}) which does not come from another node nor parameters! \n")


    # Get the attributes
    # ---
    fh = attributes_dict['kernel_shape'][0]
    fw = attributes_dict['kernel_shape'][1]
    kernel_size = fh*fw

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

    nc = acc_tensor_shape[1] 
    nh = acc_tensor_shape[2] + ph[0] + ph[1]
    nw = acc_tensor_shape[3] + pw[0] + pw[1]

    mc = out_tensor_shape[1]
    mh = out_tensor_shape[2]
    mw = out_tensor_shape[3]

    # Nc and Mc must be the same
    if (nc != mc):
        raise Exception(f"ERROR (in {filename}): Discrepency on the number of channels (nc={nc}, mc={mc})! \n")


    # Define the matrix dimensions
    # ---
    Xh = nh*nw
    Xw = nc

    Ch = mh*mw
    Cw = mc

    nb_to_store = mh*mw # The number of slice

    # Define the ALU and the store
    # ---
    operations_alu = []
    store_list = []

    # Iterate over the width slices
    for col in range(0, mh):
        # Iterate over the height slices
        for row in range (0, mw):
            # Define the position in the tensor domain
            y = col * (sh * nw) # Row
            x = y + row * sw # Row + col

            # Define the position in the matrix domain (flat tensor)
            dst_idx = x 
            # Iterate over the kernel to find SRC
            for i in range(0, fh):
                # Define SRC and iteration
                if (i == 0):
                    src_idx = dst_idx + 1
                    iteration = fw - 1
                else: 
                    src_idx = dst_idx + i*nw
                    iteration = fw

                # Append the list for each SRC
                operations_alu.append(
                    ["MAX", [[dst_idx,0], [src_idx,1], iteration]]
                )

            # Append the list for each DST
            store_list.append( [[dst_idx, 0], 1] )


    # Define the VTA IR
    # ---
    vta_ir = {
        "NAME": filename,
        "MATRICES": {
            "X": [Xh, Xw, "../compiler_output/"+filename+"accumulator_"+str(Xh)+"x"+str(Xw)+".bin"],
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


    # Return
    # ---
    node_info.update({
        "matrix_shape": (Xh, Xw),
        "processor": "vta",
        "reshape": "int32",
        "offsetA": 0,
        "scaleA": 1.,
        "offsetB": 0,
        "scaleB": 1.,
        "input_shape": acc_tensor_shape,
        "kernel": (fh, fw),
        "stride": (sh, sw),
        "padding": (ph[0], pw[0], ph[1], pw[1]),
        "output_shape": out_tensor_shape,
        "offsetC": 0,
        "scaleC": 1.,
        "rescaling": 1.
    })

    return vta_ir, node_info
