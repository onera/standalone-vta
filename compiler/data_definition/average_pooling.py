# IMPORT PACKAGES
# ---------------
import numpy as np


# REFERENCE average pooling
# -------------
def reference_average_pooling(matrix, kernel_size=2, stride=2, debug=False):
    """
    Transform the matrix into a tensor, apply average pooling on the tensor (channel-wise),
    then reshape it back into a matrix.

    Arguments:
    matrix -- the input matrix (ACC in your case), shape (H, C)
    kernel_size -- the size of the pooling kernel (default is 2x2)
    stride -- the stride of the pooling operation (default is 2)

    Returns:
    pooled_matrix -- the pooled matrix after transforming the tensor back to the matrix
    """
    # Get the height (H) and width (W) of the input matrix
    H, W = matrix.shape

    # Compute the size of the square channel tensor (sqrt(H))
    channel_size = int(np.sqrt(H))  # Each column will be reshaped into channel_size x channel_size
    
    # Calculate the dimensions of the pooled matrix after the pooling operation
    pooled_height = (channel_size - kernel_size) // stride + 1
    pooled_matrix = np.zeros((pooled_height**2, W), dtype=np.int32)

    # Iterate over each column to apply pooling on each channel (reshape the column to a square tensor)
    for j in range(W):
        # Reshape the column into a square tensor (channel_size x channel_size)
        channel_tensor = matrix[:, j].reshape(channel_size, channel_size)
        if (debug):
            print(f"\nCHANNEL:\n{channel_tensor}\n") # DEBUG

        # Initialise the result tensor
        pooled_channel = np.zeros((pooled_height, pooled_height), dtype=np.int32)
        
        # Apply pooling operation
        for i in range(0, channel_size - kernel_size + 1, stride):
            for k in range(0, channel_size - kernel_size + 1, stride):
                # Get the region for the kernel
                region = channel_tensor[i:i+kernel_size, k:k+kernel_size]
                
                # Compute the average of the region
                pooled_channel[i // stride, k // stride] = np.floor(np.mean(region))
        if (debug):
            print(f"\nPOOLED CHANNEL:\n{pooled_channel}\n") # DEBUG
        
        # Transform the channel back into a matrice
        pooled_matrix[:, j] = pooled_channel.flatten()

    return pooled_matrix, channel_size, pooled_height


def avg_pool_sram(matrix, kernel_size=2, stride=2, debug=False):
    # Get the height (H) and width (W) of the input matrix
    H, W = matrix.shape

    pooled_matrix = np.zeros((H, W), dtype=np.int32)

    # Compute the size of the square channel tensor (sqrt(H))
    channel_size = int(np.sqrt(H))  # Each column will be reshaped into channel_size x channel_size
    
    # Calculate the dimensions of the pooled matrix after the pooling operation
    pooled_height = (channel_size - kernel_size) // stride + 1

    # Add 2 by 2
    for idx in range(0, H, 2):
        pooled_matrix[idx] = matrix[idx, :] + matrix[idx+1, :]

    # Add line + shift right
    for i in range(0, channel_size - kernel_size + 1, stride): # Row
        for k in range(0, channel_size - kernel_size + 1, stride): # Col
            print((i+1)*channel_size + k)
            print("\n")
            print(i*channel_size + k)
            print("\n\n")
            pooled_matrix[i*channel_size + k] = np.floor( (pooled_matrix[i*channel_size + k, :] + pooled_matrix[(i+1)*channel_size + k, :])/(kernel_size**2) )

    return pooled_matrix, channel_size, pooled_height

# Index computation
# -------------
def average_pooling_indexes(in_tensor_size=4, out_tensor_size=2, kernel_size=2, stride=2):
    # Initialise the addresses to 0
    indexes = []

    # Loop to get the final index
    i = 0
    for outer_loop in range(0, out_tensor_size):
        for inner_loop in range(0, out_tensor_size):
            # Compute the final indexes
            sram = 0x0000 + stride*inner_loop + (in_tensor_size*stride)*outer_loop
            dram = 0x00000000 + inner_loop + out_tensor_size*outer_loop

            # Compute the internal indexes
            computation = []
            for line in range(0, kernel_size):
                for col in range(0, kernel_size):
                    computation.append(
                        hex(sram + col + line*in_tensor_size)
                    )

            # Write the data
            indexes.append({
                'I': i,
                'SRAM HEX': hex(sram),
                'SRAM DEC': sram,
                'DRAM HEX': hex(dram),
                'DRAM DEC': dram,
                'Computation': computation
            })
            i = i + 1
    return indexes


# Test average pooling function
# -------------
if __name__ == '__main__':
    kernel = 2
    stride = 2

    # INIT MATRIX
    test_matrix = np.random.randint(-128, 127, size=(16, 2), dtype=np.int32)
    print(f"The matrix: \n{test_matrix} \n")

    # REFERENCE
    pooled_matrix, in_tensor, out_tensor = reference_average_pooling(test_matrix, kernel, stride, debug=True)
    print(f"The pooled matrix: \n{pooled_matrix} \n")

    # SRAM RESULT
    sram_matrix, _, _ = avg_pool_sram(test_matrix, kernel, stride, debug=True)
    print(f"The SRAM matrix: \n{sram_matrix} \n")

    # INDEXES COMPUTATION
    indexes = average_pooling_indexes(in_tensor, out_tensor, kernel, stride)
    print("The indexes:")
    for index in indexes:
        print(index)
