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
import nn_compiler.nodes.node_add as Nadd
import nn_compiler.nodes.node_activation as Nactivation


###############################################


# MAIN FUNCTION
# -------------
def vta_backend(onnx_model_path, doGenerateBin=False,
                debug=True):

    # PARSING the ONNX model
    # ----------------------
    model_dict, dict_name_index = PO.parse_onnx_to_dict(model_path=onnx_model_path, debug=debug)
    model_param = PO.get_onnx_parameters(model_path=onnx_model_path, debug=debug)

    # Input nodes
    input_nodes = model_dict['inputs']
    # Output nodes
    output_nodes = model_dict['outputs']

    # Compute nodes
    compute_nodes = model_dict['nodes']


    # GET THE NODES
    # -------------
    vta_ir_list = []

    # List the VTA compatible nodes and get the index of each
    vta_compatible_node = [
        # GeMM
        'Conv',
        'MatMul', # As conv
        'Mul', # MulConstant
        # ALU
        'Relu',
        'Add', # Both ADD_ACC and ADD BIAS
        'MaxPool',
        # Special (must be divided into CPU and VTA)
        'ConvTranspose'
    ]
    vta_node_idx_list = []
    cpu_node_list = []

    for i, cpt_node in enumerate(compute_nodes):
        # Reset the vta_ir
        vta_ir = {}

        # Get the metadata
        index = cpt_node['index']
        # name = cpt_node['name']
        op_type = cpt_node['op_type']

        # Get the index of the VTA executable nodes
        if (op_type in vta_compatible_node):
            vta_node_idx_list.append(index)
        else: # Not compatible
            cpu_node_list.append( (index, op_type) )
            continue # No need to finish this loop


        # Define the name
        filename = op_type + str(index)

        # Define operation for each task
        # ---
        # Convolution or Fully-Connected
        if (op_type == "Conv" or op_type == "MatMul"): 
            # Get data from the node
            vta_ir, (Ah, Aw_Bh, Bw), isBias = Nconv.node_conv(node=cpt_node, param=model_param, node_mapping=dict_name_index, filename=filename, debug=False)

            # Generate the associated binaries
            if (doGenerateBin):
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
            vta_ir, (Xh, Xw) = Npool.node_pool(node=cpt_node, param=model_param, node_mapping=dict_name_index, filename=filename, debug=False)

            # Generate the associated binaries
            if (doGenerateBin):
                RRBG.random_raw_binary_generator(m_rows=Xh, n_columns=Xw, filename=filename+"accumulator", dtype='int32', debug=False)

            # Append the VTA IR list
            vta_ir_list.append( (filename, vta_ir.copy()) )

        # ---

        # MulConstant
        elif (op_type == "Mul"): 
            # Get data from the node
            vta_ir, (Ah, Aw), isBias = Nconv.node_mulconstant(node=cpt_node, param=model_param, node_mapping=dict_name_index, filename=filename, debug=False)

            # Generate the associated binaries
            if (doGenerateBin):
                RRBG.random_raw_binary_generator(m_rows=Ah, n_columns=Aw, filename=filename+"input", dtype='int8', debug=False)
                if (isBias == True):
                    RRBG.random_raw_binary_generator(m_rows=Ah, n_columns=Aw, filename=filename+"accumulator", dtype='int32', debug=False)

            # Append the VTA IR list
            vta_ir_list.append( (filename, vta_ir.copy()) )

        # ---

        # Activation
        elif (op_type == "Relu"): 
            # Get data from the node
            vta_ir, (Xh, Xw) = Nactivation.node_relu(node=cpt_node, param=model_param, node_mapping=dict_name_index, filename=filename, debug=False)

            # Generate the associated binaries
            if (doGenerateBin):
                RRBG.random_raw_binary_generator(m_rows=Xh, n_columns=Xw, filename=filename+"accumulator", dtype='int32', debug=False)

            # Append the VTA IR list
            vta_ir_list.append( (filename, vta_ir.copy()) )

        # ---

        # ADD
        elif (op_type == "Add"): 
            # Get data from the node
            vta_ir, (Xh, Xw), isBias = Nadd.node_add(node=cpt_node, param=model_param, node_mapping=dict_name_index, filename=filename, debug=False)

            # Generate the associated binaries
            if (doGenerateBin):
                RRBG.random_raw_binary_generator(m_rows=Xh, n_columns=Xw, filename=filename+"accumulator", dtype='int32', debug=False)
                RRBG.random_raw_binary_generator(m_rows=Xh, n_columns=Xw, filename=filename+"accbis", dtype='int32', debug=False)

            # Append the VTA IR list
            vta_ir_list.append( (filename, vta_ir.copy()) )

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
        print(f"\nVTA BACKEND: ")
        nb_total = len(compute_nodes)
        print(f"\t Nb nodes: {nb_total}")
        nb_vta = len(vta_node_idx_list)
        print(f"\t Nb VTA-compatible nodes: {nb_vta}")
        nb_ir = len(vta_ir_list)
        print(f"\t Nb VTA IR: {nb_ir}")
        nb_cpu = len(cpu_node_list)
        print(f"\t Nb CPU nodes: {nb_cpu}")
        if (nb_total != nb_vta + nb_cpu):
            raise Exception(f"ERROR: nb_total={nb_total} but nb_vta+nb_cpu={nb_vta + nb_cpu}! \n")

        print(f"\nStatistics: \n\t % nodes on VTA: {nb_vta/nb_total} \n\t % VTA IR on possible: {nb_ir/nb_vta} \n")

        if (nb_ir != nb_vta):
            todo_list = []
            for i in vta_node_idx_list:
                if any( ir[0].endswith(str(i)) for ir in vta_ir_list ):
                    continue
                else:
                    todo_list.append( (i, compute_nodes[i-1]['op_type']) )
            print(f"todo_list={todo_list} \n")

        print(f"cpu_node_list={cpu_node_list} \n")
        print(f"vta_node_idx_list={vta_node_idx_list} \n")
        print(f"vta_ir_list: \n")

        for ir in vta_ir_list:
            print(f"Name: {ir[0]} \n\t {ir[1]} \n")

    # ---------------------------------------------
    # RETURN 
    return 0


###############################################


# EXECUTE MAIN FUNCTION
# ---------------------
if __name__ == "__main__": 
    """
    To execute: 
        > python vta_backend.py 
            <onnx_model_path> 
            <doGenerateBin>
            <debug>
    """
    doGenerateBin = False
    debug = True

    if (len(sys.argv) == 1):
        onnx_model_path = "../../../../onnx_zoo/yolonas.onnx" 
    elif (len(sys.argv) == 2):
        onnx_model_path = sys.argv[1]
    elif (len(sys.argv) == 3):
        onnx_model_path = sys.argv[1]
        doGenerateBin = True if (sys.argv[2] == 'true' or sys.argv[2] == 'True') else False
    elif (len(sys.argv) == 4):
        onnx_model_path = sys.argv[1]
        doGenerateBin = True if (sys.argv[2] == 'true' or sys.argv[2] == 'True') else False
        debug = True if (sys.argv[3] == 'true' or sys.argv[3] == 'True') else False


    # Execute the backend
    result = vta_backend(onnx_model_path, doGenerateBin=doGenerateBin, debug=debug)

    # END!
