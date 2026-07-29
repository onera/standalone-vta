#ifndef VTA_BOARD_H_
#define VTA_BOARD_H_

#include <cstdint>

#ifndef VTA_UART_BAUD
#define VTA_UART_BAUD 921600u
#endif

namespace vta {

// Reinitialize PS UART at the given baud rate.
// Call at the very top of main(), before any xil_printf / inbyte / outbyte.
void board_init(std::uint32_t baud = VTA_UART_BAUD);

} // namespace vta

#endif // VTA_BOARD_H_
