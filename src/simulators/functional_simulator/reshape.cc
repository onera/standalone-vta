// IMPORT PACKAGES
// ---------------
#include "simulator_header.h"

#include <iostream>
#include <vector>
#include <cmath>
#include <algorithm>
#include <numeric>

// Helper function for reshaping vectors
std::vector<int8_t> reshape_vector(const std::vector<int8_t>& data, int rows, int cols) {
    std::vector<int8_t> result(rows * cols);
    for (int i = 0; i < std::min((int)data.size(), rows * cols); i++) {
        result[i] = data[i];
    }
    return result;
}

// RESHAPING FUNCTIONS
// -------------------
/**
 * Transforms a 1D vector into a 2D matrix of block matrices.
 * 
 * Args:
 *     vector: Input 1D array
 *     block_col: Number of blocks per row
 *     block_size: Base size for square blocks (width for last row blocks)
 * 
 * Returns:
 *     Vector of vectors containing vectors representing blocks
 */
std::vector<std::vector<std::vector<std::vector<int8_t>>>> to_blocks(
    const std::vector<int8_t>& vector, 
    int block_col, 
    int block_size) {
    
    std::vector<std::vector<std::vector<std::vector<int8_t>>>> B;
    
    // 1. Calculate full row count
    int elements_per_full_row = block_col * block_size * block_size;
    int block_row = vector.size() / elements_per_full_row;
    
    // 2. Calculate last row parameters
    int remaining = vector.size() % elements_per_full_row;
    bool last_row_exists = remaining > 0;
    
    // 3. Process complete rows
    for (int i = 0; i < block_row; i++) {
        std::vector<std::vector<std::vector<int8_t>>> row;
        for (int j = 0; j < block_col; j++) {
            int start = (i * block_col + j) * block_size * block_size;
            int end = start + block_size * block_size;
            
            std::vector<std::vector<int8_t>> block(block_size, std::vector<int8_t>(block_size));
            for (int r = 0; r < block_size; r++) {
                for (int c = 0; c < block_size; c++) {
                    block[r][c] = vector[start + r * block_size + c];
                }
            }
            row.push_back(block);
        }
        B.push_back(row);
    }
    
    // 4. Handle last incomplete row if needed
    if (last_row_exists) {
        int elements_per_block = remaining / block_col;
        int subheight = elements_per_block / block_size;
        std::vector<std::vector<std::vector<int8_t>>> last_row;
        int base_index = block_row * elements_per_full_row;
        
        for (int j = 0; j < block_col; j++) {
            int start = base_index + j * elements_per_block;
            int end = start + elements_per_block;
            
            std::vector<int8_t> block_flat;
            for (int k = start; k < std::min(end, (int)vector.size()); k++) {
                block_flat.push_back(vector[k]);
            }
            
            // Handle potential padding for reshape
            while (block_flat.size() < subheight * block_size) {
                block_flat.push_back(0);
            }
            
            std::vector<std::vector<int8_t>> block(subheight, std::vector<int8_t>(block_size));
            for (int r = 0; r < subheight; r++) {
                for (int c = 0; c < block_size; c++) {
                    block[r][c] = block_flat[r * block_size + c];
                }
            }
            last_row.push_back(block);
        }
        B.push_back(last_row);
    }
    
    return B;
}

/**
 * Reconstructs a matrix from blocks created by to_blocks(), removing padding.
 * 
 * Args:
 *     list_blocks: 2D list of blocks from to_blocks()
 *     block_size: Original block size used for splitting
 *     matrix_height: Original matrix height (without padding)
 *     matrix_width: Original matrix width (without padding)
 * 
 * Returns:
 *     Reconstructed matrix as 2D vector
 */
std::vector<std::vector<int8_t>> unsplit(
    const std::vector<std::vector<std::vector<std::vector<int8_t>>>>& list_blocks,
    int block_size,
    int matrix_height,
    int matrix_width) {
    
    // Initialize the final matrix
    std::vector<std::vector<int8_t>> reconstructed(
        matrix_height, std::vector<int8_t>(matrix_width, 0));
    
    // Iterate over every element in the final matrix
    for (int i = 0; i < matrix_height; i++) {
        for (int j = 0; j < matrix_width; j++) {
            // Calculate the indices of the block containing (i, j)
            int delta_height = i / block_size;  // Row index of the block
            int delta_width = j / block_size;   // Column index of the block
            
            // Calculate the position within the block
            int r = i % block_size;  // Row inside the block
            int t = j % block_size;  // Column inside the block
            
            // Access the corresponding block and copy the value
            if (delta_height < list_blocks.size() && delta_width < list_blocks[delta_height].size()) {
                const auto& block = list_blocks[delta_height][delta_width];
                if (r < block.size() && t < block[r].size()) {  // Ensure no padding is copied
                    reconstructed[i][j] = block[r][t];
                }
            }
        }
    }
    
    return reconstructed;
}

