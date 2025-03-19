import numpy as np

def im2row(X, kernel_size, stride):
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

def row2im(rows, X_shape, kernel_size, stride):
    """
    Reconstructs an input tensor from the matrix of patches.
    
    Arguments:
    rows -- Matrix of patches (result from im2row) with shape (batch_size * output_height * output_width, kernel_height * kernel_width * input_channels)
    X_shape -- Original shape of the input tensor (batch_size, input_channels, input_height, input_width)
    kernel_size -- Filter size (height, width)
    stride -- Convolution stride
    
    Returns:
    A tensor of shape (batch_size, input_channels, input_height, input_width)
    """
    batch_size, input_channels, input_height, input_width = X_shape
    kernel_height, kernel_width = kernel_size
    
    # Calculate the output dimensions
    output_height = (input_height - kernel_height) // stride + 1
    output_width = (input_width - kernel_width) // stride + 1
    
    # Recreate the output tensor
    X_reconstructed = np.zeros((batch_size, input_channels, input_height, input_width))
    count_matrix = np.zeros((batch_size, input_channels, input_height, input_width))
    
    row_idx = 0
    for b in range(batch_size):
        for i in range(0, input_height - kernel_height + 1, stride):
            for j in range(0, input_width - kernel_width + 1, stride):
                # Extract the patch from the row of the matrix
                patch = rows[row_idx].reshape(input_channels, kernel_height, kernel_width)
                X_reconstructed[b, :, i:i+kernel_height, j:j+kernel_width] += patch
                count_matrix[b, :, i:i+kernel_height, j:j+kernel_width] += 1
                row_idx += 1
    
    # Normalize the reconstruction (in case multiple patches overlap)
    X_reconstructed /= count_matrix
    return X_reconstructed


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
    reshaped_res = res.T.reshape(output_channels, output_height, output_width)
    
    # Add the batch_size dimension
    reshaped_res = reshaped_res[np.newaxis, :]
    
    return reshaped_res