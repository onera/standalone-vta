import json
import random
import os

def generate_json_matrix_definition(file_name="add_two_matrices.json"):
    """
    Create a JSON file with random matrix size.
    Args:
    file_name (str): Name of the JSON file to create.
    """
    # Manage the path
    script_dir = os.path.dirname(os.path.abspath(__file__))
    output_dir = os.path.join(script_dir, file_name)

    # Generate random values for dimension, keeping the consistency
    Ah = random.randint(1, 2048) # 8192
    Bw = random.randint(1, 2048) # 8192

    # Create a python dictionnary
    matrix_definition = {
        "MATRICES": [
            {
            "ACCUMULATOR": [Ah, Bw],
            "ADD_ACCUMULATOR": [Ah, Bw]
            }
        ],
        "ALU": [
            ["ADD_ACC", ["ACCUMULATOR", "ADD_ACCUMULATOR"]]
        ],
        "BASE_ADDRESS": "0000"
    }

    # Write dict in a JSON
    with open(output_dir, 'w') as f:
        json.dump(matrix_definition, f, indent=2) # indent=2 for better readibility

    print(f"File '{file_name}' is successfully generated! \
            \n\t A = {Ah}x{Bw} \
            \n\t Total added elements = {(Ah * Bw)*2} \n")

# Appel de la fonction pour créer le fichier
generate_json_matrix_definition()