/**
 * Converts a result matrix (after matmul) into a 4D tensor by rearranging the channels.
 * 
 * Arguments:
 * res -- Result matrix after matmul
 * batch_size -- Batch size
 * output_channels -- Number of filters (output channels)
 * output_height -- Height of the output
 * output_width -- Width of the output
 * 
 * Returns:
 * A tensor of shape (batch_size, output_channels, output_height, output_width)
 */
std::vector<std::vector<std::vector<std::vector<int8_t>>>> mat_to_tensor(
    const std::vector<std::vector<int8_t>>& res,
    int batch_size,
    int output_channels,
    int output_height,
    int output_width) {
    
    // Create output tensor of shape (batch_size, output_channels, output_height, output_width)
    std::vector<std::vector<std::vector<std::vector<int8_t>>>> tensor(
        batch_size,
        std::vector<std::vector<std::vector<int8_t>>>(
            output_channels,
            std::vector<std::vector<int8_t>>(
                output_height,
                std::vector<int8_t>(output_width)
            )
        )
    );
    
    // Transpose and reshape the matrix into a tensor
    // This implementation mimics the Python res.T.reshape()
    int idx = 0;
    for (int h = 0; h < res[0].size(); h++) {
        for (int w = 0; w < res.size(); w++) {
            int b = idx / (output_channels * output_height * output_width);
            int remainder = idx % (output_channels * output_height * output_width);
            int c = remainder / (output_height * output_width);
            remainder = remainder % (output_height * output_width);
            int y = remainder / output_width;
            int x = remainder % output_width;
            
            if (b < batch_size && c < output_channels && y < output_height && x < output_width) {
                tensor[b][c][y][x] = res[w][h];
            }
            idx++;
        }
    }
    
    return tensor;
}

/**
 * Converts an input tensor X into a matrix (im2row).
 * 
 * Arguments:
 * X -- Input tensor of shape (batch_size, input_channels, input_height, input_width)
 * kernel_size -- Filter size (height, width)
 * stride -- Convolution stride
 * 
 * Returns:
 * A matrix of shape (batch_size * output_height * output_width, input_channels * kernel_height * kernel_width)
 */
std::vector<std::vector<int8_t>> im2row(
    const std::vector<std::vector<std::vector<std::vector<int8_t>>>>& X,
    std::pair<int, int> kernel_size,
    int stride) {
    
    int batch_size = X.size();
    int input_channels = X[0].size();
    int input_height = X[0][0].size();
    int input_width = X[0][0][0].size();
    int kernel_height = kernel_size.first;
    int kernel_width = kernel_size.second;
    
    // Calculate the output dimensions
    int output_height = (input_height - kernel_height) / stride + 1;
    int output_width = (input_width - kernel_width) / stride + 1;
    
    // Initial output matrix
    int rows = batch_size * output_height * output_width;
    int cols = input_channels * kernel_height * kernel_width;
    std::vector<std::vector<int8_t>> result(rows, std::vector<int8_t>(cols, 0));
    
    // Fill the matrix with patches
    int row_idx = 0;
    for (int b = 0; b < batch_size; b++) {
        for (int i = 0; i <= input_height - kernel_height; i += stride) {
            for (int j = 0; j <= input_width - kernel_width; j += stride) {
                // Extract the patch and flatten it
                int col_idx = 0;
                for (int c = 0; c < input_channels; c++) {
                    for (int ki = 0; ki < kernel_height; ki++) {
                        for (int kj = 0; kj < kernel_width; kj++) {
                            result[row_idx][col_idx++] = X[b][c][i + ki][j + kj];
                        }
                    }
                }
                row_idx++;
            }
        }
    }
    
    return result;
}

/**
 * Pad the matrix such that its shape is a multiple of block_size.
 * If it is input, then only the number of column is padded.
 */
std::vector<std::vector<int8_t>> matrix_padding(
    const std::vector<std::vector<int8_t>>& matrix,
    int block_size = 16,
    bool isWeight = false,
    bool isSquare = true) {
    
    // Get the matrix size
    int n_row = matrix.size();
    int n_col = matrix[0].size();
    
    // Define the target dimensions (block_size or upper multiple of block_size)
    int target_rows;
    if (isWeight || isSquare) {  // Pad only the lines for the weight matrices
        target_rows = ((n_row - 1) / block_size + 1) * block_size;
    } else {  // Else, only the column are padded
        target_rows = n_row;
    }
    
    // Pad the column
    int target_cols = ((n_col - 1) / block_size + 1) * block_size;
    
    // Create the padded matrix
    std::vector<std::vector<int8_t>> padded_matrix(
        target_rows, std::vector<int8_t>(target_cols, 0));
    
    // Copy the original matrix
    for (int i = 0; i < n_row; i++) {
        for (int j = 0; j < n_col; j++) {
            padded_matrix[i][j] = matrix[i][j];
        }
    }
    
    return padded_matrix;
}

