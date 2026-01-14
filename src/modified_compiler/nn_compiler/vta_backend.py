# IMPORT PACKAGES
# ---------------
import os
import sys
import pickle # DEBUG

import numpy as np

import json
import csv

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils.find_project_root import *
from utils.json_parser import *
import utils.configuration as conf
import utils.random_raw_binary_generator as RRBG

import nn_compiler.parser.parse_onnx_to_dict as PO
import nn_compiler.parser.get_input_nodes as PG
import nn_compiler.nodes.node_conv as Nconv
import nn_compiler.nodes.node_pool as Npool
import nn_compiler.nodes.node_add as Nadd
import nn_compiler.nodes.node_activation as Nactivation
import nn_compiler.nodes.node_cpu as Ncpu


###############################################


# MAIN FUNCTION
# -------------
def vta_backend(vta_config_dict, onnx_model_path, 
                doGenerateBin=False,
                debug=True):

    # GET CONFIGURATION
    # -----------------
    # Data type
    inp_dtype = conf.data_type(vta_config_dict["LOG_INP_WIDTH"])
    wgt_dtype = conf.data_type(vta_config_dict["LOG_WGT_WIDTH"])
    acc_dtype = conf.data_type(vta_config_dict["LOG_ACC_WIDTH"])

    # PARSING the ONNX model
    # ----------------------
    model_dict, dict_name_index = PO.parse_onnx_to_dict(model_path=onnx_model_path, debug=debug)
    model_param = PO.get_onnx_parameters(model_path=onnx_model_path, debug=debug)

    # DEBUG
    if (False): 
        output_dir = compiler_output_setup()
        file_debug_path = filepath_definition(output_dir, "debug_graph.bin")
        with open(file_debug_path, 'wb') as f:
            pickle.dump(model_dict, f)


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
        'QLinearConv', # Conv
        'QLinearMul', # MulConstant
        # # ALU
        # 'QLinearAdd', # Both ADD_ACC and ADD BIAS
        'MaxPool',
        'Relu'
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
        op_type = cpt_node['op_type']

        # Get the index of the VTA executable nodes
        if (op_type in vta_compatible_nodes):
            vta_node_idx_list.append(index)
        else: # Not compatible
            cpu_node_list.append( (index, op_type) )
            # continue # No need to finish this loop

        # Define the name
        filename = op_type + str(index)

        # Reset node_info
        input_dependency = PG.get_input_nodes(compute_nodes=compute_nodes, input_nodes=cpt_node['inputs'], dict_name_index=dict_name_index) 

        node_info = {
            "node_name": filename,
            "processor": "cpu",
            "reshape": False,
            "offsetA": 0,
            "scaleA": 1.,
            "offsetB": 0,
            "scaleB": 1.,
            "offsetU": 0,
            "scaleU": 1.,
            "offsetV": 0,
            "scaleV": 1.,
            "input_shape": [0,0,0,0],
            "kernel": [0,0],
            "stride": [0,0],
            "padding": [0,0,0,0],
            "output_shape": [0,0,0,0],
            "offsetC": 0,
            "scaleC": 1.,
            "rescaling": 1.,
            "input_nodes": input_dependency.copy(),
            "matrix_shape": (0, 0)
        }

        # Define operation for each task
        # ---
        # Convolution or Fully-Connected
        if (op_type == "QLinearConv"): 
            # Get data from the node
            vta_ir, node_info = \
                Nconv.node_conv(node=cpt_node, param=model_param, node_mapping=dict_name_index, node_info=node_info, filename=filename, inp_dtype=inp_dtype, wgt_dtype=wgt_dtype, acc_dtype=acc_dtype, debug=False)

        # ---

        # MulConstant
        elif (op_type == "QLinearMul"): 
            # Get data from the node
            vta_ir, node_info = \
                Nconv.node_mulconstant(node=cpt_node, param=model_param, node_mapping=dict_name_index, node_info=node_info, filename=filename, inp_dtype=inp_dtype, wgt_dtype=wgt_dtype, acc_dtype=acc_dtype, debug=False)

        # ---

        # Pooling
        elif (op_type == "MaxPool"): 
            # Get data from the node
            vta_ir, node_info = \
                Npool.node_pool(node=cpt_node, param=model_param, node_mapping=dict_name_index, node_info=node_info, filename=filename, inp_dtype=inp_dtype, wgt_dtype=wgt_dtype, acc_dtype=acc_dtype, debug=False)

            # Generate the associated binaries
            if (doGenerateBin):
                Xh = node_info['matrix_shape'][0]
                Xw = node_info['matrix_shape'][1]

                str_type = 'int8' if (acc_dtype == np.int8) else 'int32'

                RRBG.random_raw_binary_generator(m_rows=Xh, n_columns=Xw, filename=filename+"accumulator", dtype=str_type, debug=False)

        # ---

        # Activation
        elif (op_type == "Relu"): 
            # Get data from the node
            vta_ir, node_info = \
                Nactivation.node_relu(node=cpt_node, param=model_param, node_mapping=dict_name_index, node_info=node_info, filename=filename, inp_dtype=inp_dtype, wgt_dtype=wgt_dtype, acc_dtype=acc_dtype, debug=False)

            # Generate the associated binaries
            if (doGenerateBin):
                Xh = node_info['matrix_shape'][0]
                Xw = node_info['matrix_shape'][1]

                str_type = 'int8' if (acc_dtype == np.int8) else 'int32'

                RRBG.random_raw_binary_generator(m_rows=Xh, n_columns=Xw, filename=filename+"accumulator", dtype=str_type, debug=False)
        

        # ---
        # ---

        # CPU OPERATIONS

        # ADD (Not executed on VTA)
        elif (op_type == 'QLinearAdd'): 
            # Get data from the node
            _, node_info = \
                Nadd.node_add(node=cpt_node, param=model_param, node_mapping=dict_name_index, node_info=node_info, filename=filename, inp_dtype=inp_dtype, wgt_dtype=wgt_dtype, acc_dtype=acc_dtype, debug=False)

            # Generate the associated binaries
            if (doGenerateBin):
                Xh = node_info['matrix_shape'][0]
                Xw = node_info['matrix_shape'][1]

                str_type = 'int8' if (acc_dtype == np.int8) else 'int32'
                
                RRBG.random_raw_binary_generator(m_rows=Xh, n_columns=Xw, filename=filename+"accumulator", dtype=str_type, debug=False)
                if (node_info['initAccBis'] == False):
                    RRBG.random_raw_binary_generator(m_rows=Xh, n_columns=Xw, filename=filename+"accbis", dtype=str_type, debug=False)

        # Quantise
        elif (op_type == 'QuantizeLinear' or op_type == "DequantizeLinear"): 
            # Get data from the node
            node_info = \
                Ncpu.quantizelinear(node=cpt_node, param=model_param, node_mapping=dict_name_index, node_info=node_info, filename=filename, inp_dtype=inp_dtype, wgt_dtype=wgt_dtype, acc_dtype=acc_dtype, debug=False)

        # Concat
        elif (op_type == 'QLinearConcat'): 
            # Get data from the node
            node_info = \
                Ncpu.qlinearconcat(node=cpt_node, param=model_param, node_mapping=dict_name_index, node_info=node_info, filename=filename, inp_dtype=inp_dtype, wgt_dtype=wgt_dtype, acc_dtype=acc_dtype, debug=False)

        # Concat
        elif (op_type == 'ConvTranspose'): 
            # Get data from the node
            node_info = \
                Ncpu.convtranspose(node=cpt_node, param=model_param, node_mapping=dict_name_index, node_info=node_info, filename=filename, inp_dtype=inp_dtype, wgt_dtype=wgt_dtype, acc_dtype=acc_dtype, debug=False)


        # Others
        else:
            pass
            # # Update dependency # TODO!


        # ---
        # ---

        # Append the VTA IR list
        if (len(vta_ir) != 0):
            vta_ir_list.append( (filename, vta_ir.copy()) )

        # Append the execution order
        execution_order.append( node_info.copy() )

    
    # WRITE VTA IR
    # ------------
    # TODO: tempo
    if (len(vta_ir_list) == 0):
        vta_ir = {
            "NAME": "tempo",
            "MATRICES": {
                "A": [1, 1, "debug"],
                "C": [1, 1, "output"]
            },
            "LOAD": {
                "INP": ["A"]
            },
            "GEMM": ["C", "A", int( 1 )],
            "STORE": {
                "C": ["C"]
            }
        }
        vta_ir_list.append( ("tempo", vta_ir.copy()) )

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
                dep['node_name'],           # 0
                dep['processor'],           # 1
                dep['reshape'],             # 2
                dep['offsetA'],             # 3
                f"{dep['scaleA']:.17g}",    # 4
                dep['offsetB'],             # 5
                f"{dep['scaleB']:.17g}",    # 6
                dep['offsetU'],             # 7
                f"{dep['scaleU']:.17g}",    # 8
                dep['offsetV'],             # 9
                f"{dep['scaleV']:.17g}",    # 10
                dep['input_shape'][1],      # 11
                dep['input_shape'][2],      # 12
                dep['input_shape'][3],      # 13
                dep['kernel'][0],           # 14
                dep['kernel'][1],           # 15
                dep['stride'][0],           # 16
                dep['stride'][1],           # 17
                dep['padding'][0],          # 18
                dep['padding'][1],          # 19
                dep['padding'][2],          # 20
                dep['padding'][3],          # 21
                dep['output_shape'][1],     # 22
                dep['output_shape'][2],     # 23
                dep['output_shape'][3],     # 24
                dep['offsetC'],             # 25
                f"{dep['scaleC']:.17g}",    # 26
                f"{dep['rescaling']:.17g}", # 27 # To keep the precision (.17g to print float 64)
                "INP",                      # 28
                len(dep['input_nodes']),    # 29
            ]
            # Add the dependency information # 30+
            for inp_node in dep['input_nodes']:
                dep_list.append( inp_node )
            # Write the second line
            writer.writerow(dep_list)
        # write image
        image_shape = execution_order[0]['input_shape']
        image_info = ["image"]
        image_info.append( image_shape[2]*image_shape[3] ) # Row
        image_info.append( image_shape[1] ) # Column
        writer.writerow(image_info)
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

        if (nb_total != 0 and nb_vta != 0):
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
            <debug>
            <doGenerateBin>
            <config_file> 
            <onnx_model_path> 
    """
    # Must have 4 arguments
    if (len(sys.argv) != 5):
        raise Exception(f"ERROR: There are {len(sys.argv)} arguments when 4 are expected! \n\n")

    # Read the arguments
    # Debug settings
    debug = True if (sys.argv[1] == 'true' or sys.argv[1] == 'True') else False
    doGenerateBin = True if (sys.argv[2] == 'true' or sys.argv[2] == 'True') else False
    # Config file
    vta_config_file = sys.argv[3]
    vta_config_dict = parse_json_to_dict(vta_config_file)
    # ONNX model
    onnx_model_path = sys.argv[4]

    # Execute the backend
    result = vta_backend(vta_config_dict, onnx_model_path, doGenerateBin=doGenerateBin, debug=debug)

    # END!
