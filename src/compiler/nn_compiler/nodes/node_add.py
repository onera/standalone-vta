# IMPORT PACKAGES
# ---------------
import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import utils.tensor_matrix_converter as TM



###############################################


# ADD
# ---
def node_add(node, param={}, node_mapping={}, filename='',
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
    isBias = False
    isFlat = False


    # Get the output tensors
    # ---
    for j, out in enumerate(out_list):
        # Get the output tensor shape
        if (j == 0):
            if (len(out['shape']) == 4):
                out_tensor_shape = out['shape'] # NCHW
            elif (len(out['shape']) == 2):
                out_tensor_shape = (out['shape'][0], out['shape'][1], 1, 1) 
                isFlat = True
            else:
                raise Exception(f"ERROR: Add does not support this tensor shape yet ({out['shape']})! \n")

        else: # if multiple output, all must have the same shape
            if (out['shape'] != out_list[0]['shape']):
                raise Exception(f"ERROR: No consistency between the output shape! \n")


    # Get the input tensors
    # ---
    if (len(inp_list) > 2):
        raise Exception(f"ERROR: Add should have 2 input tensors whereas it has {len(inp_list)}! \n")

    # Count the nodes
    idx_nodes = 0

    for j, inp in enumerate(inp_list):
        # Get the name
        inp_name = inp['name']

        # Get X and Y (be careful, it is in int32) -> X.shape = Y.shape
        if (inp_name in node_mapping):
            if (idx_nodes > 0):
                # Check the consistency between both inputs
                if (inp['shape'] != acc_tensor_shape):
                    raise Exception(f"ERROR: Add must add 2 same shape tensors! \n")

            elif (isFlat == True):
                # Check there are 2 dimensions
                if ( len(inp['shape']) != 2 ):
                    raise Exception(f"ERROR: Wrong input shape ({len(inp['shape'])} dimensions when 2 are expected)! \n")
                # Get the shape
                acc_tensor_shape = (inp['shape'][0], inp['shape'][1], 1, 1)
                # Check consistency between input and output
                if (acc_tensor_shape != out_tensor_shape):
                    raise Exception(f"ERROR: Add should not modify the shape but acc_tensor_shape={acc_tensor_shape} and out_tensor_shape={out_tensor_shape}! \n")

            else:
                # Check there are 4 dimensions
                if ( len(inp['shape']) != 4 ):
                    raise Exception(f"ERROR: Wrong input shape ({len(inp['shape'])} dimensions when 4 are expected)! \n")
                # Get the shape
                acc_tensor_shape = inp['shape'] # NCHW
                # Check consistency between input and output
                if (acc_tensor_shape != out_tensor_shape):
                    raise Exception(f"ERROR: Add should not modify the shape but acc_tensor_shape={acc_tensor_shape} and out_tensor_shape={out_tensor_shape}! \n")

            # Increment idx
            idx_nodes = idx_nodes + 1

        # Get bias
        elif (inp_name in param):
            isBias == True
            # When (isFlat == True) -> bias.shape = 2, else 3
            if (isFlat == True): # If it is flat, it is bias!
                isBias == True

        # Else problem 
        else:
            raise Exception(f"ERROR: Unexpected input ({inp_name}) which does not come from another node nor parameters! \n")



    # Get the attributes
    # ---
    nc = acc_tensor_shape[1]
    nh = acc_tensor_shape[2]
    nw = acc_tensor_shape[3]

    mc = out_tensor_shape[1]
    mh = out_tensor_shape[2]
    mw = out_tensor_shape[3]

    if (len(attributes_dict) > 0):
        raise Exception(f"ERROR: Add should not have attributes but have attributes_dict={attributes_dict}! \n")


    # Define the matrix dimensions
    # ---
    Xh = nh*nw
    Xw = nc

    Ch = mh*mw
    Cw = mc

    # Define the VTA IR
    # ---
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


    # Return
    # ---
    info = {
        "matrix_shape": (Xh, Xw),
        "tensor_shape": (acc_tensor_shape, out_tensor_shape),
        "padding": (0, 0, 0, 0),
        "stride": (1, 1),
        "kernel": (1, 1)
    }

    return vta_ir, info, isBias
