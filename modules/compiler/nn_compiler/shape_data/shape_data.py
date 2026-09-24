# IMPORT PACKAGES
# ---------------
import os
import sys

import numpy as np


###############################################

# EXPAND_BIAS 
# -----------
def expand_bias(vector, target_rows):
    """
    Expands a 1D numpy array into a 2D matrix using np.tile.
    """
    return np.tile(vector, (target_rows, 1))


###############################################

# KER2COL 
# -------
def ker2col(K, dtype=np.int8):
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
    
    kernel_matrix = np.zeros((rows, cols), dtype=dtype)
    
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


###############################################

# KER2OIHWIO
# ----------
def ker2oihwio(K, block_size=16, dtype=np.int8):
    """Pack convolution weights for the direct-convolution lowering.

    ker2col flattens (ic, kh, kw) into one reduction axis because the im2row
    GEMM reduces over it in one go. The direct lowering instead treats each
    kernel tap as its own reduction step, so the taps have to stay separate and
    each (output-channel block, input-channel block, tap) needs its own
    16x16 weight block - upstream TVM VTA's OIHWio layout.

    Block order is the one direct_conv.conv_uops() computes as wgt_idx:

        blk = ((ocb * IC_blocks + icb) * kh + dy) * kw + dx

    Each block is stored [out-channel][in-channel], matching the orientation
    the GEMM wants (acc[16] += WGT[16][16] . INP[16]); note this is already
    transposed relative to the ker2col path, where main_vta_compiler transposes
    on the way out instead.

    Arguments:
    K -- kernel weights, shape (out_channels, in_channels, kernel_h, kernel_w)

    Returns:
    Array of shape (OC_blocks * IC_blocks * kh * kw, block_size, block_size).
    Channel padding is zero-filled, which contributes nothing to the sum.
    """
    out_channels, in_channels, kernel_height, kernel_width = K.shape
    ic_blocks = (in_channels + block_size - 1) // block_size
    oc_blocks = (out_channels + block_size - 1) // block_size

    blocks = np.zeros(
        (oc_blocks * ic_blocks * kernel_height * kernel_width, block_size, block_size),
        dtype=dtype,
    )

    for oc in range(out_channels):
        for ic in range(in_channels):
            for dy in range(kernel_height):
                for dx in range(kernel_width):
                    blk = (
                        ((oc // block_size) * ic_blocks + ic // block_size)
                        * kernel_height
                        + dy
                    ) * kernel_width + dx
                    blocks[blk, oc % block_size, ic % block_size] = K[oc, ic, dy, dx]

    return blocks


###############################################

# FLATTEN
# -------
def flatten_conv_output(Y):
    """
    Flattens the output of a standard convolution to match the result of 
    an im2row GEMM operation.
    
    Arguments:
    Y -- Output tensor of shape (batch_size, output_channels, output_height, output_width)
    
    Returns:
    A matrix of shape (batch_size * output_height * output_width, output_channels)
    """
    # 1. Permute dimensions to (batch_size, output_height, output_width, output_channels)
    # We move the channel dimension (axis 1) to the last position.
    Y_permuted = Y.transpose(0, 2, 3, 1)
    
    # 2. Reshape to combine batch and spatial dimensions into rows
    # The -1 infers the row dimension size automatically based on the input size
    output_channels = Y.shape[1]
    result = Y_permuted.reshape(-1, output_channels)
    
    return result


