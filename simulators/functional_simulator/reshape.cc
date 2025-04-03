/***************************
    PRE-PROCESSOR DIRECTIVES
****************************/
#include "simulator_header.h"

#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <string.h>


/***************************
    TRANSFORMATION FUNCTIONS
****************************/
void to_blocks(int8_t* vector, int length, int block_col, int block_size, int8_t**** B, int* block_row, int* last_row_height) {
    // Preliminary computations
    int elements_per_full_row = block_col * block_size * block_size;
    *block_row = length / elements_per_full_row;
    int remaining = length % elements_per_full_row;
    int last_row_exists = remaining > 0;

    // Allocation of array of blocks
    *B = (int8_t***)malloc((*block_row + (last_row_exists ? 1 : 0)) * sizeof(int8_t**));

    // Process the full blocks
    for (int i = 0; i < *block_row; i++) {
        (*B)[i] = (int8_t**)malloc(block_col * sizeof(int8_t*));
        for (int j = 0; j < block_col; j++) {
            int start = (i * block_col + j) * block_size * block_size;
            (*B)[i][j] = (int8_t*)malloc(block_size * block_size * sizeof(int8_t));
            memcpy((*B)[i][j], &vector[start], block_size * block_size * sizeof(int8_t));
        }
    }

    // Process the last row if any 
    if (last_row_exists) {
        int elements_per_block = remaining / block_col;
        *last_row_height = elements_per_block / block_size;
        int base_index = (*block_row) * elements_per_full_row;

        (*B)[*block_row] = (int8_t**)malloc(block_col * sizeof(int8_t*));
        for (int j = 0; j < block_col; j++) {
            int start = base_index + j * elements_per_block;
            (*B)[*block_row][j] = (int8_t*)malloc((*last_row_height) * block_size * sizeof(int8_t));

            memcpy((*B)[*block_row][j], &vector[start], elements_per_block * sizeof(int8_t));
            if (elements_per_block < (*last_row_height) * block_size) {
                memset((*B)[*block_row][j] + elements_per_block, 0, ((*last_row_height) * block_size - elements_per_block) * sizeof(int8_t));
            }
        }
    }
}

void unsplit(int8_t*** B, int block_size, int matrix_height, int matrix_width, int8_t*** reconstructed) {
    // Allocation of the reconstructed matrix
    *reconstructed = (int8_t**)malloc(matrix_height * sizeof(int8_t*));
    for (int i = 0; i < matrix_height; i++) {
        (*reconstructed)[i] = (int8_t*)malloc(matrix_width * sizeof(int8_t));
    }

    // Reconstruct the matrix
    for (int i = 0; i < matrix_height; i++) {
        for (int j = 0; j < matrix_width; j++) {
            // Find the block containing (i,j)
            int delta_height = i / block_size;  // Index of the block on the row
            int delta_width = j / block_size;   // Index of the block on the column

            // Poisition of (i, j) in the block
            int r = i % block_size;
            int t = j % block_size;

            // Copy the value
            if (B[delta_height] != NULL && B[delta_height][delta_width] != NULL) {
                (*reconstructed)[i][j] = B[delta_height][delta_width][r * block_size + t];
            } else {
                (*reconstructed)[i][j] = 0;  // If it does not exist write 0
            }
        }
    }
}

int8_t**** mat_to_tensor(int8_t** matrix, int matrix_h, int matrix_w, 
                        int batch_size, int output_channels,
                        int output_height, int output_width) {
    /* Vérifier la correspondance des dimensions */
    int total_elements = batch_size * output_channels * output_height * output_width;
    if (matrix_h * matrix_w != total_elements) {
        fprintf(stderr, "Dimension mismatch: Matrix contains %d elements but tensor requires %d\n",
                matrix_h * matrix_w, total_elements);
        exit(EXIT_FAILURE);
    }

    /* Allocation du tensor 4D */
    int8_t**** tensor = (int8_t****)malloc(batch_size * sizeof(int8_t***));
    for (int b = 0; b < batch_size; b++) {
        tensor[b] = (int8_t***)malloc(output_channels * sizeof(int8_t**));
        for (int c = 0; c < output_channels; c++) {
            tensor[b][c] = (int8_t**)malloc(output_height * sizeof(int8_t*));
            for (int h = 0; h < output_height; h++) {
                tensor[b][c][h] = (int8_t*)malloc(output_width * sizeof(int8_t));
            }
        }
    }

    /* Remplir le tensor en réorganisant les données */
    int idx = 0;
    for (int b = 0; b < batch_size; b++) {
        for (int c = 0; c < output_channels; c++) {
            for (int h = 0; h < output_height; h++) {
                for (int w = 0; w < output_width; w++) {
                    // Calculer l'index de la matrice (ligne/colonne)
                    int matrix_row = idx / matrix_w;  // index de ligne dans la matrice
                    int matrix_col = idx % matrix_w;  // index de colonne dans la matrice

                    // Copie des valeurs dans le tensor
                    tensor[b][c][h][w] = matrix[matrix_row][matrix_col];
                    idx++;
                }
            }
        }
    }

    return tensor;
}

