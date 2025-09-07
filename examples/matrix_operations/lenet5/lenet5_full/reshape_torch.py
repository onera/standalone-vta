import numpy as np
import torch

def im2row(X, kernel_size=2, stride=1):
    # Convert numpy into torch
    tensor = torch.tensor(X, dtype=torch.float32)
    # Get im2col matrix
    col_matrix = torch.nn.functional.unfold(tensor, kernel_size=kernel_size, stride=stride)
    # Get im2row matrix
    row_matrix = col_matrix.transpose(1, 2)
    # Flatten to get a 2D matrix
    row_matrix_2d = row_matrix.view(-1, row_matrix.size(-1))
    # Cast in int8
    row_matrix_2d_int8 = row_matrix_2d.to(torch.int8)
    # Ensure contiguous memory placement and convert in numpy
    return row_matrix_2d_int8.contiguous().numpy()

def ker2col(K):
    # Convert numpy in torch
    K_tensor = torch.tensor(K, dtype=torch.float32)
    output_channels, input_channels, kernel_height, kernel_width = K_tensor.shape
    # Change kernel into matrix and transpose
    kernel_matrix = K_tensor.view(output_channels, -1).t()
    # Cast in int8 and return
    kernel_matrix_int8 = kernel_matrix.to(torch.int8)
    return kernel_matrix_int8.numpy()

def mat_to_tensor(res, batch_size, output_channels, output_height, output_width):
    # Convert numpy into torch
    res_tensor = torch.tensor(res, dtype=torch.float32)
    # Transpose the matrix from (output_channels, batch_size * output_height * output_width) to (batch_size * output_channels, output_height * output_width)
    reshaped_res = res_tensor.T
    # Convert matrix into tensor
    reshaped_res = reshaped_res.view(batch_size, output_channels, output_height, output_width)
    # Cast in numpy int8 and return
    reshaped_res_int8 = reshaped_res.to(torch.int8)
    return reshaped_res_int8.numpy()

def tensor_to_mat(tensor_in):
    """
    Transforms a 4D PyTorch tensor into a NumPy matrix where each channel is a column.
    This is the inverse operation of the provided mat_to_tensor function.

    Args:
        tensor_in (torch.Tensor): The input tensor of shape 
                                  (batch_size, channels, height, width).

    Returns:
        numpy.ndarray: The resulting matrix of shape (batch_size * height * width, channels).
    """
    # Ensure the input is a torch tensor
    if not isinstance(tensor_in, torch.Tensor):
        tensor_in = torch.tensor(tensor_in)

    # Check if the tensor is 4D
    if tensor_in.dim() != 4:
        raise ValueError(f"Input tensor must be 4D (batch, channels, height, width), but got {tensor_in.dim()}D.")

    # Get the tensor dimensions
    batch_size, channels, height, width = tensor_in.shape

    # 1. Permute dimensions to bring the channels to the last position
    # The shape changes from (B, C, H, W) to (B, H, W, C)
    tensor_permuted = tensor_in.permute(0, 2, 3, 1)

    # 2. Flatten the first 3 dimensions to create the rows of the matrix
    # The .contiguous() call is important after a permutation to ensure
    # that the tensor is stored contiguously in memory before the reshape (view).
    # The shape becomes (B * H * W, C)
    matrix = tensor_permuted.contiguous().view(-1, channels)

    # 3. Convert to a NumPy array
    return matrix.numpy()

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
