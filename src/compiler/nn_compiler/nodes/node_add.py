# IMPORT PACKAGES
# ---------------
import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import utils.tensor_matrix_converter as TM



###############################################


# ADD
# ---
def node_add(node, filename='', param={},
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
    acc_matrix_shape = []
    out_tensor_shape = []
    out_matrix_shape = []
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

    for j, inp in enumerate(inp_list):
        # Get X
        if (j == 0):
            if (isFlat == True):
                inp_tensor_shape = (inp['shape'][0], inp['shape'][1], 1, 1)
                if (len(inp['shape']) != 2): 
                    raise Exception(f"ERROR: Shape must be 2 and is {len(inp['shape'])}! \n")
                elif (inp_tensor_shape != out_tensor_shape):
                    raise Exception(f"ERROR: Add should not modify the shape but inp_tensor_shape={inp_tensor_shape} and out_tensor_shape={out_tensor_shape}! \n")

            else:
                inp_tensor_shape = inp['shape'] # NCHW
                if (len(inp['shape']) != 4): 
                    raise Exception(f"ERROR: Shape must be 4 and is {len(inp['shape'])}! \n")
                elif (inp_tensor_shape != out_tensor_shape):
                    raise Exception(f"ERROR: Add should not modify the shape but inp_tensor_shape={inp_tensor_shape} and out_tensor_shape={out_tensor_shape}! \n")

        # Get Y or Bias
        elif (j == 1):
            if (isFlat == True): # If it is flat, it is bias!
                isBias == True
                if (len(inp['shape']) != 2):
                    raise Exception(f"ERROR: Shape must be 2 and is {len(inp['shape'])}! \n")

            else:
                if (len(inp['shape']) == 4):
                    isBias = False
                    if (inp['shape'] != inp_tensor_shape):
                        raise Exception(f"ERROR: Add must add 2 same shape tensors! \n")
                else:
                    isBias = True


    # Get the attributes
    # ---
    nc = inp_tensor_shape[1]
    nh = inp_tensor_shape[2]
    nw = inp_tensor_shape[3]

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
        "NAME": "",
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
    return vta_ir, (Xh, Xw), isBias
