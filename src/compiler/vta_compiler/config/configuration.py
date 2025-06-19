# IMPORT PACKAGES
# ---------------
import numpy as np


# DEFINE DATA TYPE
# ----------------
def data_type(log_value):
    if (log_value == 3):
        return np.int8
    elif (log_value == 4):
        return np.int16
    elif (log_value == 5):
        return np.int32
    else: # Not supported
        raise Exception("ERROR: Not supported data type representation (configuration)!\n\n")

# DEFINE BUFFER SIZE
# ------------------
def buffer_size(log_size, log_dtype, block_size):
    buffer_size_bit = 2**log_size
    dtype_bytes = 2**log_dtype / 8
    buffer_size = int (buffer_size_bit / (dtype_bytes * block_size))
    return buffer_size # Nb of data structure
