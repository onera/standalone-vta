#ifndef DPI_TYPES_H_
#define DPI_TYPES_H_

#include <cstdint>

// Portable DPI scalar types used across all DPI-C function implementations.
// These match the Verilog DPI types: byte unsigned → dpi8_t, int → dpi32_t.
typedef unsigned char       dpi8_t;
typedef unsigned int        dpi32_t;
typedef unsigned long long  dpi64_t;

#endif  // DPI_TYPES_H_
