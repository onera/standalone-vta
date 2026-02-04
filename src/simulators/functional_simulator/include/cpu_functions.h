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

  // convert_vector_type
  /**
    * Converts a vector of one type to a vector of another type.
    * (e.g., int8_t to int32_t).
    *
    * Args:
    * input: The source vector of type T_IN.
    *
    * Returns:
    * A new vector of type T_OUT containing the converted values.
    */
  template <typename T_OUT, typename T_IN>
  std::vector<T_OUT> convert_vector_type(const std::vector<T_IN>& input) {
      // The vector range constructor performs implicit type conversion automatically.
      // It also handles memory allocation efficiently in one go.
      return std::vector<T_OUT>(input.begin(), input.end());
  }

  // --------------------------------------------------------
  // RESHAPE HELPER FUNCTIONS (Dependencies for main reshape)
  // --------------------------------------------------------

  // to_blocks
  /**
   * Transforms a 1D vector into a 2D matrix of block matrices.
   * * Args:
   * vector: Input 1D array
   * block_col: Number of blocks per row
   * block_size: Base size for square blocks (width for last row blocks)
   * * Returns:
   * Vector of vectors containing vectors representing blocks (4D structure)
   */
  template <typename T>
  std::vector<std::vector<std::vector<std::vector<T>>>> to_blocks(
      const std::vector<T>& vector, 
      int block_col, 
      int block_size) {
      
      std::vector<std::vector<std::vector<std::vector<T>>>> B;
      
      // 1. Calculate full row count
      int elements_per_full_row = block_col * block_size * block_size;
      int block_row = vector.size() / elements_per_full_row;
      
      // 2. Calculate last row parameters
      int remaining = vector.size() % elements_per_full_row;
      bool last_row_exists = remaining > 0;
      
      // 3. Process complete rows
      for (int i = 0; i < block_row; i++) {
          std::vector<std::vector<std::vector<T>>> row;
          for (int j = 0; j < block_col; j++) {
              int start = (i * block_col + j) * block_size * block_size;
              // int end = start + block_size * block_size; // Unused variable removed
              
              std::vector<std::vector<T>> block(block_size, std::vector<T>(block_size, T{}));
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
          std::vector<std::vector<std::vector<T>>> last_row;
          int base_index = block_row * elements_per_full_row;
          
          for (int j = 0; j < block_col; j++) {
              int start = base_index + j * elements_per_block;
              int end = start + elements_per_block;
              
              std::vector<T> block_flat;
              for (int k = start; k < std::min(end, (int)vector.size()); k++) {
                  block_flat.push_back(vector[k]);
              }
              
              // Handle potential padding for reshape
              while (block_flat.size() < (size_t)(subheight * block_size)) {
                  block_flat.push_back(T{}); // Padding with default value
              }
              
              std::vector<std::vector<T>> block(subheight, std::vector<T>(block_size, T{}));
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

  // unsplit
  /**
   * Reconstructs a matrix from blocks created by to_blocks(), removing padding.
   */
  template <typename T>
  std::vector<std::vector<T>> unsplit(
      const std::vector<std::vector<std::vector<std::vector<T>>>>& list_blocks,
      int block_size,
      int matrix_height,
      int matrix_width) {
      
      // Initialize the final matrix
      std::vector<std::vector<T>> reconstructed(
          matrix_height, std::vector<T>(matrix_width, T{}));
      
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
              if (delta_height < (int)list_blocks.size() && delta_width < (int)list_blocks[delta_height].size()) {
                  const auto& block = list_blocks[delta_height][delta_width];
                  if (r < (int)block.size() && t < (int)block[r].size()) {  // Ensure no padding is copied
                      reconstructed[i][j] = block[r][t];
                  }
              }
          }
      }
      
      return reconstructed;
  }

  // mat_to_tensor
  /**
   * Converts a result matrix (after matmul) into a 4D tensor by rearranging the channels.
   * Mimics Python's res.T.reshape().
   */
  template <typename T>
  std::vector<std::vector<std::vector<std::vector<T>>>> mat_to_tensor(
      const std::vector<std::vector<T>>& res,
      int batch_size,
      int output_channels,
      int output_height,
      int output_width) {
      
      // Create output tensor of shape (batch_size, output_channels, output_height, output_width)
      std::vector<std::vector<std::vector<std::vector<T>>>> tensor(
          batch_size,
          std::vector<std::vector<std::vector<T>>>(
              output_channels,
              std::vector<std::vector<T>>(
                  output_height,
                  std::vector<T>(output_width, T{})
              )
          )
      );
      
      // Transpose and reshape the matrix into a tensor
      int idx = 0;
      for (int h = 0; h < (int)res[0].size(); h++) {
          for (int w = 0; w < (int)res.size(); w++) {
              int b = idx / (output_channels * output_height * output_width);
              int remainder = idx % (output_channels * output_height * output_width);
              int c = remainder / (output_height * output_width);
              remainder = remainder % (output_height * output_width);
              int y = remainder / output_width;
              int x = remainder % output_width;
              
              if (b < batch_size && c < output_channels && y < output_height && x < output_width) {
                  // UTILISEZ .at() POUR DÉTECTER LE CRASH ICI
                  try {
                      tensor.at(b).at(c).at(y).at(x) = res.at(w).at(h);
                  } catch (const std::out_of_range& e) {
                      std::cerr << "CRITICAL ERROR in mat_to_tensor!" << std::endl;
                      std::cerr << "Accessing tensor["<<b<<"]["<<c<<"]["<<y<<"]["<<x<<"]" << std::endl;
                      std::cerr << "Reading res["<<w<<"]["<<h<<"]" << std::endl;
                      exit(1);
                  }
              }
              idx++;
          }
      }
      return tensor;
  }

  // pad_tensor
  /**
  * Adds spatial padding to a 4D tensor with a custom fill value.
  *
  * Args:
  * tensor: Input 4D tensor (batch, channel, height, width)
  * padding: Vector of 4 integers [top, left, bottom, right]
  * fill_value: The value used to fill the padded areas (e.g., 0, -inf, etc.)
  *
  * Returns:
  * Padded 4D tensor
  */
  template <typename T>
  std::vector<std::vector<std::vector<std::vector<T>>>> pad_tensor(
      const std::vector<std::vector<std::vector<std::vector<T>>>>& tensor,
      const std::vector<int>& padding,
      T fill_value) { 
      
      // Safety check
      if (padding.size() != 4) {
          if (padding.empty()) return tensor;
          throw std::invalid_argument("Padding vector must have size 4: [top, left, bottom, right]");
      }
      int pad_top = padding[0];
      int pad_left = padding[1];
      int pad_bottom = padding[2];
      int pad_right = padding[3];
      // Optimization: if no padding is needed, return original
      if (pad_top == 0 && pad_left == 0 && pad_bottom == 0 && pad_right == 0) {
          return tensor;
      }
      int batch_size = tensor.size();
      int channels = tensor[0].size();
      int height = tensor[0][0].size();
      int width = tensor[0][0][0].size();
      int new_height = height + pad_top + pad_bottom;
      int new_width = width + pad_left + pad_right;
      // Initialize new tensor with 'fill_value'
      std::vector<std::vector<std::vector<std::vector<T>>>> padded_tensor(
          batch_size,
          std::vector<std::vector<std::vector<T>>>(
              channels,
              std::vector<std::vector<T>>(
                  new_height,
                  std::vector<T>(new_width, fill_value) 
              )
          )
      );
      // Copy original data to the center
      for (int b = 0; b < batch_size; ++b) {
          for (int c = 0; c < channels; ++c) {
              for (int h = 0; h < height; ++h) {
                  for (int w = 0; w < width; ++w) {
                      padded_tensor[b][c][h + pad_top][w + pad_left] = tensor[b][c][h][w];
                  }
              }
          }
      }
      return padded_tensor;
  }

  // im2row
  /**
   * Converts an input tensor X into a matrix (im2row).
   */
  template <typename T>
  std::vector<std::vector<T>> im2row(
      const std::vector<std::vector<std::vector<std::vector<T>>>>& X,
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
      // Initial output matrix
      std::vector<std::vector<T>> result(rows, std::vector<T>(cols, T{}));
      
      // Fill the matrix with patches
      int row_idx = 0;
      for (int b = 0; b < batch_size; b++) {
          for (int i = 0; i <= input_height - kernel_height; i += stride) {
              for (int j = 0; j <= input_width - kernel_width; j += stride) {
                  
                  // SECURITE : Vérifier row_idx AVANT d'écrire
                  if (row_idx >= rows) {
                      std::cerr << "CRITICAL ERROR in im2row: Row overflow!" << std::endl;
                      std::cerr << "Current row_idx: " << row_idx << " >= Allocated rows: " << rows << std::endl;
                      exit(1);
                  }

                  int col_idx = 0;
                  for (int c = 0; c < input_channels; c++) {
                      for (int ki = 0; ki < kernel_height; ki++) {
                          for (int kj = 0; kj < kernel_width; kj++) {
                              
                              // SECURITE : Vérifier col_idx
                              if (col_idx >= cols) {
                                   std::cerr << "CRITICAL ERROR in im2row: Col overflow!" << std::endl;
                                   std::cerr << "Current col_idx: " << col_idx << " >= Allocated cols: " << cols << std::endl;
                                   exit(1);
                              }
                              
                              // Utilisation de .at() pour l'accès au tenseur source aussi
                              try {
                                result.at(row_idx).at(col_idx++) = X.at(b).at(c).at(i + ki).at(j + kj);
                              } catch (...) {
                                std::cerr << "CRITICAL ERROR in im2row: Source tensor access out of bounds" << std::endl;
                                exit(1);
                              }
                          }
                      }
                  }
                  row_idx++;
              }
          }
      }
      
      return result;
  }

  // tensor_to_flat_matrix_rows
  /**
   * Flattens a 4D tensor into a 1D vector representing a matrix 
   * where rows are spatial pixels (B*H*W) and columns are channels (C).
   * This prepares the data for data_formatting().
   */
  template <typename T>
  std::vector<T> tensor_to_flat_matrix_rows(
      const std::vector<std::vector<std::vector<std::vector<T>>>>& tensor) {
      
      if (tensor.empty()) return {};

      int batch = tensor.size();
      int channel = tensor[0].size();
      int height = tensor[0][0].size();
      int width = tensor[0][0][0].size();

      std::vector<T> flat_vector;
      flat_vector.reserve(batch * height * width * channel);

      // We want to format as Matrix[Rows][Cols]
      // Rows = (b * h * w)
      // Cols = c
      // data_formatting's vec1DtoMat2D fills row by row.
      
      for (int b = 0; b < batch; ++b) {
          for (int h = 0; h < height; ++h) {
              for (int w = 0; w < width; ++w) {
                  for (int c = 0; c < channel; ++c) {
                      flat_vector.push_back(tensor[b][c][h][w]);
                  }
              }
          }
      }
      return flat_vector;
  }


  // --------------------------------------------------------
  // MAIN RESHAPE FUNCTIONS
  // --------------------------------------------------------
  
  // subtract_offset
  /**
    * Remove the offset on a vector.
    */
  template <typename T>
  std::vector<T> subtract_offset(
    const std::vector<T>& input_vector,
    int offset) {

      // Initialise directly with size (faster than reserve + push_back)
      std::vector<T> result(input_vector.size());

      for (size_t i = 0; i < input_vector.size(); ++i) {
          result[i] = input_vector[i] - offset;
      }

      return result;
  }


  // reshape
  /**
   * Main reshape function that combines all transformation steps.
   * * Steps:
   * 1. Vector -> Blocks (to_blocks)
   * 2. Blocks -> Matrix (unsplit - unpad)
   * 3. Matrix -> Tensor (mat_to_tensor) (+ pad)
   * 4. Tensor -> New Matrix (im2row)
   * 5. New Matrix -> Padded Matrix (matrix_padding)
   * 6. Padded Matrix -> Blocks (matrix_splitting)
   * 7. Blocks -> Vector (flatten_blocks)
   */
  template <typename T>
  std::vector<T> reshape(
      const std::vector<T>& vector,
      int block_size,
      int batch_size,
      int tensor_channel,
      int tensor_height,
      int tensor_width,
      std::pair<int, int> kernel_size,
      int stride,
      const std::vector<int>& padding = {0, 0, 0, 0},
      bool isSquare = false,
      int offset = 0
    ) { 

      if (vector.empty()) {
          std::cerr << "ERROR: Input vector is empty!" << std::endl;
          return {};
      }

      // 0 - CALCULATE VARIABLES
      int prev_outC_matrix_height = tensor_height * tensor_width;
      int prev_outC_matrix_width = tensor_channel;
      int block_col = (prev_outC_matrix_width + block_size - 1) / block_size;
      

      // 1 - VECTOR -> BLOCKS
      auto list_blocks = to_blocks(vector, block_col, block_size);

      
      // 2 - BLOCKS -> MATRIX (unpad)
      auto previous_matrix = unsplit(list_blocks, block_size, prev_outC_matrix_height, prev_outC_matrix_width);

      if (previous_matrix.empty()) {
           std::cerr << "CRITICAL: unsplit returned empty matrix." << std::endl;
           exit(1);
      }

      // 2b - APPLY OFFSET
      if (offset != 0) {
          for (auto& row : previous_matrix) {
              for (auto& val : row) {
                  val -= offset;
              }
          }
      }


      // 3 - MATRIX -> TENSOR
      auto tensor = mat_to_tensor(previous_matrix, batch_size, tensor_channel, tensor_height, tensor_width);
      

      // Check tensor validity
      if (tensor.empty() || tensor[0].empty() || tensor[0][0].empty()) {
          std::cerr << "CRITICAL: Tensor dimensions invalid/empty after step 3." << std::endl;
          exit(1);
      }
      
      // 3.5 - APPLY PADDING
      auto padded_tensor = pad_tensor(tensor, padding, 0);


      // 4 - TENSOR -> NEW MATRIX (unpad)
      auto new_matrix = im2row(padded_tensor, kernel_size, stride);

      
      // 5 - NEW MATRIX -> PADDED MATRIX
      auto padded_matrix = matrix_padding(new_matrix, block_size, isSquare);

      
      // 6 - PADDED MATRIX -> BLOCKS
      auto [blocks, _] = matrix_splitting(padded_matrix, block_size, isSquare);

      
      // 7 - BLOCKS -> VECTOR (flatten blocks)
      auto res = flatten_blocks(blocks);

      
      return res;
  }


  // rescaling
  /**
    * Rescales input vector values, adds an offset, and clamps to int8.
    *
    * Operations pipeline:
    * 1. Multiply value by rescale_factor (floating point).
    * 2. Round the result to the nearest integer.
    * 3. Add the integer offset.
    * 4. Clamp the result to the int8 range [-128, 127].
    * 5. Cast to int8_t.
    *
    * Args:
    * input_vector: Input vector of type T.
    * rescale_factor: Floating point factor.
    * offset: Integer offset to add after scaling.
    *
    * Returns:
    * std::vector<int8_t>: The resulting quantized vector.
    */
  template <typename T>
  std::vector<int8_t> rescaling(
      const std::vector<T>& input_vector,
      double rescale_factor,
      int32_t offset) {

      std::vector<int8_t> result;
      // Reserve memory to avoid reallocations
      result.reserve(input_vector.size());

      for (const auto& val : input_vector) {
          // 1. Multiply by factor (cast input to double for precision)
          // 2. Round to nearest integer
          double scaled_val = std::nearbyint(static_cast<double>(val) * rescale_factor); // round vs nearbyint

          // 3. Add offset (cast back to int32 for arithmetic)
          int32_t offsetted_val = static_cast<int32_t>(scaled_val) + offset;

          // 4. Clamp to int8 range [-128, 127]
          // We force the bounds to be integers to ensure correct comparison
          int32_t clamped_val = std::clamp(offsetted_val, -128, 127);

          // 5. Cast to int8_t
          result.push_back(static_cast<int8_t>(clamped_val));
      }

      return result;
  }

  // pad_matrix
  template <typename T>
    std::vector<T> pad_matrix(
        const std::vector<T>& input_data,
        int tensor_channel,
        int tensor_height,
        int tensor_width,
        int block_size,
        const std::vector<int>& padding_vec, // {top, left, bottom, right}
        int pad_value = -128 
    ) {
        
        // 1. Define dimensions (Batch=1 assumed based on context)
        int batch_size = 1; 
        int prev_h = tensor_height * tensor_width;
        int prev_w = tensor_channel;
        int block_col = (prev_w + block_size - 1) / block_size;

        // 2. Reconstruct Tensor (Vector -> Blocks -> Matrix -> Tensor)
        auto list_blocks = to_blocks(input_data, block_col, block_size);
        auto matrix = unsplit(list_blocks, block_size, prev_h, prev_w);
        auto tensor = mat_to_tensor(matrix, batch_size, tensor_channel, tensor_height, tensor_width);

        // 3. Apply Padding
        // Relies on your existing 'pad_tensor' function
        auto padded_tensor = pad_tensor(tensor, padding_vec, pad_value);

        // 4. Flatten Tensor to Matrix Rows
        auto flat_vector = tensor_to_flat_matrix_rows(padded_tensor);

        // 5. Re-format to VTA Block Structure
        // Calculate new spatial dimensions based on padding
        int p0 = padding_vec[0]; // Top
        int p1 = padding_vec[1]; // Left
        int p2 = padding_vec[2]; // Bottom
        int p3 = padding_vec[3]; // Right

        int new_height = tensor_height + p0 + p2;
        int new_width = tensor_width + p1 + p3;
        
        int m_rows = batch_size * new_height * new_width;
        int n_cols = tensor_channel;

        // Return the formatted, padded data
        return data_formatting(flat_vector, m_rows, n_cols, block_size, true);
    }
  
  // output_tensor
  /**
   * Performs the first 3 steps of reshape to get a tensor, 
   * then writes it to a binary file.
   * * Steps:
   * 1. Vector -> Blocks (to_blocks)
   * 2. Blocks -> Matrix (unsplit)
   * 3. Matrix -> Tensor (mat_to_tensor)
   * 4. Tensor -> Binary File
   */
  template <typename T>
  void output_tensor(
      const std::vector<T>& vector,
      int block_size,
      int batch_size,
      int tensor_channel,
      int tensor_height,
      int tensor_width,
      const std::string& filepath
  ) {
      if (vector.empty()) {
          std::cerr << "ERROR: Input vector is empty!" << std::endl;
          return;
      }

      // 0 - CALCULATE VARIABLES
      int prev_outC_matrix_height = tensor_height * tensor_width;
      int prev_outC_matrix_width = tensor_channel;
      int block_col = (prev_outC_matrix_width + block_size - 1) / block_size;
      
      // 1 - VECTOR -> BLOCKS
      auto list_blocks = to_blocks(vector, block_col, block_size);
      
      // 2 - BLOCKS -> MATRIX (unpad)
      auto previous_matrix = unsplit(list_blocks, block_size, prev_outC_matrix_height, prev_outC_matrix_width);

      if (previous_matrix.empty()) {
           std::cerr << "CRITICAL: unsplit returned empty matrix." << std::endl;
           exit(1);
      }

      // 3 - MATRIX -> TENSOR
      auto tensor = mat_to_tensor(previous_matrix, batch_size, tensor_channel, tensor_height, tensor_width);

      // Check tensor validity
      if (tensor.empty() || tensor[0].empty() || tensor[0][0].empty()) {
          std::cerr << "CRITICAL: Tensor dimensions invalid/empty after step 3." << std::endl;
          exit(1);
      }

      // 4 - WRITE TENSOR TO BINARY FILE
      std::ofstream out(filepath, std::ios::binary);
      if (!out.is_open()) {
          std::cerr << "ERROR: Could not open file " << filepath << " for writing." << std::endl;
          return;
      }

      // Iterate and write raw bytes
      // Dimensions: [batch_size][channels][height][width]
      for (const auto& batch : tensor) {
          for (const auto& channel : batch) {
              for (const auto& row : channel) {
                  for (const auto& val : row) {
                      out.write(reinterpret_cast<const char*>(&val), sizeof(T));
                  }
              }
          }
      }

      out.close();
      if (!out) {
          std::cerr << "ERROR: Write failure occurred for " << filepath << std::endl;
      } else {
          std::cout << "Tensor successfully written to " << filepath << std::endl;
      }
  }


  // --------------------------------------------------------
  // QLINEAR CONCAT OPERATOR
  // --------------------------------------------------------

  // qlinear_concat
  /**
   * Performs a Quantized Linear Concatenation on multiple input vectors.
   * * Steps:
   * 1. Reconstruct 4D tensors from blocked input vectors.
   * 2. Dequantize inputs, concatenate, and requantize to output scale/offset.
   * 3. Format the result back into the CPU block structure.
   * * Args:
   * inputs: Vector of input 1D vectors (blocked data).
   * shapes: Vector of shapes {N, C, H, W} for each input.
   * input_scales: Vector of float scales for each input.
   * input_zps: Vector of zero points for each input.
   * output_scale: Scale for the result.
   * output_zp: Zero point for the result.
   * axis: The axis to concatenate along (0=Batch, 1=Channel, etc.).
   * block_size: Architecture block size (default 16).
   */
  template <typename T>
  std::vector<T> qlinear_concat(
      const std::vector<std::vector<T>>& inputs,
      const std::vector<std::vector<int>>& shapes,
      const std::vector<float>& input_scales,
      const std::vector<int32_t>& input_zps,
      float output_scale,
      int32_t output_zp,
      int axis,
      int block_size = 16
  ) {
      // Basic validation
      if (inputs.size() != shapes.size() || inputs.size() != input_scales.size()) {
          throw std::invalid_argument("Size mismatch between inputs, shapes, or scales.");
      }
      if (inputs.empty()) return {};

      // 1. DETERMINE OUTPUT SHAPE
      std::vector<int> out_shape = shapes[0];
      for (size_t i = 1; i < shapes.size(); ++i) {
          out_shape[axis] += shapes[i][axis];
          // Check other dimensions match
          for (int d = 0; d < 4; ++d) {
              if (d != axis && shapes[i][d] != shapes[0][d]) {
                  throw std::invalid_argument("Input dimensions must match except for concat axis.");
              }
          }
      }

      int out_N = out_shape[0];
      int out_C = out_shape[1];
      int out_H = out_shape[2];
      int out_W = out_shape[3];

      // Initialize Output Tensor
      std::vector<std::vector<std::vector<std::vector<T>>>> output_tensor(
          out_N, std::vector<std::vector<std::vector<T>>>(
              out_C, std::vector<std::vector<T>>(
                  out_H, std::vector<T>(out_W, T{}))));

      // 2. PROCESS EACH INPUT
      int current_axis_offset = 0;

      for (size_t i = 0; i < inputs.size(); ++i) {
          const auto& vec = inputs[i];
          const auto& shape = shapes[i];
          float scale_in = input_scales[i];
          int32_t zp_in = input_zps[i];

          int N = shape[0];
          int C = shape[1];
          int H = shape[2];
          int W = shape[3];

          // A. RECONSTRUCT TENSOR (Logic from reshape)
          // -------------------------------------------------
          int matrix_h = H * W * N; // Flattening spatial + batch
          int matrix_w = C;
          
          int block_col = (matrix_w + block_size - 1) / block_size;

          // 1. Vector -> Blocks
          auto list_blocks = to_blocks(vec, block_col, block_size);
          
          // 2. Blocks -> Matrix
          auto matrix = unsplit(list_blocks, block_size, matrix_h, matrix_w);
          
          // 3. Matrix -> Tensor
          auto input_tensor = mat_to_tensor(matrix, N, C, H, W);
          // -------------------------------------------------

          // B. COPY & REQUANTIZE TO OUTPUT TENSOR
          // -------------------------------------------------
          for (int b = 0; b < N; ++b) {
              for (int c = 0; c < C; ++c) {
                  for (int h = 0; h < H; ++h) {
                      for (int w = 0; w < W; ++w) {
                          
                          // Determine position in output
                          int out_b = b + (axis == 0 ? current_axis_offset : 0);
                          int out_c = c + (axis == 1 ? current_axis_offset : 0);
                          int out_h = h + (axis == 2 ? current_axis_offset : 0); // usually not concatenated
                          int out_w = w + (axis == 3 ? current_axis_offset : 0); // usually not concatenated

                          // Get Value
                          T val_q = input_tensor[b][c][h][w];

                          // Dequantize: (x - zp_in) * s_in
                          float val_f = (static_cast<float>(val_q) - zp_in) * scale_in;

                          // Requantize: (x / s_out) + zp_out
                          // Using nearbyint for rounding
                          int32_t val_rec = static_cast<int32_t>(std::nearbyint(val_f / output_scale)) + output_zp; // round vs nearbyint
                          
                          // Clamp (assuming int8 output range)
                          val_rec = std::clamp(val_rec, -128, 127);

                          output_tensor[out_b][out_c][out_h][out_w] = val_rec;
                      }
                  }
              }
          }
          
          // Update offset for next input
          current_axis_offset += shape[axis];
      }

      // 3. FLATTEN OUTPUT TENSOR (Tensor -> 1D Vector)
      // This creates a vector representing a (N*H*W) x C matrix row-by-row
      auto flat_vector = tensor_to_flat_matrix_rows(output_tensor);

      // 4. APPLY DATA FORMATTING (Pad -> Split -> Flatten Blocks)
      // Target Rows = N * H * W
      // Target Cols = C
      int m_rows = out_N * out_H * out_W;
      int n_cols = out_C;
      bool isSquare = true; 

      return data_formatting(flat_vector, m_rows, n_cols, block_size, isSquare);
  }

  // dequantize_linear
  /**
    * Dequantizes a vector of integers to floating point values.
    * ONNX Formula: y = (x - x_zero_point) * x_scale
    *
    * Args:
    * input_vector: Input vector of type T (e.g., int8 or int32).
    * scale: The floating point scale factor.
    * zero_point: The integer zero point offset.
    *
    * Returns:
    * std::vector<float>: The resulting floating point vector.
    */
  template <typename T>
  std::vector<float> dequantize_linear(
      const std::vector<T>& input_vector,
      float scale,
      int32_t zero_point) {

      std::vector<float> result;
      result.reserve(input_vector.size());

      for (const auto& val : input_vector) {
          // Cast input to float, subtract zero point, then multiply by scale
          float f = (static_cast<float>(val) - static_cast<float>(zero_point)) * scale;
          result.push_back(f);
      }

      return result;
  }

  // quantize_linear
  /**
    * Quantizes a vector of floating point values to integers.
    * ONNX Formula: y = saturate(round(x / scale) + zero_point)
    *
    * Args:
    * input_vector: Input vector of floats.
    * scale: The floating point scale factor.
    * zero_point: The integer zero point offset.
    *
    * Returns:
    * std::vector<int32_t>: The resulting quantized vector (clamped to int8 range).
    */
  inline std::vector<int32_t> quantize_linear(
      const std::vector<float>& input_vector,
      float scale,
      int32_t zero_point) {

      std::vector<int32_t> result;
      // Reserve memory to avoid reallocations
      result.reserve(input_vector.size());

      for (const auto& val : input_vector) {
          // 1. Divide by scale
          // 2. Round to nearest integer (using nearbyint)
          double scaled_val = std::nearbyint(val / scale); // round vs nearbyint

          // 3. Add Zero Point
          int32_t quant_val = static_cast<int32_t>(scaled_val) + zero_point;

          // 4. Saturate (Clamp)
          // Even though we return int32, the operation is "Quantize", 
          // so we clamp to the standard int8 range [-128, 127].
          quant_val = std::clamp(quant_val, -128, 127);

          result.push_back(quant_val);
      }

      return result;
  }

  // conv_transpose
  /**
    * Performs a ConvTranspose (Deconvolution) operation on floating point data.
    * * Pipeline:
    * 1. Reconstruct Input Tensor (from VTA blocked format).
    * 2. Perform arithmetic ConvTranspose (including padding handling).
    * 3. Add Bias.
    * 4. Flatten Output Tensor to (N*H*W, C) format.
    */
  /**
    * Performs a ConvTranspose (Deconvolution) on floating point data.
    * matches 'numpy_implementation.py' reference.
    */
  template <typename T>
  std::vector<T> conv_transpose(
      const std::vector<T>& input_vector,
      const std::vector<T>& weights,
      const std::vector<T>& bias,
      int batch_size,
      int in_channels, int in_height, int in_width,
      int out_channels, int out_height, int out_width,
      int kernel_h, int kernel_w,
      int stride,
      const std::vector<int>& padding, // {top, left, bottom, right}
      int block_size = 16
  ) {
      if (input_vector.empty()) return {};

      // 1. RECONSTRUCT INPUT TENSOR FROM BLOCKED DATA
      // ---------------------------------------------
      // The input is ALREADY a sequence of 16x16 blocks (flattened). 
      // We must not use 'to_blocks' (which assumes flat NCHW). 
      // Instead, we just reshape the vector into 2D blocks.
      
      int prev_h = in_height * in_width; 
      int prev_w = in_channels;
      
      // Calculate layout dimensions
      int block_col = (prev_w + block_size - 1) / block_size;
      int block_row = (prev_h + block_size - 1) / block_size; // Should typically be 1 for small inputs
      
      // A. Reconstruct the "List of Blocks" structure
      std::vector<std::vector<std::vector<T>>> list_blocks;
      size_t vals_per_block = block_size * block_size;
      size_t num_blocks = input_vector.size() / vals_per_block;
      
      // Re-assemble blocks directly from the linear stream
      for (size_t b = 0; b < num_blocks; ++b) {
          std::vector<std::vector<T>> block(block_size, std::vector<T>(block_size));
          size_t base_idx = b * vals_per_block;
          for (int r = 0; r < block_size; ++r) {
              for (int c = 0; c < block_size; ++c) {
                  block[r][c] = input_vector[base_idx + r * block_size + c];
              }
          }
          list_blocks.push_back(block);
      }
      
      // We need a 4D structure for 'unsplit' [BlockRow][BlockCol][BlockH][BlockW]
      // Since 'unsplit' expects that format, let's rearrange our linear list_blocks
      std::vector<std::vector<std::vector<std::vector<T>>>> grid_blocks;
      int block_idx = 0;
      for (int i = 0; i < block_row; ++i) {
          std::vector<std::vector<std::vector<T>>> row_of_blocks;
          for (int j = 0; j < block_col; ++j) {
              if (block_idx < (int)list_blocks.size()) {
                  row_of_blocks.push_back(list_blocks[block_idx++]);
              }
          }
          grid_blocks.push_back(row_of_blocks);
      }

      // B. Unsplit to Matrix -> Tensor
      auto matrix = unsplit(grid_blocks, block_size, prev_h, prev_w);
      auto input_tensor = mat_to_tensor(matrix, batch_size, in_channels, in_height, in_width);


      // 2. INITIALIZE OUTPUT TENSOR
      // ---------------------------
      std::vector<std::vector<std::vector<std::vector<T>>>> output_tensor(
          batch_size,
          std::vector<std::vector<std::vector<T>>>(
              out_channels,
              std::vector<std::vector<T>>(
                  out_height,
                  std::vector<T>(out_width, 0.0f)
              )
          )
      );

      // 3. PERFORM CONV TRANSPOSE
      // -------------------------
      int pad_top = padding[0];
      int pad_left = padding[1];

      for (int b = 0; b < batch_size; ++b) {
          for (int c_in = 0; c_in < in_channels; ++c_in) {
              for (int h_in = 0; h_in < in_height; ++h_in) {
                  for (int w_in = 0; w_in < in_width; ++w_in) {
                      
                      T input_val = input_tensor[b][c_in][h_in][w_in];
                      if (input_val == 0.0f) continue;

                      for (int c_out = 0; c_out < out_channels; ++c_out) {
                          for (int ky = 0; ky < kernel_h; ++ky) {
                              for (int kx = 0; kx < kernel_w; ++kx) {
                                  
                                  // SCATTER LOGIC
                                  int h_out = h_in * stride + ky - pad_top;
                                  int w_out = w_in * stride + kx - pad_left;

                                  if (h_out >= 0 && h_out < out_height && w_out >= 0 && w_out < out_width) {
                                      
                                      // NO FLIPPED WEIGHT ACCESS
                                      // ONNX standard ConvTranspose weights [In][Out][KH][KW] work directly
                                      // with the scatter logic (Input * Weight -> Output).
                                      
                                      // ONNX Layout: [In_Channels][Out_Channels/Group][KH][KW]
                                      // Assuming Group=1, so dim is [In][Out][KH][KW]
                                      int w_idx = c_in * (out_channels * kernel_h * kernel_w) + 
                                                  c_out * (kernel_h * kernel_w) + 
                                                  ky * kernel_w + kx;
                                      
                                      output_tensor[b][c_out][h_out][w_out] += input_val * weights[w_idx];
                                  }
                              }
                          }
                      }
                  }
              }
          }
      }

      // 4. ADD BIAS
      // -----------
      if (!bias.empty()) {
          for (int b = 0; b < batch_size; ++b) {
              for (int c_out = 0; c_out < out_channels; ++c_out) {
                  T b_val = bias[c_out];
                  for (int h = 0; h < out_height; ++h) {
                      for (int w = 0; w < out_width; ++w) {
                          output_tensor[b][c_out][h][w] += b_val;
                      }
                  }
              }
          }
      }

      // 5. FLATTEN OUTPUT AND FORMAT TO BLOCKS
      // --------------------------------------
      // We get a vector representing rows of a (N*H*W) x C matrix
      auto flat_vector = tensor_to_flat_matrix_rows(output_tensor);

      // We must format this into VTA blocks for compatibility with subsequent layers (like Quantize)
      // Target Matrix Dimensions:
      // Rows = Spatial (Batch * Height * Width)
      // Cols = Channels
      int m_rows = batch_size * out_height * out_width;
      int n_cols = out_channels;

      // Apply standard formatting (pad -> split -> flatten blocks)
      return data_formatting(flat_vector, m_rows, n_cols, block_size, true);
  }

#endif  // CPU_FUNCTIONS_H