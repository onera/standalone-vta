import numpy as np

def im2row(X, kernel_size=2, stride=1):
    """
    Converts an input tensor X into a matrix (im2row).
    
    Arguments:
    X -- Input tensor of shape (batch_size, input_channels, input_height, input_width)
    kernel_size -- Filter size (height, width)
    stride -- Convolution stride
    
    Returns:
    A matrix of shape (batch_size, output_height * output_width * input_channels, kernel_height * kernel_width)
    """
    batch_size, input_channels, input_height, input_width = X.shape
    kernel_height, kernel_width = kernel_size
    
    # Calculate the output dimensions
    output_height = (input_height - kernel_height) // stride + 1
    output_width = (input_width - kernel_width) // stride + 1
    
    # Initial output matrix
    rows = batch_size * output_height * output_width
    cols = input_channels * kernel_height * kernel_width
    result = np.zeros((rows, cols), dtype=np.int8)
    
    # Fill the matrix with patches
    row_idx = 0
    for b in range(batch_size):
        for i in range(0, input_height - kernel_height + 1, stride):
            for j in range(0, input_width - kernel_width + 1, stride):
                # Extract the patch
                patch = X[b, :, i:i+kernel_height, j:j+kernel_width]
                result[row_idx] = patch.flatten()
                row_idx += 1
                
    return result

def ker2col(K):
    """
    Converts convolution weights (kernels) into a matrix (ker2col).
    
    Arguments:
    K -- Kernel weights of shape (output_channels, input_channels, kernel_height, kernel_width)
    
    Returns:
    A matrix of shape (input_channels * kernel_height * kernel_width, output_channels)
    """
    output_channels, input_channels, kernel_height, kernel_width = K.shape
    # C*H*W, N -> C is the number of input channel, H the height of the kernel, W the width of the kernel, N the number of output channel
    rows = input_channels * kernel_height * kernel_width  # C * H * W
    cols = output_channels  # N
    
    kernel_matrix = np.zeros((rows, cols), dtype=np.int8)
    
    # Fulfill the kernel
    col_idx = 0
    for oc in range(output_channels):  # Output channel 
        for ic in range(input_channels):  # Input channel 
            for h in range(kernel_height):  # Kernel height 
                for w in range(kernel_width):  # Kernel width 
                    # Each 3D filter is a column
                    kernel_matrix[ic * kernel_height * kernel_width + h * kernel_width + w, col_idx] = K[oc, ic, h, w]
        col_idx += 1

    return kernel_matrix

def mat_to_tensor(res, batch_size, output_channels, output_height, output_width):
    """
    Converts a result matrix (after matmul) into a 4D tensor by rearranging the channels.
    
    Arguments:
    res -- Result matrix after matmul
    batch_size -- Batch size
    output_channels -- Number of filters (output channels)
    output_height -- Height of the output
    output_width -- Width of the output
    
    Returns:
    A tensor of shape (batch_size, output_channels, output_height, output_width)
    """
    # Rearrange the matrix into a tensor of shape (batch_size, output_channels, output_height, output_width)
    # We need to manipulate the matrix so that the channels are correctly distributed
    reshaped_res = res.T.reshape(batch_size, output_channels, output_height, output_width)
    return reshaped_res

def to_blocks(vector, block_col, block_size):
    """
    Transforms a 1D vector into a 2D matrix of block matrices.
    
    Args:
        vector: Input 1D array (will be converted to numpy array)
        block_col: Number of blocks per row
        block_size: Base size for square blocks (width for last row blocks)
    
    Returns:
        List of lists containing numpy arrays representing blocks
    """
    vector = np.array(vector)
    B = []
    
    # 1. Calculate full row count
    elements_per_full_row = block_col * block_size**2
    block_row = len(vector) // elements_per_full_row
    
    # 2. Calculate last row parameters
    remaining = len(vector) % elements_per_full_row
    last_row_exists = remaining > 0
    
    # 3. Process complete rows
    for i in range(block_row):
        row = []
        for j in range(block_col):
            start = (i * block_col + j) * block_size**2
            end = start + block_size**2
            row.append(vector[start:end].reshape(block_size, block_size))
        B.append(row)
    
    # 4. Handle last incomplete row if needed
    if last_row_exists:
        elements_per_block = remaining // block_col
        subheight = elements_per_block // block_size
        last_row = []
        base_index = block_row * elements_per_full_row
        
        for j in range(block_col):
            start = base_index + j * elements_per_block
            end = start + elements_per_block
            block = vector[start:end]
            
            # Handle potential padding for reshape
            if len(block) < subheight * block_size:
                block = np.pad(block, (0, subheight*block_size - len(block)))
            
            last_row.append(block.reshape(subheight, block_size))
        
        B.append(last_row)
    
    return B

def unsplit(list_block, block_size, matrix_height, matrix_width):
    """
    Reconstructs a matrix from blocks created by to_blocks(), removing padding.
    
    Args:
        list_block: 2D list of blocks from to_blocks()
        block_size: Original block size used for splitting
        matrix_height: Original matrix height (without padding)
        matrix_width: Original matrix width (without padding)
    
    Returns:
        Reconstructed matrix as numpy array
    """
    # Initialize the final matrix
    reconstructed = np.zeros((matrix_height, matrix_width))
    
    # Iterate over every element in the final matrix
    for i in range(matrix_height):
        for j in range(matrix_width):
            # Calculate the indices of the block containing (i, j)
            delta_height = i // block_size  # Row index of the block
            delta_width = j // block_size  # Column index of the block
            
            # Calculate the position within the block
            r = i % block_size  # Row inside the block
            t = j % block_size  # Column inside the block
            
            # Access the corresponding block and copy the value
            if delta_height < len(list_block) and delta_width < len(list_block[delta_height]):
                block = list_block[delta_height][delta_width]
                if r < block.shape[0] and t < block.shape[1]:  # Ensure no padding is copied
                    reconstructed[i, j] = block[r, t]
    
    return reconstructed

if __name__ == '__main__':
    # TENSOR -> MATRIX
    # Init tensor
    im_tensor = np.random.randint(0, 4, size=(1, 1, 32, 32), dtype=np.int8)
    kernel_tensor = np.random.randint(0, 4, size=(6, 1, 5, 5), dtype=np.int8)
    # Convolution parameter
    kernel_size = (5, 5)
    stride = 1
    # Transformation
    im_matrix = im2row(im_tensor, kernel_size, stride)
    kernel_matrix = ker2col(kernel_tensor)
    # Print matrix size
    print(im_matrix.shape)  # (output_height * output_width, input_channels * kernel_height * kernel_width)
    print(kernel_matrix.shape)  # (input_channels * kernel_height * kernel_width, output_channels)

    # BIN -> BLOCKS
    vector = np.arange(1152)
    print(vector)
    # Convert to blocks (3 columns, 2x2 blocks)
    blocks = to_blocks(vector, block_col=2, block_size=16)
    print(len(blocks))
    i=0
    for row in blocks:
        for block in row:
            print("\nB", i)
            print(block)
            i += 1
    
    # BLOCKS -> MATRIX
    np.set_printoptions(threshold=np.inf, suppress=True, linewidth=np.inf)
    matrix = unsplit(blocks, block_size=16, matrix_height=36, matrix_width=32)
    print("\nThe reconstructed matrix\n", matrix)
