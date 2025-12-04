# IMPORT PACKAGES
# ---------------
import os
import sys

import json
import csv

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils.find_project_root import *
import utils.random_raw_binary_generator as RRBG

import nn_compiler.parser.parse_onnx_to_dict as PO
import nn_compiler.parser.get_input_nodes as PG
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
    vta_compatible_nodes = [
        # GeMM
        'Conv', 'QLinearConv',
        'MatMul', # As conv
        'Mul', 'QLinearMul', # MulConstant
        # ALU
        'Relu',
        'Add', 'QLinearAdd', # Both ADD_ACC and ADD BIAS
        'MaxPool',
        # Special (must be divided into CPU and VTA)
        'ConvTranspose'
    ]
    vta_node_idx_list = []
    cpu_node_list = []


    # GET EXECUTION ORDER
    # -------------------
    execution_order = []


    # GENERATE VTA IR
    # ---------------
    for i, cpt_node in enumerate(compute_nodes):
        # Reset the vta_ir
        vta_ir = {}

        # Get the metadata
        index = cpt_node['index']
        # name = cpt_node['name']
        op_type = cpt_node['op_type']

        # Get the index of the VTA executable nodes
        if (op_type in vta_compatible_nodes):
            vta_node_idx_list.append(index)
        else: # Not compatible
            cpu_node_list.append( (index, op_type) )
            continue # No need to finish this loop

        # Define the name
        filename = op_type + str(index)

        # Reset node_dependency
        input_dependency = PG.get_input_nodes(compute_nodes=compute_nodes, input_nodes=cpt_node['inputs'], dict_name_index=dict_name_index) 

        node_dependency = {
            "node_name": filename,
            "processor": "cpu",
            "reshape": False,
            "offset": 0,
            "input_shape": [0,0,0,0],
            "output_shape": [0,0,0,0],
            "kernel": [0,0],
            "stride": [0,0],
            "padding": [0,0,0,0],
            "input_nodes": input_dependency.copy()
        }

        # Define operation for each task
        # ---
        # Convolution or Fully-Connected
        if (op_type == "Conv" or op_type == "QLinearConv" or op_type == "MatMul"): 
            # Get data from the node
            vta_ir, info = \
                Nconv.node_conv(node=cpt_node, param=model_param, node_mapping=dict_name_index, filename=filename, debug=False)

            # Generate the associated binaries
            if (doGenerateBin):
                Ah = info['matrix_shape'][0]
                Aw_Bh = info['matrix_shape'][1]
                Bw = info['matrix_shape'][2]

                RRBG.random_raw_binary_generator(m_rows=Ah, n_columns=Aw_Bh, filename=filename+"input", dtype='int8', debug=False)

            # Append the VTA IR list
            vta_ir_list.append( (filename, vta_ir.copy()) )

            # Update dependency
            node_dependency['processor'] = "vta"
            if (node_dependency['input_nodes'][0] == "Image"):
                node_dependency['reshape'] = False
            else:
                node_dependency['reshape'] = True
            node_dependency['offset'] = info['offset']
            node_dependency['input_shape'] = info['tensor_shape'][0]
            node_dependency['output_shape'] = info['tensor_shape'][1]
            node_dependency['kernel'] = info['kernel']
            node_dependency['stride'] = info['stride']
            node_dependency['padding'] = info['padding']

        # ---

        # Pooling
        elif (op_type == "MaxPool"): 
            # Get data from the node
            vta_ir, info = \
                Npool.node_pool(node=cpt_node, param=model_param, node_mapping=dict_name_index, filename=filename, debug=False)

            # Generate the associated binaries
            if (doGenerateBin):
                Xh = info['matrix_shape'][0]
                Xw = info['matrix_shape'][1]

                RRBG.random_raw_binary_generator(m_rows=Xh, n_columns=Xw, filename=filename+"accumulator", dtype='int32', debug=False)

            # Append the VTA IR list
            vta_ir_list.append( (filename, vta_ir.copy()) )

            # Update dependency
            node_dependency['processor'] = "vta"
            if (node_dependency['input_nodes'][0] == "Image"):
                node_dependency['reshape'] = False
            else:
                node_dependency['reshape'] = "int32"
            node_dependency['offset'] = info['offset']
            node_dependency['input_shape'] = info['tensor_shape'][0]
            node_dependency['output_shape'] = info['tensor_shape'][1]
            node_dependency['kernel'] = info['kernel']
            node_dependency['stride'] = info['stride']
            node_dependency['padding'] = info['padding']

        # ---

        # MulConstant
        elif (op_type == "Mul" or op_type == "QLinearMul"): 
            # Get data from the node
            vta_ir, info = \
                Nconv.node_mulconstant(node=cpt_node, param=model_param, node_mapping=dict_name_index, filename=filename, debug=False)

            # Generate the associated binaries
            if (doGenerateBin):
                Ah = info['matrix_shape'][0]
                Aw = info['matrix_shape'][1]

                RRBG.random_raw_binary_generator(m_rows=Ah, n_columns=Aw, filename=filename+"input", dtype='int8', debug=False)

            # Append the VTA IR list
            vta_ir_list.append( (filename, vta_ir.copy()) )

            # Update dependency
            node_dependency['processor'] = "vta"
            if (node_dependency['input_nodes'][0] == "Image"):
                node_dependency['reshape'] = False
            else:
                node_dependency['reshape'] = True
            node_dependency['offset'] = info['offset']
            node_dependency['input_shape'] = info['tensor_shape'][0]
            node_dependency['output_shape'] = info['tensor_shape'][1]
            node_dependency['kernel'] = info['kernel']
            node_dependency['stride'] = info['stride']
            node_dependency['padding'] = info['padding']

        # ---

        # Activation
        elif (op_type == "Relu"): 
            # Get data from the node
            vta_ir, info = \
                Nactivation.node_relu(node=cpt_node, param=model_param, node_mapping=dict_name_index, filename=filename, debug=False)

            # Generate the associated binaries
            if (doGenerateBin):
                Xh = info['matrix_shape'][0]
                Xw = info['matrix_shape'][1]

                RRBG.random_raw_binary_generator(m_rows=Xh, n_columns=Xw, filename=filename+"accumulator", dtype='int32', debug=False)

            # Append the VTA IR list
            vta_ir_list.append( (filename, vta_ir.copy()) )

            # Update dependency
            node_dependency['processor'] = "vta"
            if (node_dependency['input_nodes'][0] == "Image"):
                node_dependency['reshape'] = False
            else:
                node_dependency['reshape'] = "int32"
            node_dependency['offset'] = info['offset']
            node_dependency['input_shape'] = info['tensor_shape'][0]
            node_dependency['output_shape'] = info['tensor_shape'][1]
            node_dependency['kernel'] = info['kernel']
            node_dependency['stride'] = info['stride']
            node_dependency['padding'] = info['padding']

        # ---

        # ADD
        elif (op_type == "Add" or op_type == 'QLinearAdd'): 
            # Get data from the node
            vta_ir, info = \
                Nadd.node_add(node=cpt_node, param=model_param, node_mapping=dict_name_index, filename=filename, debug=False)

            # Generate the associated binaries
            if (doGenerateBin):
                Xh = info['matrix_shape'][0]
                Xw = info['matrix_shape'][1]
                
                RRBG.random_raw_binary_generator(m_rows=Xh, n_columns=Xw, filename=filename+"accumulator", dtype='int32', debug=False)
                RRBG.random_raw_binary_generator(m_rows=Xh, n_columns=Xw, filename=filename+"accbis", dtype='int32', debug=False)

            # Append the VTA IR list
            vta_ir_list.append( (filename, vta_ir.copy()) )

            # Update dependency
            node_dependency['processor'] = "vta"
            if (node_dependency['input_nodes'][0] == "Image"):
                node_dependency['reshape'] = False
            else:
                node_dependency['reshape'] = "int32"
            node_dependency['offset'] = info['offset']
            node_dependency['input_shape'] = info['tensor_shape'][0]
            node_dependency['output_shape'] = info['tensor_shape'][1]
            node_dependency['kernel'] = info['kernel']
            node_dependency['stride'] = info['stride']
            node_dependency['padding'] = info['padding']

        # ---

        # Others
        else:
            pass
            # # Update dependency # TODO!
            # node_dependency['reshape'] = "int32"
            # node_dependency['input_shape'] = Tinp_shape
            # node_dependency['output_shape'] = Tout_shape

        # ---

        # Append the execution order
        execution_order.append( node_dependency.copy() )

    
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
    
    
    # WRITE DEPENDENCY INFORMATION
    # ----------------------------
    dependency_file_path = filepath_definition(output_dir, 'dependency.csv')
    with open(dependency_file_path, 'w', newline='') as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(["nb_steps", len(execution_order)])
        for i, dep in enumerate(execution_order):
            # One line with execution order
            writer.writerow([
                i,                      # 0
                dep['processor'],       # 1
                dep['node_name']        # 2
            ])

            # One line with reshape and dependency information
            dep_list = [
                dep['node_name'],       # 0
                dep['input_shape'][1],  # 1
                dep['input_shape'][2],  # 2
                dep['input_shape'][3],  # 3
                dep['reshape'],         # 4
                dep['offset'],          # 5
                dep['kernel'][0],       # 6
                dep['kernel'][1],       # 7
                dep['stride'][0],       # 8
                dep['stride'][1],       # 9
                dep['padding'][0],      # 10
                dep['padding'][1],      # 11
                dep['padding'][2],      # 12
                dep['padding'][3],      # 13
                "INP",                  # 14
                len(dep['input_nodes']),# 15
            ]
            # Add the dependency information # 16+
            for inp_node in dep['input_nodes']:
                dep_list.append( inp_node )
            # Write the second line
            writer.writerow(dep_list)
        # write output
        writer.writerow([
            "output",                               # 0
            execution_order[-1]['node_name'],       # 1
            execution_order[-1]['output_shape'][1], # 2
            execution_order[-1]['output_shape'][2], # 3
            execution_order[-1]['output_shape'][3]  # 4
        ])


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


        print(f"\nExecution order: ")
        for i, step in enumerate(execution_order):
            print(f"Step {i}: \t {step} \n")

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
    # Must have 4 arguments
    if (len(sys.argv) != 4):
        raise Exception(f"ERROR: There are {len(sys.argv)} arguments when 4 are expected! \n\n")

    # Read the arguments
    onnx_model_path = sys.argv[1]
    doGenerateBin = True if (sys.argv[2] == 'true' or sys.argv[2] == 'True') else False
    debug = True if (sys.argv[3] == 'true' or sys.argv[3] == 'True') else False

    # Execute the backend
    result = vta_backend(onnx_model_path, doGenerateBin=doGenerateBin, debug=debug)

    # END!
