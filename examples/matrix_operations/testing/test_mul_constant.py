import json
import random
import os

def generate_json_matrix_definition(file_name="mul_constant.json"):
    """
    Create a JSON file with random matrix size.
    Args:
    file_name (str): Name of the JSON file to create.
    """
    # Manage the path
    script_dir = os.path.dirname(os.path.abspath(__file__))
    output_dir = os.path.join(script_dir, file_name)

    # Generate random values for dimension, keeping the consistency for C = X + A*B
    Ah = random.randint(1, 2048)
    Bw = random.randint(1, 2048)
    scalar = random.randint(-128, 127)

    # Create a python dictionnary
    matrix_definition = {
        "MATRICES": [
            {
            "INPUT": [Ah, Bw],
            "ACCUMULATOR": [Ah, Bw]
            }
        ],
        "GEMM": ["INPUT", scalar, "ACCUMULATOR"],
        "ALU": [
            ["RELU"]
        ],
        "BASE_ADDRESS": "0000"
    }

    # Write dict in a JSON
    with open(output_dir, 'w') as f:
        json.dump(matrix_definition, f, indent=2) # indent=2 for better readibility

    print(f"File '{file_name}' is successfully generated!")

# Appel de la fonction pour créer le fichier
generate_json_matrix_definition()