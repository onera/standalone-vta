# IMPORT PACKAGES
# ---------------
import os
import sys

import numpy as np

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import utils.tensor_matrix_converter as TM



###############################################


# RELU
# ----
def node_relu(node, param={}, node_mapping={}, node_info={}, filename='', 
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
            # Check consistency
            if ( acc_tensor_shape != out_tensor_shape):
                raise Exception(f"ERROR (in {filename}): ReLU should not modify the shape but  acc_tensor_shape={acc_tensor_shape} and out_tensor_shape={out_tensor_shape}! \n")

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
        raise Exception(f"ERROR (in {filename}): ReLU should not have attributes but have attributes_dict={attributes_dict}! \n")


    # Define the matrix dimensions
    # ---
    Xh = nh*nw
    Xw = nc

    Ch = mh*mw
    Cw = mc

    # Define the ALU 
    # ---
    operations_alu = []

    # Append the list
    operations_alu.append(
        ["MAX_IMM", [[0,1], 0, Xh]]
    )


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
            "C": ["C"]
        }
    }


    # Return
    # ---
    node_info.update({
        "matrix_shape": (Ah, Aw_Bh, Bw),
        "processor": "vta",
        "reshape": "int32",
        "offsetA": 0,
        "offsetB": 0,
        "input_shape": acc_tensor_shape,
        "kernel": (1, 1),
        "stride": (1, 1),
        "padding": (0, 0, 0, 0),
        "output_shape": out_tensor_shape,
        "rescaling": 1.,
        "offsetC": 0
    })

    return vta_ir, node_info
