/*!
 * \file simulator_header.h
 * \brief Header for main_simulator.cc and the functions for interacting with the simulator
 */

#ifndef SIMULATOR_HEADER_H_
  #define SIMULATOR_HEADER_H_

  /********************* 
    Include the packages 
  **********************/
  // System package
  #include <filesystem>
  #include <iostream>
  #include <fstream>
  #include <vector>

  // Configuration
  #include "config/config_header.h" // Instruction and UOP types

  // VTA's libraries
  #include "include/driver.h"
  #include "include/sim_tlpp.h"
  #include "include/virtual_memory.h"


  /******************************
    Execute simulator's prototype
  *******************************/
  // Execute simulator using binary files
  int execute_simulator(void);

  /********************
    READ BINARY FILES
  *********************/
  template <typename T>
  std::vector<T> read_binary_file(const std::string& file_path) {
      std::ifstream file(file_path, std::ios::binary);
      if (!file) {
          perror(("ERROR: Could not open file: " + file_path).c_str());
          return {}; // Return an empty vector
      }

      // Determine file size
      file.seekg(0, std::ios::end);
      std::streamsize file_size = file.tellg();
      file.seekg(0, std::ios::beg);

      if (file_size == -1) {
          std::cerr << "ERROR: Could not determine file size.\n";
          return {};
      }

      size_t num_elements = static_cast<size_t>(file_size) / sizeof(T);
      std::vector<T> buffer(num_elements);

      // Read data
      file.read(reinterpret_cast<char*>(buffer.data()), file_size);

      if (file.gcount() != file_size) {
          std::cerr << "Warning: Could only read " << file.gcount() << " bytes from file.\n";
      }

      file.close();
      return buffer;
  }


  /***************************
    Other functions' prototype
  ****************************/
  // Print int8_t vector
  void print_int8_vector(int8_t * vector, uint64_t size);

  // Print int32_t vector
  void print_int32_vector(int32_t * vector, uint64_t size);

  // Compare two 8-bit vectors
  bool compare_vector(int8_t * vector_A, int8_t * vector_B, uint64_t size);

  // Initialise vector with random values or with "-1" values
  int8_t * init_vector_values(int8_t * vector, uint64_t size, bool random_value, unsigned int seed);

  // Reshape function
  std::vector<int8_t> reshape(const std::vector<int8_t>& intermediate_result, int in_channel, int in_tensor_size, 
    int out_tensor_size, int kernel_size, int stride, int block_size, int nb_elements);

#endif  // SIMULATOR_HEADER_H_