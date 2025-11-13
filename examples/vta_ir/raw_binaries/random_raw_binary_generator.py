# IMPORT PACKAGES
# ---------------
import os
import sys
import numpy as np

###############################################

# MAIN FUNCTION
# -------------
def main(m_rows, n_columns):
    # Generation parameters
    random_bound = 8
    low_bound = -random_bound
    dtype = np.int8 # TODO: modify
    filename = "input"+"_"+str(m_rows)+"x"+str(n_columns) # TODO: modify

    # Matrix generation
    matrix = np.random.randint(low_bound, random_bound - 1, size=(m_rows, n_columns), dtype=dtype)

    # Print matrix
    print(f"\nMatrix generated: \n{matrix} \n")
    with open("prompt_"+filename+".txt", 'w') as f:
        np.savetxt(f, matrix, fmt='%4d')

    # Write binary
    with open(filename+".bin", 'wb') as f:
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
    """
    if len(sys.argv) == 1:
        m_rows = 16
        n_columns = 16
    elif len(sys.argv) == 2:
        m_rows = int( sys.argv[1] )
        n_columns = m_rows     
    else:
        m_rows = int( sys.argv[1] )
        n_columns = int( sys.argv[2] )
    
    print(f"\nGeneration of {m_rows}x{n_columns} raw matrix ...")
    main(m_rows, n_columns)
