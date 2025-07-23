import json
import random
import os

def generate_json_matrix_definition(file_name="maxpool.json"):
    """
    Create a JSON file with random matrix size.
    Args:
    file_name (str): Name of the JSON file to create.
    """
    # Manage the path
    script_dir = os.path.dirname(os.path.abspath(__file__))
    output_dir = os.path.join(script_dir, file_name)

    # Generate random values for dimension
    Xh = random.randint(8, 2048)
    Xw = random.randint(1, 2048)

    # Define the number of ALU
    nb_alu = random.randint(1, Xh//4)
    kernel_size = Xh // nb_alu

    # Create the ALU operations
    operations_alu = []
    for i in range(0, nb_alu):
        dst_idx = i*kernel_size
        src_idx = dst_idx + 1
        iteration = kernel_size-1
        operations_alu.append(
            ["MAX", [[dst_idx,0], [src_idx,1], iteration]]
        )

    # Create a python dictionnary
    matrix_definition = {
        "MATRICES": [
            {
            "ACCUMULATOR": [Xh, Xw]
            }
        ],
        "ALU": operations_alu,
        "BASE_ADDRESS": "0000"
    }

    # Write dict in a JSON
    with open(output_dir, 'w') as f:
        json.dump(matrix_definition, f, indent=2) # indent=2 for better readibility

    print(f"File '{file_name}' is successfully generated!")

# Appel de la fonction pour créer le fichier
generate_json_matrix_definition()