int8_t** im2row(int8_t**** X, int batch_size, int input_channels, 
                int input_height, int input_width, 
                int kernel_height, int kernel_width, int stride,
                int* output_height, int* output_width) {
    
    // Calculate output dimensions
    *output_height = (input_height - kernel_height) / stride + 1;
    *output_width = (input_width - kernel_width) / stride + 1;
    int rows = batch_size * (*output_height) * (*output_width);
    int cols = input_channels * kernel_height * kernel_width;

    // Allocate result matrix
    int8_t** result = (int8_t**)malloc(rows * sizeof(int8_t*));
    for(int i=0; i<rows; i++) {
        result[i] = (int8_t*)malloc(cols * sizeof(int8_t));
    }

    // Fill matrix with patches
    int row_idx = 0;
    for(int b=0; b<batch_size; b++) {
        for(int i=0; i <= input_height - kernel_height; i += stride) {
            for(int j=0; j <= input_width - kernel_width; j += stride) {
                
                int8_t* patch = result[row_idx];
                int patch_idx = 0;
                
                // Extract patch from 4D tensor
                for(int c=0; c<input_channels; c++) {
                    for(int di=0; di<kernel_height; di++) {
                        for(int dj=0; dj<kernel_width; dj++) {
                            patch[patch_idx++] = X[b][c][i+di][j+dj];
                        }
                    }
                }
                row_idx++;
            }
        }
    }
    return result;
}

int8_t** matrix_padding(int8_t** matrix, int orig_rows, int orig_cols, 
                       int block_size, int isWeight, int isSquare,
                       int* target_rows, int* target_cols) {
    
    // Calculate target dimensions
    *target_rows = orig_rows;
    if(isWeight || isSquare) {
        *target_rows = ((orig_rows - 1) / block_size + 1) * block_size;
    }
    *target_cols = ((orig_cols - 1) / block_size + 1) * block_size;

    // Allocate padded matrix
    int8_t** padded = (int8_t**)malloc((*target_rows) * sizeof(int8_t*));
    for(int i=0; i<(*target_rows); i++) {
        padded[i] = (int8_t*)calloc((*target_cols), sizeof(int8_t)); // Initialize to 0
        if(i < orig_rows) {
            memcpy(padded[i], matrix[i], orig_cols * sizeof(int8_t));
        }
    }
    return padded;
}

int8_t*** matrix_splitting(int8_t** matrix, int padded_rows, int padded_cols, 
                          int block_size, int isWeight, int isSquare, 
                          int* num_blocks, int* blocks_col, int* blocks_row) {
    
    // Validate input dimensions
    if(padded_cols % block_size != 0) {
        fprintf(stderr, "Matrix width %d not multiple of block size %d\n", padded_cols, block_size);
        exit(EXIT_FAILURE);
    }

    *blocks_col = padded_cols / block_size;
    *blocks_row = (isWeight || isSquare) ? 
                    (padded_rows / block_size) : 
                    ((padded_rows + block_size - 1) / block_size);

    *num_blocks = (*blocks_row) * (*blocks_col);
    int8_t*** blocks = (int8_t***)malloc(*num_blocks * sizeof(int8_t**));

    int block_idx = 0;
    for(int i=0; i<(*blocks_row); i++) {
        for(int j=0; j<(*blocks_col); j++) {
            
            // Calculate block dimensions
            int rows = (isWeight || isSquare) ? block_size : 
                      ((i == (*blocks_row)-1) ? (padded_rows % block_size) : block_size);
            if(rows == 0) rows = block_size;

            // Allocate and copy block
            blocks[block_idx] = (int8_t**)malloc(rows * sizeof(int8_t*));
            for(int r=0; r<rows; r++) {
                blocks[block_idx][r] = (int8_t*)malloc(block_size * sizeof(int8_t));
                memcpy(blocks[block_idx][r], 
                      matrix[i*block_size + r] + j*block_size, 
                      block_size * sizeof(int8_t));
            }
            block_idx++;
        }
    }
    return blocks;
}

std::vector<int8_t> flatten_blocks(int8_t*** blocks, int num_blocks, int blocks_row, int block_size) {
    std::vector<int8_t> flattened_vector;
    int block_idx = 0;

    // Itérer sur tous les blocs
    for (int i = 0; i < blocks_row; i++) {
        for (int j = 0; j < (num_blocks / blocks_row); j++) {
            int rows = (i == blocks_row - 1) ? (num_blocks % blocks_row) : num_blocks;

            // Copier chaque ligne du bloc dans le vecteur
            for (int r = 0; r < rows; r++) {
                for (int c = 0; c < block_size; c++) {
                    flattened_vector.push_back(blocks[block_idx][r][c]);
                }
            }
            block_idx++;
        }
    }

    return flattened_vector;
}

