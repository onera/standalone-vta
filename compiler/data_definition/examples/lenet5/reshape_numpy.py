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


if __name__ == '__main__':
    # Init tensor
    im_tensor = np.random.randint(0, 4, size=(1, 1, 32, 32), dtype=np.int8)
    kernel_tensor = np.random.randint(0, 4, size=(6, 1, 5, 5), dtype=np.int8)

    # Convolution parameter
    kernel_size = (5, 5)
    stride = 1

    # Transformation
    im_matrix = im2row(im_tensor, kernel_size, stride)
    kernel_matrix = ker2col(kernel_tensor, kernel_size)

    # Print matrix size
    print(im_matrix.shape)  # (output_height * output_width, input_channels * kernel_height * kernel_width)
    print(kernel_matrix.shape)  # (input_channels * kernel_height * kernel_width, output_channels)
