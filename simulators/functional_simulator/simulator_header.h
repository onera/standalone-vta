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


  /***************************
    Other functions' prototype
  ****************************/
  // Dump memory into a binary file
  void dump_memory(void * ptr, const char * path, size_t size, size_t n_element);

  // Print int8_t vector
  void print_int8_vector(int8_t * vector, uint64_t size);

  // Print int32_t vector
  void print_int32_vector(int32_t * vector, uint64_t size);

  // Compare two 8-bit vectors
  bool compare_vector(int8_t * vector_A, int8_t * vector_B, uint64_t size);

  // Initialise vector with random values or with "-1" values
  int8_t * init_vector_values(int8_t * vector, uint64_t size, bool random_value, unsigned int seed);

#endif  // SIMULATOR_HEADER_H_