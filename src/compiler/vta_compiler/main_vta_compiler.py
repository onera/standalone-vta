# IMPORT PACKAGES
# ---------------
import os
import sys

import numpy as np
import ctypes
import csv
import json

import toolbox.alu_operations as ALU
import toolbox.matrix_to_block_index as MTB
import toolbox.sort_idx_to_store as SIS

import data_definition.data_definition as DF
import dram_allocation.dram_allocation as DA
import matrix_partitioning.matrix_partitioning as MP
import operations_definition.operations_definition as OP

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils.find_project_root import *
from utils.json_parser import *
import utils.configuration as conf


###############################################


# MAIN FUNCTION
# -------------
def main(vta_config_dict, operations_dict, base_address, dram_offset,
         dram_state_dictionary={},
         debug=True, summary=True):
    
    if (debug):
        print(f"\nVTA COMPILER compiling..." + \
              f"\n\t {operations_dict} \n\t With: {vta_config_dict}" + \
              f"\n\t Starting at base_address={hex(base_address)} and dram_offset={hex(dram_offset)}!\n")

    # GET CONFIGURATION
    # -----------------
    # Data type
    inp_dtype = conf.data_type(vta_config_dict["LOG_INP_WIDTH"])
    wgt_dtype = conf.data_type(vta_config_dict["LOG_WGT_WIDTH"])
    acc_dtype = conf.data_type(vta_config_dict["LOG_ACC_WIDTH"])

    # Block size (hardware constraint)
    block_size = 2**vta_config_dict["LOG_BLOCK"]

    # SRAM memory capacity
    inp_buffer_size = conf.buffer_size(vta_config_dict["LOG_INP_BUFF_SIZE"], vta_config_dict["LOG_INP_WIDTH"], block_size)
    wgt_buffer_size = conf.buffer_size(vta_config_dict["LOG_WGT_BUFF_SIZE"], vta_config_dict["LOG_WGT_WIDTH"], block_size*block_size)
    acc_buffer_size = conf.buffer_size(vta_config_dict["LOG_ACC_BUFF_SIZE"], vta_config_dict["LOG_ACC_WIDTH"], block_size)
    out_buffer_size = acc_buffer_size
    uop_buffer_size = conf.buffer_size(vta_config_dict["LOG_UOP_BUFF_SIZE"], 5, 1)


    # INIT VARIABLES AND FLAGS (METADATA)
    # -----------------------------------
    flag_dict = {
        "doGemm": False, # Perform a GEMM
        "doExpandBias": False, # Expand the bias
        "doMulConstant": False, # Perform a GEMM with a scalar
        "doAlu": False, # Perform ALU operations
        "doAddMatrix": False, # Perform an element-wise addition between two matrices

        "doLoadInp": False, # Load INP
        "doLoadWgt": False, # Load WGT
        "doLoadAcc": False, # Load ACC
        "doLoadAccBis": False, # Load ACC_BIS (two ACC matrices)
        "doStoreFullMatrix": False # Store the entire OUT matrix
    }

    # Define constants
    mulConstant = 0
    strategy_selector = 1

    # Lists of operations
    gemm_op = []
    alu_list = []
    flat_store_list = []

    # Default matrix names
    input_name = ''
    weight_name = ''
    acc_name = ''
    acc_bis_name = ''
    output_name = ''


    # DECODE VTA IR (JSON file)
    # -------------------------
    # Get VTA IR sections (name, matrix, load operation)
    name = operations_dict["NAME"]
    matrices_dict = operations_dict["MATRICES"]
    load_dict = operations_dict["LOAD"]


    # Define the matrix name through the load operations
    if "INP" in load_dict:
        flag_dict["doLoadInp"] = True
        input_name = load_dict["INP"][0]
    if "WGT" in load_dict:
        flag_dict["doLoadWgt"] = True
        weight_name = load_dict["WGT"][0]
    if "ACC" in load_dict:
        flag_dict["doLoadAcc"] = True
        acc_name = load_dict["ACC"][0]
        if ( len(load_dict["ACC"]) > 1):
            if ( type(load_dict["ACC"][1]) == str ):
                flag_dict["doLoadAccBis"] = True
                acc_bis_name = load_dict["ACC"][1]
    

    # Define the output matrix name 
    for key in matrices_dict.keys():
        if ( matrices_dict[key][2] == "output" ):
            output_name = key
            break


    # Check the matrix dimensions
    if (input_name != '' and weight_name != ''):
        if (matrices_dict[input_name][1] != matrices_dict[weight_name][0] or \
            matrices_dict[input_name][0] != matrices_dict[output_name][0] or \
            matrices_dict[weight_name][1] != matrices_dict[output_name][1]):
            raise Exception(f"ERROR: Dimension inconsistency: INP=({matrices_dict[input_name][0]},{matrices_dict[input_name][1]}), WGT=({matrices_dict[weight_name][0]},{matrices_dict[weight_name][1]}) and OUT=({matrices_dict[output_name][0]},{matrices_dict[output_name][1]})! \n")
    if (acc_name != ''):
        if (matrices_dict[acc_name][0] != matrices_dict[output_name][0]):
            # Specific case, Bias can be expanded
            if (matrices_dict[acc_name][0] == 1):
                flag_dict["doExpandBias"] = True
            else:
                raise Exception(f"ERROR: Dimension inconsistency: ACC=({matrices_dict[acc_name][0]},{matrices_dict[acc_name][1]}) and OUT=({matrices_dict[output_name][0]},{matrices_dict[output_name][1]})! \n")
        if (matrices_dict[acc_name][1] != matrices_dict[output_name][1]):
            raise Exception(f"ERROR: Dimension inconsistency: ACC=({matrices_dict[acc_name][0]},{matrices_dict[acc_name][1]}) and OUT=({matrices_dict[output_name][0]},{matrices_dict[output_name][1]})! \n")
    if (acc_bis_name != ''):
        if (matrices_dict[acc_bis_name][0] != matrices_dict[output_name][0] or \
            matrices_dict[acc_bis_name][1] != matrices_dict[output_name][1]):
            raise Exception(f"ERROR: Dimension inconsistency: ACC_BIS=({matrices_dict[acc_bis_name][0]},{matrices_dict[acc_bis_name][1]}) and OUT=({matrices_dict[output_name][0]},{matrices_dict[output_name][1]})! \n")


    # Define the compute operations to perform (either: GEMM, MulConstant or ALU)
    if "GEMM" in operations_dict:
        gemm_op = operations_dict["GEMM"]
        if ( type(gemm_op[2]) == int ):
            flag_dict["doMulConstant"] = True
            mulConstant = gemm_op[2]
        else:
            flag_dict["doGemm"] = True
        # Finally, check if the operation correct
        if ( (gemm_op[0] != output_name or gemm_op[1] != input_name) or \
             (gemm_op[2] != weight_name and flag_dict["doMulConstant"] == False) ):
            raise Exception(f"ERROR: GEMM declaration must be GEMM(OUT, INP, WGT|scalar)! \n")
    if "ALU" in operations_dict:
        # Check if ACC is init
        if ((flag_dict["doLoadAcc"] == False) and (flag_dict["doGemm"] == False and flag_dict["doMulConstant"] == False)):
            raise Exception(f"ERROR: no ACC loaded! \n")
        # Check if ALU is performed on the right matrice
        if not (output_name in operations_dict["ALU"]):
            raise Exception(f"ERROR: ALU must be performed on OUTPUT buffer! \n")
        # Define the list of alu operations
        alu_list = operations_dict["ALU"][output_name]
        if ( alu_list[0][0] == "ADD_ACC" ):
            flag_dict["doAddMatrix"] = True
        else:
            flag_dict["doAlu"] = True
    

    # Define the store operation to perform
    if not (output_name in operations_dict["STORE"]):
        raise Exception(f"ERROR: STORE must store OUTPUT buffer! \n")

    store_list = operations_dict["STORE"][output_name]
    if ( type(store_list[0]) == str ):
        flag_dict["doStoreFullMatrix"] = True
        if (flag_dict["doAlu"] == True and \
            flag_dict["doLoadInp"] == False and flag_dict["doLoadWgt"] == False and flag_dict["doLoadAcc"] == True):
            flat_store_list = list(range(0, matrices_dict[output_name][0])) 
    else: # Compute the matrix row to store
        for store in store_list:
            dst_idx, dst_step = store[0]
            nb_loop = store[1]
            for i in range(0, nb_loop):
                flat_store_list.append( dst_idx + dst_step * i )


    # Define the matrix partitioning strategy (1, 2, 3, 4)
    if ("STRATEGY" in operations_dict):
        strategy_selector = operations_dict["STRATEGY"]
        if ( type(strategy_selector) != int ):
            raise Exception(f"\nERROR: Strategy is {type(strategy_selector)} while int is expected! \n\n")



    # ADD EXTRA INFORMATION TO IR
    # ---------------------------
    # Update ALU 
    if (flag_dict["doAlu"]):
        C_row = matrices_dict[output_name][0]
        C_col = matrices_dict[output_name][1]
        alu_list = ALU.alu_operations(alu_operations=alu_list, shape=(C_row,C_col), block_size=block_size)


    # ---------------------------------------------
    # DATA DEFINITION
    # ---------------
    A_blocks, A_blocks_col, B_blocks, B_blocks_col, \
        X_blocks, Y_blocks, C_blocks, C_blocks_col, \
        A_matrix, X_matrix, Y_matrix, metadata, flag_dict = \
        DF.data_definition(matrices_dict=matrices_dict, flag_dict=flag_dict, block_size=block_size,
                           input_name=input_name, inp_dtype=inp_dtype, 
                           weight_name=weight_name, wgt_dtype=wgt_dtype, 
                           mulConstant=mulConstant,
                           acc_name=acc_name, acc_dtype=acc_dtype,
                           acc_bis_name=acc_bis_name, # dtype = acc_dtype
                           output_name=output_name, flat_store_list=flat_store_list, # dtype = inp_dtype
                           debug=debug)


    # ---------------------------------------------
    # DRAM ALLOCATION
    # ---------------
    # # Force an allocation size for OUT
    # forced_allocation_size = sum(matrix.nbytes for matrix in ALU_blocks)
    # Create the object to allocate
    object_list = [("INP", A_blocks),
                   ("WGT", B_blocks),
                   ("ACC", X_blocks),
                   ("ACC_BIS", Y_blocks),
                   ("OUT", C_blocks),
                   ("UOP", [], 4)]

    # Allocate the object
    base_addresses_list, updated_base_address = \
        DA.dram_allocation(object_list, base_addr=base_address, block_size=block_size, 
                           inp_dtype=inp_dtype, wgt_dtype=wgt_dtype, acc_dtype=acc_dtype,
                           dram_offset=dram_offset, debug=debug)


    # ---------------------------------------------
    # MATRIX PARTITIONING
    # -------------------
    # Compute the data for matrix partitioning
    if (flag_dict["doGemm"] == True or flag_dict["doMulConstant"] == True):
        nb_A = len(A_blocks)
        nb_B = len(B_blocks)
    else:
        nb_A = 0
        nb_B = 0
    nb_X = len(X_blocks)
    nb_C = len(C_blocks)

    # Refine the idx_to_store (block vectors)
    idx_to_store = [] # if empty <=> doStoreFullMatrix == True
    idx_to_store_to_sort = [] 
    for mat_vec in flat_store_list:
        flat, pair = MTB.vectorMatrixToBlock(matrix_vector=mat_vec, block_size=block_size, nb_blocks_col=C_blocks_col)
        idx_to_store_to_sort = idx_to_store_to_sort + pair
    # Order the list
    if (len(idx_to_store_to_sort) > 0):
        idx_to_store = SIS.sort_idx_to_store(idx_to_store=idx_to_store_to_sort, nb_col=C_blocks_col, block_size=block_size)


    # Apply matrix partitioning (check is overfit then applies selected trategy)
    strategy, flag_dict = \
        MP.matrix_partitioning(nb_A=nb_A, A_blocks_col=A_blocks_col, nb_B=nb_B, B_blocks_col=B_blocks_col, 
                               nb_X=nb_X, nb_C=nb_C, C_blocks_col=C_blocks_col,
                               inp_buffer_size=inp_buffer_size, wgt_buffer_size=wgt_buffer_size, 
                               acc_buffer_size=acc_buffer_size, out_buffer_size=out_buffer_size,
                               alu_operations=alu_list, idx_to_store=idx_to_store,
                               flag_dict=flag_dict,
                               strategy_selector=strategy_selector, block_size=block_size,
                               debug=debug)
	

    # ---------------------------------------------
    # OPERATIONS DEFINITION
    # ---------------------
    insn_buffer, uop_buffer = \
        OP.operations_definition(strategy=strategy, dram_addresses=base_addresses_list,
                                 operations_dict=operations_dict, flag_dict=flag_dict,
                                 block_size=block_size, uop_buffer_size=uop_buffer_size,
                                 A_blocks_col=A_blocks_col, B_blocks_col=B_blocks_col, C_blocks_col=C_blocks_col,
                                 debug=debug)


    # ---------------------------------------------
    # UPDATE DRAM ALLOCATION
    # ----------------------
    object_list = [("UOP", uop_buffer),
                   ("INSN", insn_buffer)]
    updated_addr, updated_base_address = \
        DA.dram_allocation(object_list, base_addr=updated_base_address-4, block_size=block_size, 
                           inp_dtype=inp_dtype, wgt_dtype=wgt_dtype, acc_dtype=acc_dtype,
                           dram_offset=dram_offset, debug=debug)
    base_addresses_list[-1] = updated_addr[0]
    base_addresses_list.append(updated_addr[1])


    # ---------------------------------------------
    # BINARISATION
    # ------------
    # Setup the output folder (standalone-vta/compiler_output/)
    output_dir = compiler_output_setup()

    # MATRICES
    # ---
    # No need to write A_matrix nor C_blocks
    
    # Define the path of file to reserve space
    B_blocks_file_path = filepath_definition(output_dir, 'weight'+name+'.bin')

    # Raw matrix files
    X_matrix_file_path = filepath_definition(output_dir, 'accumulator'+name+'.bin')
    Y_matrix_file_path = filepath_definition(output_dir, 'add_accumulator'+name+'.bin')
    
    # Write B_blocks matrix (TO TRANSPOSE!)
    with open(B_blocks_file_path, 'wb') as f:
        for block in B_blocks:
            transposed = block.transpose()
            transposed.tofile(f)

    # Write X_matrix
    with open(X_matrix_file_path, 'wb') as f:
        X_matrix.tofile(f)

    # Write Y_matrix
    with open(Y_matrix_file_path, 'wb') as f:
        Y_matrix.tofile(f)
    

    # INSTRUCTIONS + UOP
    # ---
    insn_file_path = filepath_definition(output_dir, 'instructions'+name+'.bin')
    uop_file_path = filepath_definition(output_dir, 'uop'+name+'.bin')
    with open(insn_file_path, "wb") as f:
        for insn in insn_buffer:
            f.write(insn)
    with open(uop_file_path, "wb") as f:
        for uop in uop_buffer:
            f.write(uop)


    # META INFORMATION
    # ---
    metadata_file_path = filepath_definition(output_dir, 'metadata'+name+'.csv')
    with open(metadata_file_path, 'w', newline='') as csvfile:
        writer = csv.writer(csvfile)
        for data in metadata:
            writer.writerow([data['type'], data['rows'], data['columns'], data['square']])




    # TODO: FOR CHISEL
    # Dram allocation
    base_addresses_file_path = filepath_definition(output_dir, 'memory_addresses'+name+'.csv')
    with open(base_addresses_file_path, 'w', newline='') as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(["Buffer type", "Physical address (hex)", "Logical address (hex)"]) # Header
        for obj_addr in base_addresses_list:
            writer.writerow([obj_addr['type'], obj_addr['physical_base_address'], obj_addr['logical_base_address']])

    # Binaries
    A_blocks_file_path = filepath_definition(output_dir, 'input'+name+'.bin')
    C_blocks_file_path = filepath_definition(output_dir, 'out_init.bin')
    tempo_file_path = filepath_definition(output_dir, 'expected_out_sram.bin')
    with open(A_blocks_file_path, 'wb') as f:
        for block in A_blocks:
            block.tofile(f)
    with open(C_blocks_file_path, 'wb') as f:
        for block in C_blocks:
            block.tofile(f)
    with open(tempo_file_path, 'wb') as f:
        for block in C_blocks:
            block.tofile(f)


    # Dictionary for CHISEL
    if (dram_state_dictionary != False):
        dram_state_dictionary[name] = {}
        def get_hex_value_from_blocks(blocks, type_input):
            values_list = []
            dt = np.dtype(type_input)
            n_bits = dt.itemsize * 8
            mask = (1 << n_bits) - 1
            hex_width = n_bits // 4
            
            fmt = f"{{:0{hex_width}X}}"

            for block in blocks:
                # Flat the block
                flat_data = block.flatten() if isinstance(block, np.ndarray) else block
                
                for value in flat_data:
                    # Mask to handle negative numbers (two's complement)
                    val_int = int(value) & mask
                    values_list.append(fmt.format(val_int))
                    
            return values_list

        def get_hex_value_from_ctype(insn):
            # Convert structure in Bytes
            raw_bytes = ctypes.string_at(ctypes.byref(insn), ctypes.sizeof(insn))

            # Convert Bytes in hexadecimal chain
            hex_string = raw_bytes[::-1].hex().upper()

            return hex_string

        for i, mem in enumerate(base_addresses_list):
            # Get the type
            mem_type = mem['type']

            # Get the values
            if (mem_type == "INP"):
                values_list = get_hex_value_from_blocks(A_blocks, inp_dtype)
            elif (mem_type == "WGT"):
                values_list = get_hex_value_from_blocks(B_blocks, wgt_dtype)
            elif (mem_type == "ACC"):
                values_list = get_hex_value_from_blocks(X_blocks, acc_dtype)
            elif (mem_type == "ACC_BIS"):
                values_list = get_hex_value_from_blocks(Y_blocks, acc_dtype)
            elif (mem_type == "OUT"):
                values_list = get_hex_value_from_blocks(C_blocks, inp_dtype)
            elif (mem_type == "INSN"):
                values_list = []
                for value in insn_buffer:
                    values_list.append( get_hex_value_from_ctype(value) )
            elif (mem_type == "UOP"):
                values_list = []
                for value in uop_buffer:
                    values_list.append( get_hex_value_from_ctype(value) )

            else: # UOP 
                values_list = []

            # Update the dictionary
            dram_state_dictionary[name][mem_type] = {
                "PhysicalAddr": mem['physical_base_address'].removeprefix("0x"),
                "values": values_list
            }

 
    # ---------------------------------------------
    # DEBUG
    nb_steps = len(strategy)
    nb_uop = len(uop_buffer)
    nb_insn = len(insn_buffer)
    if (debug == True or summary == True):
        # VTA IR DECODING
        print(f"\nVTA COMPILER SUMMARY: {name}")
        print(f"Matrices name: \n\t input_name={input_name}, weight_name={weight_name}, " + \
              f"acc_name={acc_name}, acc_bis_name={acc_bis_name}, output_name={output_name}\n")
        
        print(f"Subsection of JSON: \n\t name={name} \n\t load_dict={load_dict} \n\t matrices_dict={matrices_dict}" + \
              f"\n\t gemm_op={gemm_op} \n\t alu_list={alu_list} \n\t store_list={store_list} \n\n")

        print(f"The flag_dict: \n\t {flag_dict} \n\n")

        print(f"Do the matrices overfit? {flag_dict['isOverfitting']} (Strategy {strategy_selector}) \n")
        print(f"The compilation of '{name}' generates: \n\t {nb_steps} steps \n\t {nb_uop} UOPs \n\t {nb_insn} instructions")
        
        # BINARY FILES GENERATION
        print(f"\n\nBinary files successfully written at: {output_dir}\n")

        print(f"-"*50)

    # ---------------------------------------------
    
    # RETURN new base_address
    return updated_base_address, name, nb_steps, nb_uop, nb_insn, dram_state_dictionary


