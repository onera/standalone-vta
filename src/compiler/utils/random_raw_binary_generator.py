# IMPORT PACKAGES
# ---------------
import os
import sys
import numpy as np

from find_project_root import *

###############################################

# MAIN FUNCTION
# -------------
def random_raw_binary_generator(m_rows, n_columns, filename="input",
                                debug=False):
    # Generation parameters
    random_bound = 8
    low_bound = -random_bound

    # Define the dtype
    if (filename == "input" or filename == "weight"):
        dtype = np.int8
    else: 
        dtype = np.int32

    # Matrix generation
    matrix = np.random.randint(low_bound, random_bound - 1, size=(m_rows, n_columns), dtype=dtype)

    # Print matrix
    if (debug):
        print(f"\nMatrix generated: \n{matrix} \n")

    # Rename the file
    filename = filename+"_"+str(m_rows)+"x"+str(n_columns) # TODO: modify

    # Write file
    output_dir = compiler_output_setup()
    prompt_file_path = filepath_definition(output_dir, 'prompt_'+filename+'.txt')
    file_path = filepath_definition(output_dir, filename+'.bin')

    with open(prompt_file_path, 'w') as f:
        np.savetxt(f, matrix, fmt='%4d')

    # Write binary
    with open(file_path, 'wb') as f:
        matrix.tofile(f)


###############################################


# EXECUTE MAIN FUNCTION
# ---------------------
if __name__ == "__main__": 
    """
    To execute: 
        > python random_raw_binary_generator.py 
            <m_rows> 
            <n_columns> 
            <filename>
    """
    filename ="input"
    if len(sys.argv) == 1:
        m_rows = 16
        n_columns = 16
    elif len(sys.argv) == 2:
        m_rows = int( sys.argv[1] )
        n_columns = m_rows   
    elif len(sys.argv) == 2:
        m_rows = int( sys.argv[1] )
        n_columns = int( sys.argv[2] )
    else:
        m_rows = int( sys.argv[1] )
        n_columns = int( sys.argv[2] )
        filename = sys.argv[3]

    
    print(f"\nGeneration of {m_rows}x{n_columns} raw matrix ...")
    random_raw_binary_generator(m_rows, n_columns, filename)
