/*!
 * \file simulator_header.h
 * \brief Header for main_simulator.cc and the functions for interacting with the simulator
 */

#ifndef SIMULATOR_HEADER_H_
  #define SIMULATOR_HEADER_H_

  /********************* Include the packages 
  **********************/
  // System package
  #include <filesystem>
  #include <iostream>
  #include <fstream>
  #include <vector>
  #include <string>
  #include <sstream>
  #include <unordered_map>
  #include <algorithm>

  // Configuration
  #include "../config/config_header.h" 

  // VTA's libraries
  #include "../include/driver.h"
  #include "../include/sim_tlpp.h"
  #include "../include/virtual_memory.h"
  #include "../include/cpu_functions.h"


  /******************************
    Execute simulator's prototype
  *******************************/
  int fsim_nn();

  /********************
    READ BINARY FILES
  *********************/
  template <typename T>
  std::vector<T> read_binary_file(const std::string& file_path) {
      std::ifstream file(file_path, std::ios::binary);
      if (!file) {
          perror(("ERROR: Could not open file: " + file_path).c_str());
          return {}; 
      }
      file.seekg(0, std::ios::end);
      std::streamsize file_size = file.tellg();
      file.seekg(0, std::ios::beg);

      if (file_size == -1) return {};

      size_t num_elements = static_cast<size_t>(file_size) / sizeof(T);
      std::vector<T> buffer(num_elements);

      file.read(reinterpret_cast<char*>(buffer.data()), file_size);
      file.close();
      return buffer;
  }

  /***************
    READ CSV FILES
  ****************/
  /**
  * Finds a row by its first element (the 'name') and returns the
  * element at the specified column index from that row.
  *
  * @param filename The path to the CSV file.
  * @param rowName The "key" to search for in the first column.
  * @param targetCol The 0-indexed column to retrieve from that row.
  * @return The element as a std::string, or an error message.
  */
  std::string getCsvElementByName(const std::string& filename, 
                                  const std::string& rowName, 
                                  int targetCol);
  
  // Type definition for the CSV map: Key -> Row values
  using CsvMap = std::unordered_map<std::string, std::vector<std::string>>;

  /**
   * Loads an entire CSV file into a hash map.
   * Key: The first column of the row.
   * Value: A vector containing all columns of that row (including the key at index 0).
   */
  CsvMap load_csv_to_map(const std::string& filename);

  /**
   * Helper to retrieve a value from the map.
   * Returns empty string or throws error if key/index invalid.
   */
  std::string get_csv_value(const CsvMap& map, const std::string& key, int col_index);

  // Convert string into int
  int strToInt(const std::string value);
  // Convert string into float
  float strToFloat(const std::string value);


  /***************************
    Other functions' prototype
  ****************************/
  void print_int8_vector(int8_t * vector, uint64_t size);
  void print_int32_vector(int32_t * vector, uint64_t size);
  bool compare_vector(int8_t * vector_A, int8_t * vector_B, uint64_t size);
  int8_t * init_vector_values(int8_t * vector, uint64_t size, bool random_value, unsigned int seed);

#endif  // SIMULATOR_HEADER_H_