/***************************
    MEMORY MANAGEMENT
****************************/
void free_blocks(int8_t*** B, int block_row, int block_col, int last_row_height) {
    for (int i = 0; i < block_row; i++) {
        for (int j = 0; j < block_col; j++) {
            free(B[i][j]);
        }
        free(B[i]);
    }
    if (last_row_height > 0) {
        for (int j = 0; j < block_col; j++) {
            free(B[block_row][j]);
        }
        free(B[block_row]);
    }
    free(B);
}

void free_matrix(int8_t** matrix, int height) {
    for (int i = 0; i < height; i++) {
        free(matrix[i]);
    }
    free(matrix);
}

void free_tensor(int8_t**** tensor, int batch_size, int output_channels, int output_height) {
    for(int b=0; b<batch_size; b++) {
        for(int c=0; c<output_channels; c++) {
            for(int h=0; h<output_height; h++) {
                free(tensor[b][c][h]);
            }
            free(tensor[b][c]);
        }
        free(tensor[b]);
    }
    free(tensor);
}

void free_matrix_splitting(int8_t*** blocks, int num_blocks, int blocks_row) {
    int block_idx = 0;
    for(int i = 0; i < blocks_row; i++) {
        for(int j = 0; j < (num_blocks / blocks_row); j++) {
            int rows = (i == blocks_row - 1) ? (num_blocks % blocks_row) : num_blocks;
            for (int r = 0; r < rows; r++) {
                free(blocks[block_idx][r]);  // Free each row (int8_t*)
            }
            free(blocks[block_idx]);  // Free the block (int8_t**)
            block_idx++;
        }
    }
    
    // Libérer le tableau de blocs (int8_t***)
    free(blocks);
}


/**************************
    RESHAPE (main function)
***************************/
///*
// Function to perform reshaping operations
std::vector<int8_t> reshape(const std::vector<int8_t>& vector_std, int block_col, int block_size, 
                       int out_matrix_height, int out_matrix_width,
                       int batch_size, int out_tensor_channel, int out_tensor_height, int out_tensor_width,
                       int kernel_size, int stride, bool isSquare) {
    // 0 - CONVERTING
    int8_t* vector = const_cast<int8_t*>(vector_std.data());
    //const int8_t* vector = vector_std.data();
    
    // 1 - VECTOR -> BLOCKS
    int8_t*** B;
    int block_row, last_row_height = 0;
    int length = vector_std.size();
    to_blocks(vector, length, block_col, block_size, &B, &block_row, &last_row_height);

    
    // 2 - BLOCKS -> MATRIX (unpad)
    int8_t** matrix;
    unsplit(B, block_size, out_matrix_height, out_matrix_width, &matrix);
  

    // 3 - MATRIX -> TENSOR
    int8_t**** tensor = mat_to_tensor(matrix, out_matrix_height, out_matrix_width, 
                                      batch_size, out_tensor_channel, out_tensor_height, out_tensor_width);

    // 4 - TENSOR -> NEW MATRIX (im2row)
    int final_matrix_height, final_matrix_width = 0;
    int8_t** out_matrix = im2row(tensor, batch_size, out_tensor_channel, 
                                 out_tensor_height, out_tensor_width, 
                                 kernel_size, kernel_size, stride,
                                 &final_matrix_height, &final_matrix_width);


    // 5 - NEW MATRIX -> PADDED MATRIX
    int target_rows, target_cols = 0;
    int8_t** padded_matrix = matrix_padding(out_matrix, final_matrix_height, final_matrix_width, 
                                            block_size, false, isSquare,
                                            &target_rows, &target_cols);

    // 6 - PADDED MATRIX -> BLOCKS
    int num_blocks, out_blocks_col, out_blocks_row = 0;
    int8_t*** blocks = matrix_splitting(padded_matrix, target_rows, target_cols, 
                                        block_size, false, isSquare, 
                                        &num_blocks, &out_blocks_col, &out_blocks_row);
    
    // 7 - BLOCKS -> BINARIES
    std::vector<int8_t> result_vector = flatten_blocks(blocks, num_blocks, out_blocks_row, block_size);


    // 8 - FREE THE MEMORIES
    free_blocks(B, block_row, block_col, last_row_height);
    free_matrix(matrix, out_matrix_height);
    free_tensor(tensor, batch_size, out_tensor_channel, out_tensor_height);
    free_matrix(out_matrix, final_matrix_height);
    free_matrix(padded_matrix, target_rows);
    free_matrix_splitting(blocks, num_blocks, out_blocks_row);
    
    // 8 - RETURN THE RESULT
    return result_vector;
}
//*/