###############################################


# EXECUTE MAIN FUNCTION
# ---------------------
if __name__ == "__main__": 
    """
    To execute: 
        > python main_vta_compiler.py 
            <debug>
            <summary>
            <dram_json>
            <config_file> 
            [json_file] ...
    """
    base_address = 0x0
    dram_offset = 0x0

    layer_addr_name = []
    
    # Need at least: script_name, debug, summary, config_file, vta_ir
    if len(sys.argv) < 6:
        raise Exception(f"ERROR: There are {len(sys.argv)} arguments when 6 are expected (at least)! \n\n")

    # Debug settings
    debug = True if (sys.argv[1] == 'True' or sys.argv[1] == 'true') else False
    summary = True if (sys.argv[2] == 'True' or sys.argv[2] == 'true') else False
    # CHISEL
    dram_json = True if (sys.argv[3] == 'True' or sys.argv[3] == 'true') else False
    # Config file
    vta_config_file = sys.argv[4]
    vta_config_dict = parse_json_to_dict(vta_config_file)

    # DEBUG
    nb_steps = 0
    nb_uop = 0
    nb_insn = 0
    if (dram_json == True):
        dram_state_dictionary = {} # {} or False
    else:
        dram_state_dictionary = False

    for i, vta_ir in enumerate(sys.argv[5:]):
        if (debug or summary):
            print(f"-"*50)
            print(f"COMPILATION of VTA IR: {i}")
        
        # Parse the JSON files
        operations_dict = parse_json_to_dict(vta_ir)

        # Execute the main function
        base_address, name, steps, uop, insn, dram_state_dictionary = \
            main(vta_config_dict, operations_dict, base_address, dram_offset,
                 dram_state_dictionary=dram_state_dictionary,
                 debug=debug, summary=summary)
        
        # Append layer_addr_name
        layer_addr_name.append( (base_address, name) )

        # DEBUG
        nb_steps += steps
        nb_uop += uop
        nb_insn += insn
    
    # DEBUG
    if (debug or summary):
        print(f"\nTOTAL: \n\t nb_steps={nb_steps} \n\t nb_uop={nb_uop} \n\t nb_insn={nb_insn} \n\n")
    
    # Generate a CSV
    output_dir = compiler_output_setup()
    file_path = filepath_definition(output_dir, 'layers_name.csv')
    with open(file_path, 'w', newline='') as csvfile:
        writer = csv.writer(csvfile)
        # Write the number of JSON and the debug flag
        writer.writerow(["Line identifier", "Nb of VTA IR", "Provide execution log"]) # Header
        writer.writerow(["nb_vta_ir", len(layer_addr_name), summary])
        # Write the information
        writer.writerow(["Line identifier", "VTA IR name", "Last physical DRAM address allocated by the layer"]) # Header
        for i, (add, n) in enumerate(layer_addr_name):
            writer.writerow([i, n, hex(add)])
    
    # Generate a JSON
    if (dram_state_dictionary != False):
        file_dram_state_path = filepath_definition(output_dir, 'dram_state.json')
        with open(file_dram_state_path, 'w') as f:
            json.dump(dram_state_dictionary, f, indent=2) # indent=2 for better readibility

    # END!
