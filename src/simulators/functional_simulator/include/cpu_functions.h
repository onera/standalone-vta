/*!
 * \file simulator_header.h
 * \brief Header for cpu_functions.cc emulating the CPU
 */

#ifndef CPU_FUNCTIONS_H
  #define CPU_FUNCTIONS_H

  /********************* 
    Include the packages 
  **********************/
  // System package
  #include <filesystem>
  #include <iostream>
  #include <fstream>
  #include <vector>
  #include <string>
  #include <cmath>
  #include <algorithm>
  #include <numeric>
  #include <stdexcept>


  /**************
    CPU FUNCTIONS
  ***************/
  // vec1DtoMat2D
  /**
    * Transforms a 1D vector into a 2D matrix (vector of vectors).
    * (Comments in British English as requested)
    *
    * If the input vector is smaller than the target matrix size,
    * the matrix is padded with default-initialised values (e.g., 0).
    * If the input vector is larger, the excess data is ignored.
    *
    * Args:
    * vector: Input 1D array
    * m_rows: Number of rows for the output matrix
    * n_columns: Number of columns for the output matrix
    *
    * Returns:
    * matrix: The resulting 2D matrix
    */
  template <typename T>
  std::vector<std::vector<T>> vec1DtoMat2D(
      const std::vector<T>& vector,
      int m_rows,
      int n_columns) {

      // Initialise the result matrix with the target dimensions.
      // T{} ensures default initialisation (e.g., 0 for numbers)
      std::vector<std::vector<T>> matrix(m_rows, std::vector<T>(n_columns, T{}));

      size_t input_size = vector.size();
      size_t k = 0; // Current index for the 1D input vector

      for (int i = 0; i < m_rows; ++i) {
          for (int j = 0; j < n_columns; ++j) {
              if (k < input_size) {
                  matrix[i][j] = vector[k];
                  k++;
              } else {
                  // We have run out of input elements.
                  // The rest of the matrix remains default-initialised.
                  return matrix;
              }
          }
      }

      // Warning if the input vector was larger than the matrix
      if (k < input_size) {
          std::cerr << "Warning: Input vector was larger than target matrix ("
                    << m_rows << "x" << n_columns
                    << "). Input data has been truncated.\n";
      }

      return matrix;
  }

  // matrix_padding
  /**
    * Pad the matrix such that its shape is a multiple of block_size.
    */
    template <typename T>
    std::vector<std::vector<T>> matrix_padding(
        const std::vector<std::vector<T>>& matrix,
        int block_size = 16,
        bool isSquare = true) {
        
        // Get the matrix size
        int n_row = matrix.size();
        int n_col = matrix[0].size();
        
        // ... (logic for target dims is the same) ...
        int target_rows;
        if (isSquare) { 
            target_rows = ((n_row - 1) / block_size + 1) * block_size;
        } else { 
            target_rows = n_row;
        }
        int target_cols = ((n_col - 1) / block_size + 1) * block_size;
        
        // Create the padded matrix
        std::vector<std::vector<T>> padded_matrix(
            target_rows, std::vector<T>(target_cols, T{}));
        
        // Copy the original matrix
        for (int i = 0; i < n_row; i++) {
            for (int j = 0; j < n_col; j++) {
                padded_matrix[i][j] = matrix[i][j];
            }
        }
        
        return padded_matrix;
    }

    // matrix_splitting
    /**
    * Split the matrix into blocks using slicing...
    */
    template <typename T>
    std::pair<std::vector<std::vector<std::vector<T>>>, int> matrix_splitting(
        const std::vector<std::vector<T>>& matrix,
        int block_size = 16,
        bool isSquare = true) {
        
        // ... (logic for dims is the same) ...
        int n_row = matrix.size();
        int n_col = matrix[0].size();
        
        if (n_col % block_size != 0) {
            throw std::invalid_argument("ERROR: Matrix width must be a multiple of block_size");
        }
        
        int blocks_col = n_col / block_size; 
        std::vector<std::vector<std::vector<T>>> blocks; 
        
        if (isSquare) {
            if (n_row % block_size != 0) {
                throw std::invalid_argument("Matrix height must be a multiple of block_size");
            }
            
            int blocks_row = n_row / block_size; 
            for (int i = 0; i < blocks_row; i++) {
                for (int j = 0; j < blocks_col; j++) {
                    std::vector<std::vector<T>> block(block_size, std::vector<T>(block_size, T{}));
                    for (int r = 0; r < block_size; r++) {
                        for (int c = 0; c < block_size; c++) {
                            block[r][c] = matrix[i * block_size + r][j * block_size + c];
                        }
                    }
                    blocks.push_back(block);
                }
            }
        } else {
            int blocks_row = (n_row + block_size - 1) / block_size; 
            for (int i = 0; i < blocks_row; i++) {
                for (int j = 0; j < blocks_col; j++) {
                    int row_start = i * block_size;
                    int row_end = std::min((i + 1) * block_size, n_row); 
                    
                    std::vector<std::vector<T>> block(row_end - row_start, std::vector<T>(block_size, T{}));
                    for (int r = 0; r < row_end - row_start; r++) {
                        for (int c = 0; c < block_size; c++) {
                            block[r][c] = matrix[row_start + r][j * block_size + c];
                        }
                    }
                    blocks.push_back(block);
                }
            }
        }
        
        return {blocks, blocks_col};
    }

  // flatten_blocks
  /**
    * Flattens a list of 2D blocks into a single 1D vector.
    *
    * Args:
    * blocks: A vector containing 2D blocks (matrices).
    * Expected shape: std::vector<std::vector<std::vector<T>>>
    *
    * Returns:
    * A 1D vector containing all elements from the blocks, concatenated.
    */
  template <typename T>
  std::vector<T> flatten_blocks(const std::vector<std::vector<std::vector<T>>>& blocks) {
      std::vector<T> reshaped_vector;
      
      // Reserve space if possible (optional but can improve performance)
      // size_t total_size = 0;
      // for (const auto& block : blocks) {
      //     for (const auto& row : block) {
      //         total_size += row.size();
      //     }
      // }
      // reshaped_vector.reserve(total_size);

      // Iterate and flatten
      for (const auto& block : blocks) {
          for (const auto& row : block) {
              // This is more efficient than a for-loop with push_back
              reshaped_vector.insert(reshaped_vector.end(), row.begin(), row.end());
          }
      }
      
      return reshaped_vector;
  }

  // data_formatting
  /**
    * Applies a complete data formatting pipeline to a 1D vector.
    *
    * The pipeline performs the following steps:
    * 0. Takes a 1D vector as input.
    * 1. Converts the 1D vector to a 2D matrix (vec1DtoMat2D).
    * 2. Pads the matrix to be a multiple of the block size (matrix_padding).
    * 3. Splits the padded matrix into a list of blocks (matrix_splitting).
    * 4. Flattens the list of blocks back into a single 1D vector (flatten_blocks).
    *
    * Args:
    * input_vector: The initial 1D vector.
    * m_rows: The number of rows for the intermediate matrix (step 1).
    * n_columns: The number of columns for the intermediate matrix (step 1).
    * block_size: The block size to use for padding and splitting.
    * isSquare: Flag for padding and splitting logic.
    *
    * Returns:
    * A new 1D vector, formatted according to the pipeline.
    */
  template <typename T>
  std::vector<T> data_formatting(
      const std::vector<T>& input_vector,
      int m_rows,
      int n_columns,
      int block_size = 16,
      bool isSquare = true) {
      
      // 1. vec1DtoMat2D
      auto matrix = vec1DtoMat2D(input_vector, m_rows, n_columns);
      
      // 2. matrix_padding
      auto padded_matrix = matrix_padding(matrix, block_size, isSquare);
      
      // 3. matrix_splitting
      // matrix_splitting returns a std::pair<vector_of_blocks, blocks_col_count>
      // We use C++17 structured binding to get the first element (the blocks)
      // and ignore the second one (with _)
      auto [blocks, _] = matrix_splitting(padded_matrix, block_size, isSquare);
      
      // 4. flatten_blocks
      return flatten_blocks(blocks);
  }


#endif  // CPU_FUNCTIONS_H