/**
 * Split the matrix into blocks using slicing to handle unequal row division.
 * For weight matrices (isWeight=true), it splits into square blocks of size block_size x block_size.
 * For other matrices (isWeight=false), it splits into blocks of size up to block_size x block_size,
 * splitting only along rows if the number of rows exceeds block_size.
 */
std::pair<std::vector<std::vector<std::vector<int8_t>>>, int> matrix_splitting(
    const std::vector<std::vector<int8_t>>& matrix,
    int block_size = 16,
    bool isWeight = false,
    bool isSquare = true) {
    
    // Get the matrix dimensions
    int n_row = matrix.size();
    int n_col = matrix[0].size();
    
    // Ensure the matrix width is a multiple of block_size
    if (n_col % block_size != 0) {
        throw std::invalid_argument("ERROR: Matrix width must be a multiple of block_size");
    }
    
    int blocks_col = n_col / block_size;  // Number of blocks in each column
    std::vector<std::vector<std::vector<int8_t>>> blocks;  // Vector to store the blocks
    
    if (isWeight || isSquare) {
        // Ensure the matrix height is a multiple of block_size
        if (n_row % block_size != 0) {
            throw std::invalid_argument("Matrix height must be a multiple of block_size");
        }
        
        int blocks_row = n_row / block_size;  // Number of blocks in each row
        for (int i = 0; i < blocks_row; i++) {
            for (int j = 0; j < blocks_col; j++) {
                std::vector<std::vector<int8_t>> block(block_size, std::vector<int8_t>(block_size));
                for (int r = 0; r < block_size; r++) {
                    for (int c = 0; c < block_size; c++) {
                        block[r][c] = matrix[i * block_size + r][j * block_size + c];
                    }
                }
                blocks.push_back(block);
            }
        }
    } else {
        // Calculate the number of blocks in each column
        int blocks_row = (n_row + block_size - 1) / block_size;  // Ensure that all rows are processed
        for (int i = 0; i < blocks_row; i++) {
            for (int j = 0; j < blocks_col; j++) {
                int row_start = i * block_size;
                int row_end = std::min((i + 1) * block_size, n_row);  // Ensure not to exceed the number of rows
                
                std::vector<std::vector<int8_t>> block(row_end - row_start, std::vector<int8_t>(block_size));
                for (int r = 0; r < row_end - row_start; r++) {
                    for (int c = 0; c < block_size; c++) {
                        block[r][c] = matrix[row_start + r][j * block_size + c];
                    }
                }
                blocks.push_back(block);
            }
        }
    }
    
    // Return the list of blocks and the number of blocks per column
    return {blocks, blocks_col};
}

/**
 * Main reshape function that combines all transformation steps
 */
std::vector<int8_t> reshape(
    const std::vector<int8_t>& vector,
    int block_col,
    int block_size,
    int out_matrix_height,
    int out_matrix_width,
    int batch_size,
    int out_tensor_channel,
    int out_tensor_height,
    int out_tensor_width,
    std::pair<int, int> kernel_size,
    int stride,
    bool isSquare) {
    
    // 1 - VECTOR -> BLOCKS
    auto list_blocks = to_blocks(vector, block_col, block_size);
    
    // 2 - BLOCKS -> MATRIX (unpad)
    auto previous_matrix = unsplit(list_blocks, block_size, out_matrix_height, out_matrix_width);
    
    // 3 - MATRIX -> TENSOR
    auto tensor = mat_to_tensor(previous_matrix, batch_size, out_tensor_channel, out_tensor_height, out_tensor_width);
    
    // 4 - TENSOR -> NEW MATRIX (unpad)
    auto new_matrix = im2row(tensor, kernel_size, stride);
    
    // 5 - NEW MATRIX -> PADDED MATRIX
    auto padded_matrix = matrix_padding(new_matrix, block_size, false, isSquare);
    
    // 6 - PADDED MATRIX -> BLOCKS
    auto [blocks, _] = matrix_splitting(padded_matrix, block_size, false, isSquare);
    
    // 7 - BLOCKS -> VECTOR (flatten blocks)
    std::vector<int8_t> reshaped_vector;
    for (const auto& block : blocks) {
        for (const auto& row : block) {
            for (const auto& val : row) {
                reshaped_vector.push_back(val);
            }
        }
    }
    
    return reshaped_vector;
}
