# USERS VARIABLES
# ---------------

"""MATRIX GENERATION"""
# Matrices initialised with random value? (True / False)
isInitRandom = True
# If yes, random_bound limit the value range (int8 = [-128; 127] -> random_bound = 128)
random_bound = 4

# A matrix size
A_row = 784
A_col = 25

# B matrix size
B_row = A_col # Required by matrix multiplication
B_col = 6


"""COMPUTATION SPECIFICATION"""
# The size of the square matrix multiplication (multiple two block_size square matrix together)
block_size = 16

# Use square matrix or not
isSquare = True

# Compute the non-padded matrix? (True / False)
doMultiplyNonPadded = False

# C matrix option
# Reduction from int16 to int8: useClip (True / False)
# => True: if x > 0: clip => max(127, x)
# => False: Truncate the MSB
useClip = False

# Apply ReLU on the result
useReLU = False


"""PROMPTING AND DUMPING FILES FEATURES"""
# Print the data (True / False)
doPrint = True

# Write matrices in binary files in OUTPUT dir (True / False)
doWriteBinaryFile = False

# Write a JSON file for CHISEL Compute in OUTPUT dir (True / False)
doWriteJSON = True