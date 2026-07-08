/*!
 * \file config_header.h
 * \brief Header including the common type for the simulator and the operation
 */

#ifndef CONFIG_HEADER_H_
  #define CONFIG_HEADER_H_

  /********************* 
    Include the packages 
  **********************/
  // Basic libraries
  #include <stdio.h>
  #include <string> 
  #include <cstdint> // uint32_t
  #include <cstdlib> // srand() and rand()
  #include <ctime> // time()
  

  /********************
    NEW TYPE DEFINITION
  *********************/
  typedef __uint128_t instruction_t; // To modify with union or struct! (TODO)
  typedef uint32_t uop_t; // To modify with union or struct! (TODO)

  /********************
    VTA SCALAR DATA TYPES
  *********************/
  // Host-side element types for the INP / WGT / ACC / OUT buffers, derived from
  // the per-buffer log2 bit-width in the generated build/vta_config.h (force-
  // included into every TU by the Makefile). A log-width of 3 (8-bit) maps to
  // int8_t; anything wider (e.g. 5 = 32-bit) maps to int32_t. Single source of
  // truth shared by fsim_nn.cc / fsim_single_layer.cc (see include/fsim_layer.h).
  #if (VTA_LOG_INP_WIDTH == 3)
    using inp_dtype = int8_t;
  #else
    using inp_dtype = int32_t;
  #endif

  #if (VTA_LOG_WGT_WIDTH == 3)
    using wgt_dtype = int8_t;
  #else
    using wgt_dtype = int32_t;
  #endif

  #if (VTA_LOG_ACC_WIDTH == 3)
    using acc_dtype = int8_t;
  #else
    using acc_dtype = int32_t;
  #endif

  #if (VTA_LOG_OUT_WIDTH == 3)
    using out_dtype = int8_t;
  #else
    using out_dtype = int32_t;
  #endif

#endif  // CONFIG_HEADER_H_