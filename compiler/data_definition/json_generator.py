# IMPORT PACKAGES
# ---------------
import numpy as np
import json


# FUNCTIONS
# ---------
def int8_to_hex(value):
    """Convert an int8 in hexadecimal."""
    return f"{int(value) & 0xFF:02X}"

# CHISEL Compute simulation: src/test/my_experiments/ComputeInvestigation.scala
def generate_json(A_blocks, B_blocks, X_blocks, C_blocks, json_file_path='output.json', block_size=16):
    """Generate the JSON for CHISEL Compute module simulation with the matrix values. 
       Instructions and UOPs must be manually corrected."""
    # Create a JSON dictionnary
    json_data = {
        "inst": {},
        "dram": [],
        "inp": [],
        "wgt": [],
        "out": [],
        "out_expect": []
    }

    # Add random instructions
    for i in range(10):
        json_data["inst"][f"I{i}"] = f"{i:032b}"

    # Add DRAM data
    # ACC init value
    for i, block in enumerate(X_blocks):
        for row in range(block.shape[0]):
            json_data["dram"].append({
                "idx": f"{(i*block_size + row)*64:08X}",  # Incrémentation par 64 (0x40)
                "vec": [f"{int(x) & 0xFFFFFFFF:08X}" for x in block[row]]
            })
    # UOP (start at 0x4000 and are incremented by 4)
    json_data["dram"].append({
        "idx": "00004000",
        "vec": ["00000000", "00000001", "00000002"]
    })
    json_data["dram"].append({
        "idx": "00004004",
        "vec": ["00000003", "00000004", "00000005"]
    })

    # Add INP data (A_matrix)
    for i, block in enumerate(A_blocks):
        for row in range(block.shape[0]):
            json_data["inp"].append({
                "idx": f"{i*block_size + row:08X}",
                "vec": [int8_to_hex(x) for x in block[row]]
            })

    # Add WGT data (B_matrix.tranpose())
    for i, block in enumerate(B_blocks):
        json_data["wgt"].append({
            "idx": f"{i:08X}",
            "vec": [int8_to_hex(x) for x in block.T.flatten()]
        })

    # Add OUT_EXPECT data (C)
    # Count the number of memory vectors are expected
    nb_out_vector = 0
    for i, block in enumerate(C_blocks):
        for row in range(block.shape[0]):
            json_data["out_expect"].append({
                "idx": f"{i*block_size + row:08X}",
                "vec": [int8_to_hex(x) for x in block[row]]
            })
            nb_out_vector = nb_out_vector + 1
    
    # Add OUT data initialised with "FF"
    for i in range(nb_out_vector):
        json_data["out"].append({
            "idx": f"{i:08X}",
            "vec": ["FF"] * 16
        })

    # Write the JSON file
    with open(json_file_path, 'w') as f:
        json.dump(json_data, f, indent=2)

    # Confirm the binary files generation
    print("JSON file successfully generated.")

    # Return the JSON dictionnary
    return json_data
