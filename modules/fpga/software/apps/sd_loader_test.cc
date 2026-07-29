/**
 * sd_loader_test.cc - Standalone SD-card -> DRAM read test (phase 1).
 *
 * Self-contained baremetal app: depends only on the Xilinx BSP + xilffs
 * (FatFs). No VTA driver, no generated headers, no data-loader. It proves the
 * SD read path before we wire it into the VTA framework.
 *
 * What it does:
 *   1. f_mount the first SD controller (logical drive "0:/").
 *   2. f_open TEST_FILE and read it in chunks directly into a DDR pointer
 *      (DDR_DEST), accumulating a 32-bit additive byte checksum.
 *   3. Flush the written DDR range from cache.
 *   4. Read-back compare: for each window, invalidate the DDR range, re-read
 *      the same file offset into a static staging buffer, and memcmp staging
 *      vs. DDR. This is the gate that catches cache / AXI / DMA-coherency bugs.
 *   5. Print byte count, checksum, and READBACK OK / READBACK MISMATCH.
 *
 * Host prep: format a microSD as FAT32, copy TEST_FILE to its root.
 * The matching host checksum is `sum(open(f,'rb').read()) & 0xffffffff`
 * (see `./mill vta.fpga.sdChecksum`).
 *
 * The SD controller's MIO pins + clocks must already be configured by
 * ps7_init / psu_init (run via XSDB `loadhw` and/or the FSBL) before this app
 * runs, otherwise f_mount fails. See docs/fpga/sdcard_loader.md.
 *
 * Console (xil_printf) uses the BSP standalone_stdout UART, initialized by the
 * BSP at boot - no explicit UART setup needed here.
 */

#include <cstdint>
#include <cstring>

extern "C" {
#include "ff.h"
#include "xil_cache.h"
#include "xil_printf.h"
}

// ---------------------------------------------------------------------------
// Tunables
// ---------------------------------------------------------------------------

#define SD_DRIVE "0:/"                // logical drive 0 = first SD controller
#define TEST_FILE SD_DRIVE "test.bin" // 8.3 name -> no long-filename support
#define DDR_DEST 0x10000000u        // safe on Zynq-7000 (clear of OCM) + ZCU104
#define CHUNK_BYTES (64u * 1024u)   // f_read transfer size
#define STAGING_BYTES (64u * 1024u) // read-back compare window
#define MAX_BYTES (16u * 1024u * 1024u) // DDR write cap (guards huge files)

// Static so a large window never lives on the stack.
static std::uint8_t g_staging[STAGING_BYTES];

