# IMPORT PACKAGES
# ---------------
import os
import sys

import json

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils.find_project_root import *
import utils.random_raw_binary_generator as RRBG

import nn_compiler.parser.parse_onnx_to_dict as PO
import nn_compiler.nodes.node_conv as Nconv
import nn_compiler.nodes.node_pool as Npool


###############################################


# MAIN FUNCTION
# -------------
def vta_backend(onnx_model_path, 
                debug=True):

    # PARSING the ONNX model
    # ----------------------
    model_dict, dict_name_index = PO.parse_onnx_to_dict(model_path=onnx_model_path, debug=debug)

    # Input nodes
    input_nodes = model_dict['inputs']
    # Output nodes
    output_nodes = model_dict['outputs']

    # Compute nodes
    compute_nodes = model_dict['nodes']


    # GET THE NODES
    # -------------
    vta_ir_list = []

    for i, cpt_node in enumerate(compute_nodes):
        # Reset the vta_ir
        vta_ir = {}

        # Get the metadata
        index = cpt_node['index']
        # name = cpt_node['name']
        op_type = cpt_node['op_type']

        # Define the name
        filename = op_type + str(index)


        # Define operation for each task
        # ---
        # Convolution or Fully-Connected
        if (op_type == "Conv" or op_type == "MatMul"): 
            # Get data from the node
            vta_ir, (Ah, Aw_Bh, Bw), isBias = Nconv.node_conv(node=cpt_node, filename=filename, debug=False)

            # Generate the associated binaries
            RRBG.random_raw_binary_generator(m_rows=Ah, n_columns=Aw_Bh, filename=filename+"input", dtype='int8', debug=False)
            RRBG.random_raw_binary_generator(m_rows=Aw_Bh, n_columns=Bw, filename=filename+"weight", dtype='int8', debug=False)
            if (isBias == True):
                RRBG.random_raw_binary_generator(m_rows=Ah, n_columns=Bw, filename=filename+"accumulator", dtype='int32', debug=False)

            # Append the VTA IR list
            vta_ir_list.append( (filename, vta_ir.copy()) )

        # ---

        # Pooling
        elif (op_type == "MaxPool"): 
            # Get data from the node
            vta_ir, (Xh, Xw) = Npool.node_pool(node=cpt_node, filename=filename, debug=False)

            # Generate the associated binaries
            RRBG.random_raw_binary_generator(m_rows=Xh, n_columns=Xw, filename=filename+"accumulator", dtype='int32', debug=False)

            # Append the VTA IR list
            vta_ir_list.append( (filename, vta_ir.copy()) )

        # ---

        # MulConstant
        elif (op_type == "Mul"): 
            # Get data from the node
            vta_ir, (Ah, Aw), isBias = Nconv.node_mulconstant(node=cpt_node, filename=filename, debug=False)

            # Generate the associated binaries
            RRBG.random_raw_binary_generator(m_rows=Ah, n_columns=Aw, filename=filename+"input", dtype='int8', debug=False)
            if (isBias == True):
                RRBG.random_raw_binary_generator(m_rows=Ah, n_columns=Aw, filename=filename+"accumulator", dtype='int32', debug=False)

            # Append the VTA IR list
            vta_ir_list.append( (filename, vta_ir.copy()) )

        # ---

        # Add (ADD ACC) != Bias adding # TODO
        elif (op_type == "Add"): 
            pass

        # ---

        # Others
        else:
            pass

        
    # WRITE VTA IR
    # ------------
    # Manage the output dir
    output_dir = compiler_output_setup()
    for filename, current_vta_ir in vta_ir_list:
        # Manage the file_path
        file_path = filepath_definition(output_dir, filename+'.json')
        # Write dict in a JSON
        with open(file_path, 'w') as f:
            json.dump(current_vta_ir, f, indent=2) # indent=2 for better readibility


    # ---------------------------------------------
    # DEBUG
    if (debug):
        # VTA IR DECODING
        print(f"\nVTA BACKEND: \n There are {len(vta_ir_list)} VTA IR. \n")
        for ir in vta_ir_list:
            print(f"Name: {ir[0]} \n\t {ir[1]} \n")

    # ---------------------------------------------
    # RETURN new base_address
    return 0


###############################################


# EXECUTE MAIN FUNCTION
# ---------------------
if __name__ == "__main__": 
    """
    To execute: 
        > python main_vta_compiler.py 
            <onnx_model_path> 
    """
    debug = True

    onnx_selector = 3

    # Test ONNX
    if (onnx_selector == 1): # Non-quantised LeNet-5
        onnx_default = "/home/afauregi/Documents/onnx_zoo/mnist-12.onnx" 
    elif (onnx_selector == 2): # Quantised LeNet-5
        onnx_default = "/home/afauregi/Documents/onnx_zoo/mnist-12-int8.onnx" 
    elif (onnx_selector == 3): # Non-quantised Yolo
        onnx_default = "/home/afauregi/Documents/onnx_zoo/yolonas.onnx" 
    elif (onnx_selector == 4): # Quantised Yolo
        onnx_default = "/home/afauregi/Documents/onnx_zoo/yolonas_quantized_using_ONNX.onnx" 

    
    # Need at least 3: script_name, config_file, 1_json_file
    if (len(sys.argv) == 1):
        onnx_model_path = onnx_default
        # onnx_model_path = "/home/afauregi/Documents/onnx_zoo/yolonas_quantized_using_ONNX.onnx" 
    elif (len(sys.argv) == 2):
        onnx_model_path = sys.argv[1]

    # Execute the backend
    result = vta_backend(onnx_model_path, debug=debug)

    # END!
