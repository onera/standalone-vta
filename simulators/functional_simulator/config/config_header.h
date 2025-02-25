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
  // union instruction_t {
  //   uint64_t upper_section;
  //   uint64_t lower_section;
  // };
  typedef __uint128_t instruction_t; // To modify with union or struct! (TODO)
  typedef uint32_t uop_t; // To modify with union or struct! (TODO)

#endif  // CONFIG_HEADER_H_