namespace {

// 32-bit additive byte checksum. Reproduced host-side as
// `sum(file_bytes) & 0xffffffff`.
inline std::uint32_t add_byte(std::uint32_t sum, std::uint8_t b) {
  return static_cast<std::uint32_t>(sum + b);
}

// Read the whole file into DDR_DEST in CHUNK_BYTES transfers.
// Returns the total bytes read; sets *checksum and *ok.
std::uint32_t read_into_ddr(FIL *fil, std::uint32_t *checksum, bool *ok) {
  auto *dst =
      reinterpret_cast<std::uint8_t *>(static_cast<std::uintptr_t>(DDR_DEST));
  std::uint32_t total = 0;
  std::uint32_t sum = 0;
  *ok = true;

  for (;;) {
    if (total >= MAX_BYTES) {
      xil_printf("ERROR: file exceeds MAX_BYTES (%u)\r\n",
                 static_cast<unsigned>(MAX_BYTES));
      *ok = false;
      break;
    }
    UINT want = CHUNK_BYTES;
    if (MAX_BYTES - total < want)
      want = MAX_BYTES - total;

    UINT br = 0;
    FRESULT fr = f_read(fil, dst + total, want, &br);
    if (fr != FR_OK) {
      xil_printf("ERROR: f_read failed at offset %u: %d\r\n",
                 static_cast<unsigned>(total), static_cast<int>(fr));
      *ok = false;
      break;
    }
    for (UINT i = 0; i < br; ++i)
      sum = add_byte(sum, dst[total + i]);
    total += br;
    if (br < want)
      break; // EOF
  }

  *checksum = sum;
  return total;
}

// Re-read the file window-by-window into g_staging, invalidate the matching DDR
// window, and compare. Returns true if every byte matches.
bool readback_compare(FIL *fil, std::uint32_t total) {
  auto *dst =
      reinterpret_cast<std::uint8_t *>(static_cast<std::uintptr_t>(DDR_DEST));

  FRESULT fr = f_lseek(fil, 0);
  if (fr != FR_OK) {
    xil_printf("ERROR: f_lseek(0) failed: %d\r\n", static_cast<int>(fr));
    return false;
  }

  std::uint32_t off = 0;
  while (off < total) {
    UINT want = STAGING_BYTES;
    if (total - off < want)
      want = total - off;

    UINT br = 0;
    fr = f_read(fil, g_staging, want, &br);
    if (fr != FR_OK || br != want) {
      xil_printf("ERROR: read-back f_read at %u: fr=%d br=%u want=%u\r\n",
                 static_cast<unsigned>(off), static_cast<int>(fr),
                 static_cast<unsigned>(br), static_cast<unsigned>(want));
      return false;
    }

    Xil_DCacheInvalidateRange(
        static_cast<UINTPTR>(static_cast<std::uintptr_t>(DDR_DEST) + off), br);

    if (std::memcmp(g_staging, dst + off, br) != 0) {
      // Find and report the first mismatching byte for diagnosis.
      for (UINT i = 0; i < br; ++i) {
        if (g_staging[i] != dst[off + i]) {
          xil_printf("MISMATCH at byte %u: sd=0x%02x ddr=0x%02x\r\n",
                     static_cast<unsigned>(off + i),
                     static_cast<unsigned>(g_staging[i]),
                     static_cast<unsigned>(dst[off + i]));
          break;
        }
      }
      return false;
    }
    off += br;
  }
  return true;
}

} // namespace

int main() {
  xil_printf("=== SD loader test ===\r\n");
  xil_printf("file=%s dst=0x%08x\r\n", TEST_FILE,
             static_cast<unsigned>(DDR_DEST));

  FATFS fs;
  FRESULT fr = f_mount(&fs, SD_DRIVE, 1); // 1 = mount now
  if (fr != FR_OK) {
    xil_printf("ERROR: f_mount failed: %d "
               "(SD MIO/clocks not init'd? card not FAT32?)\r\n",
               static_cast<int>(fr));
    return -1;
  }

  FIL fil;
  fr = f_open(&fil, TEST_FILE, FA_READ);
  if (fr != FR_OK) {
    xil_printf("ERROR: f_open(%s) failed: %d (file missing?)\r\n", TEST_FILE,
               static_cast<int>(fr));
    return -1;
  }
  xil_printf("opened %s, size=%u bytes\r\n", TEST_FILE,
             static_cast<unsigned>(f_size(&fil)));

  std::uint32_t checksum = 0;
  bool ok = false;
  std::uint32_t total = read_into_ddr(&fil, &checksum, &ok);
  if (!ok) {
    f_close(&fil);
    return -1;
  }

  // Flush the freshly written DDR region so DRAM holds the bytes before the
  // read-back pass invalidates and re-reads them.
  Xil_DCacheFlushRange(static_cast<UINTPTR>(DDR_DEST), total);

  xil_printf("read %u bytes into DDR, checksum=0x%08x\r\n",
             static_cast<unsigned>(total), static_cast<unsigned>(checksum));

  bool match = readback_compare(&fil, total);
  f_close(&fil);

  if (match) {
    xil_printf("READBACK OK (%u bytes)\r\n", static_cast<unsigned>(total));
    return 0;
  }
  xil_printf("READBACK MISMATCH\r\n");
  return -1;
}
