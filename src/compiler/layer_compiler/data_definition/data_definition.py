# IMPORT PACKAGES
# ---------------
import os
import sys
import numpy as np


###############################################

# MAIN FUNCTION
# -------------
def data_definition(matrices_dict, block_size=16,
                    doLoadInp=False, input_name='', inp_dtype=np.int8, 
                    doLoadWgt=False, weight_name='', wgt_dtype=np.int8,  
                    doMulConstant=False, mulConstant=0,
                    doLoadAcc=False, acc_name='', acc_dtype=np.int32,
                    doLoadAccBis=False, acc_bis_name='', # dtype = acc_dtype
                    doStoreFullMatrix=False, output_name='', flat_store_list=[], # dtype = inp_dtype
                    debug=True):
    """
    Pad and split the matrix to create block matrix composed of square block_size*block_size blocks.

    Inputs:
        - matrices_dict (dict): From BTA IR JSON file
        - block_size (int): hardware constraint
        - doLoadInp, doLoadWgt, doMulConstant, doLoadAcc, doLoadAccBis, doStoreFullMatrix (bool)
        - input_name, weight_name, acc_name, acc_bis_name, output_name (str)
        - inp_dtype, wgt_dtype, acc_dtype (np.dtype)
        - mulConstant (int): the scalar value for GEMM
        - flat_store_list (list of int): list of matrix vectors to store
        - debug (bool): to print some information / partial results
    
    Outputs:
        - A_blocks (list of matrices): input block matrix
        - A_blocks_col (int): number of columns in number of blocks
        - B_blocks (list of matrices), B_blocks_col(int): weight
        - X_blocks, Y_blocks (list of matrices): accumulator and accumulator bis
        - C_blocks (list of matrices), C_blocks_col (int): output with the DRAM size
        - A_matrix, X_matrix, Y_matrix (matrix): raw matrices
        - metadata (list of dict): dimension of matrices [{'type': str, 'rows': int, 'columns': int}]
    ]
    """
    # INIT
    # ----
    A_row = 0
    A_col = 0
    A_file = None
    B_row = 0
    B_col = 0
    B_file = None
    X_row = 0
    X_col = 0
    X_file = None
    Y_row = 0
    Y_col = 0
    Y_file = None
    C_row = 0
    C_col = 0


    # GET MATRICES
    # ------------
    # A - Check if the matrix is specified
    if (doLoadInp):
        A_row = matrices_dict[input_name][0]
        A_col = matrices_dict[input_name][1]
        # If binary file is given
        if ( matrices_dict[input_name][2].endswith(".bin") ):
            A_file = matrices_dict[input_name][2]
    # Create the matrix
    A_matrix = matrix_creation(m_row=A_row, n_col=A_col, file=A_file, dtype=inp_dtype)

    # B - Check if the matrix is specified
    if (doLoadWgt):
        B_row = matrices_dict[weight_name][0]
        B_col = matrices_dict[weight_name][1]
        # If binary file is given
        if ( matrices_dict[weight_name][2].endswith(".bin") ):
            B_file = matrices_dict[weight_name][2]
    # Create the matrix
    if (doMulConstant):
        B_matrix = matrix_diagonal(diag_value=mulConstant, block_size=block_size, dtype=wgt_dtype)
    else:
        B_matrix = matrix_creation(m_row=B_row, n_col=B_col, file=B_file, dtype=wgt_dtype)

    # X - Check if the matrix is specified
    if (doLoadAcc):
        X_row = matrices_dict[acc_name][0]
        X_col = matrices_dict[acc_name][1]
        # If binary file is given
        if ( matrices_dict[acc_name][2].endswith(".bin") ):
            X_file = matrices_dict[acc_name][2]
    else: # Give default size
        if (doLoadInp==True and doLoadWgt==False): # A * scalar
            X_row, X_col = (A_row, A_col)
        elif (doLoadInp==True and doLoadWgt==True): # A * B
            X_row, X_col = (A_row, B_col)
    # Create the matrix
    X_matrix = matrix_creation(m_row=X_row, n_col=X_col, file=X_file, dtype=acc_dtype)

    # Y - Check if the matrix is specified
    if (doLoadAccBis):
        Y_row = matrices_dict[acc_bis_name][0] 
        Y_col = matrices_dict[acc_bis_name][1]
        # If binary file is given
        if ( matrices_dict[acc_bis_name][2].endswith(".bin") ):
            Y_file = matrices_dict[acc_bis_name][2]
    # Create the matrix
    Y_matrix = matrix_creation(m_row=Y_row, n_col=Y_col, file=Y_file, dtype=acc_dtype)

    # C - Check if the matrix is fully stored
    C_col = matrices_dict[output_name][1]
    if (doStoreFullMatrix):
        C_row = matrices_dict[output_name][0] 
    else: # Not full matrix
        C_row = len( flat_store_list )
    # Create the matrix
    C_matrix = matrix_creation(m_row=C_row, n_col=C_col, file=None, dtype=inp_dtype)


    # -------
    # PADDING
    # -------
    isSquare = True # TODO: For now, always square

    # Pad
    A_padded = matrix_padding(matrix=A_matrix, block_size=block_size, isWeight=False, isSquare=isSquare)
    B_padded = matrix_padding(matrix=B_matrix, block_size=block_size, isWeight=True, isSquare=isSquare)
    X_padded = matrix_padding(matrix=X_matrix, block_size=block_size, isWeight=False, isSquare=isSquare)
    Y_padded = matrix_padding(matrix=Y_matrix, block_size=block_size, isWeight=False, isSquare=isSquare)
    # Square only if (doStoreFullMatrix == True)
    C_padded = matrix_padding(matrix=C_matrix, block_size=block_size, isWeight=False, isSquare=doStoreFullMatrix)


    # --------
    #SPLITTING
    # --------
    A_blocks, A_blocks_col, A_blocks_row = matrix_splitting(matrix=A_padded, block_size=block_size, isWeight=False, isSquare=isSquare)
    B_blocks, B_blocks_col, B_blocks_row = matrix_splitting(matrix=B_padded, block_size=block_size, isWeight=True, isSquare=isSquare)
    X_blocks, X_blocks_col, X_blocks_row = matrix_splitting(matrix=X_padded, block_size=block_size, isWeight=False, isSquare=isSquare)
    Y_blocks, _, _                       = matrix_splitting(matrix=Y_padded, block_size=block_size, isWeight=False, isSquare=isSquare)
    C_blocks, C_blocks_col, C_blocks_row = matrix_splitting(matrix=C_padded, block_size=block_size, isWeight=False, isSquare=doStoreFullMatrix)

    # Check if X_blocks_col == C_blocks_col
    if (X_blocks_col != C_blocks_col):
        raise Exception(f"ERROR: X_blocks_col must be equal to C_blocks_col! \n")


    # META INFORMATION
    # ----------------
    outIsSquare = True if (doStoreFullMatrix == True) else False
    metadata = [
        {"type": "BS", "rows": outIsSquare, "columns": block_size},
        {"type": "A", "rows": A_row, "columns": A_col},
        {"type": "X", "rows": X_row, "columns": X_col},
        {"type": "Y", "rows": Y_row, "columns": Y_col},
        {"type": "C", "rows": C_row, "columns": C_col}
    ]

    # DEBUG
    # -----
    if (debug):
        print(f"DATA DEFINITION:")
        print(f" INP - {input_name}: {A_row}x{A_col} elements ({A_row*A_col})  \t-> {A_blocks_row}x{A_blocks_col} blocks ({len(A_blocks)})")
        print(f"\n WGT - {weight_name}: {B_row}x{B_col} elements ({B_row*B_col})  \t-> {B_blocks_row}x{B_blocks_col} blocks ({len(B_blocks)})")
        print(f"\n ACC - {acc_name}/{acc_bis_name}: {X_row}x{X_col} elements ({X_row*X_col})  \t-> {X_blocks_row}x{X_blocks_col} blocks ({len(X_blocks)})")
        print(f"\n OUT - {output_name}: {C_row}x{C_col} elements ({C_row*C_col})  \t-> {C_blocks_row}x{C_blocks_col} blocks ({len(C_blocks)})")


    # RETURN
    # ------
    return A_blocks, A_blocks_col, B_blocks, B_blocks_col, \
           X_blocks, Y_blocks, C_blocks, C_blocks_col, \
           A_matrix, X_matrix, Y_matrix, metadata


###############################################

# MATRIX CREATION
# ---------------
def matrix_creation(m_row=16, n_col=16, file=None, dtype=np.int8):
    """Create a matrix with dtype values (e.g., int8 or int32)."""

    if (file == None): # No values -> full of zeros
        matrix = np.zeros((m_row, n_col), dtype=dtype)

    else: # Raw binary file
        # Read the data (1D)
        flat_array = np.fromfile(file, dtype=dtype)
        # Reshaphe the data in 2D (h, w)
        matrix = flat_array.reshape((m_row, n_col))

    # Return the matrix
    return matrix


###############################################

# MATRIX DIAGONAL
# ---------------
def matrix_diagonal(diag_value=0, block_size=16, dtype=np.int8):
    """Create a diagonal matrix with dtype values (e.g., int8 or int32)."""
    matrix = diag_value * np.eye(block_size, dtype=dtype) 
    # Return the matrix
    return matrix


###############################################

# MATRIX PADDING
# --------------
def matrix_padding(matrix, block_size=16, isWeight=False, isSquare=True):
    """Pad the matrix such that its shape is a multiple of block_size.
       If it is input, then only the number of column is padded."""
    # Get the matrix size
    m_row, n_col = matrix.shape

    # Define the target dimensions (block_size or upper multiple of block_size)
    if (isWeight or isSquare):  # Pad only the lines for the weight matrices
        target_rows = ((m_row - 1) // block_size + 1) * block_size
    else: # Else, only the column are padded
        target_rows = m_row 

    # Pad the column
    target_cols = ((n_col - 1) // block_size + 1) * block_size

    # Pad the matrix with 0 (pad = target - n)
    padded_matrix = np.pad(matrix, ((0, target_rows-m_row), (0, target_cols-n_col)), mode='constant')

    # Return the padded matrix
    return padded_matrix


###############################################

# MATRIX CREATION
# ---------------
def matrix_splitting(matrix, block_size=16, isWeight=False, isSquare=True):
    """Split the matrix into blocks using slicing to handle unequal row division.
    For weight matrices (isWeight=True), it splits into square blocks of size block_size x block_size.
    For other matrices (isWeight=False), it splits into blocks of size up to block_size x block_size,
    splitting only along rows if the number of rows exceeds block_size."""
    
    # Get the matrix dimensions
    m_row, n_col = matrix.shape

    # Ensure the matrix width is a multiple of block_size
    if n_col % block_size != 0:
        raise ValueError("ERROR: Matrix width must be a multiple of block_size")

    blocks_col = n_col // block_size  # Number of blocks in each column
    blocks = []  # List to store the blocks

    if (isWeight or isSquare):
        # Ensure the matrix height is a multiple of block_size
        if m_row % block_size != 0:
            raise ValueError("Matrix height must be a multiple of block_size")

        blocks_row = m_row // block_size  # Number of blocks in each row
        for i in range(blocks_row):
            for j in range(blocks_col):
                block = matrix[i * block_size:(i + 1) * block_size, j * block_size:(j + 1) * block_size]
                blocks.append(block)
    else:
        # Calculate the number of blocks in each column
        blocks_row = (m_row + block_size - 1) // block_size # Ensure that all rows are processed
        for i in range(blocks_row):
            for j in range(blocks_col):
                row_start = i * block_size
                row_end = min((i + 1) * block_size, m_row)  # Ensure not to exceed the number of rows
                block = matrix[row_start:row_end, j * block_size:(j + 1) * block_size]
                blocks.append(block)

    # Return the list of blocks
    return blocks, blocks_col, blocks_row

