// vta_sd.cc - runtime SD-card -> DRAM loader for the VTA baremetal software.
//
// Reads the compiler's .bin streams from a FAT32 SD card into their DDR
// addresses at boot, replacing the host/JTAG-tied tcl/elf loaders. The file ->
// address map is the generated nn_sd_manifest.h (compiled into the ELF).
//
// Guarded by NN_SD_LOADER: UserConfig.cmake globs every driver/src/*.cc into
// every app, but ff.h only exists when the xilffs BSP library is enabled (sd
// builds only). For tcl/elf builds this whole unit preprocesses away.
#ifdef NN_SD_LOADER

#include "../include/vta_sd.h"
#include <cstdint>

extern "C" {
#include "ff.h"
#include "xil_cache.h"
#include "xil_printf.h"
}

namespace {

constexpr unsigned kChunkBytes = 64u * 1024u;

// Build "<drive><name>" into out, e.g. "0:/" + "weight_L0.bin".
void join_path(char *out, unsigned cap, const char *drive, const char *name) {
  unsigned i = 0;
  for (const char *p = drive; *p && i + 1 < cap; ++p)
    out[i++] = *p;
  for (const char *p = name; *p && i + 1 < cap; ++p)
    out[i++] = *p;
  out[i] = '\0';
}

// Read an already-open file into DDR at addr, in chunks, then flush the range.
// Returns the byte count, or -1 on error.
long read_file_to_ddr(FIL *fil, std::uint32_t addr) {
  auto *dst =
      reinterpret_cast<std::uint8_t *>(static_cast<std::uintptr_t>(addr));
  std::uint32_t total = 0;
  for (;;) {
    UINT br = 0;
    FRESULT fr = f_read(fil, dst + total, kChunkBytes, &br);
    if (fr != FR_OK) {
      xil_printf("  f_read failed at +%u: %d\r\n", static_cast<unsigned>(total),
                 static_cast<int>(fr));
      return -1;
    }
    total += br;
    if (br < kChunkBytes)
      break; // short read == EOF
  }
  // Flush so the SD-DMA-written bytes are coherent for VTA's AXI reads;
  // run_nn() also flushes the static buffers before launch, so this is the
  // early gate.
  Xil_DCacheFlushRange(static_cast<UINTPTR>(addr), total);
  return static_cast<long>(total);
}

} // namespace

namespace vta {

int sd_load_files(const char *drive, const SdFile *files, unsigned n) {
  static FATFS fs;
  FRESULT fr = f_mount(&fs, drive, 1); // 1 = mount now
  if (fr != FR_OK) {
    xil_printf("sd_load: f_mount(%s) failed: %d "
               "(SD MIO/clocks not init'd? card not FAT32?)\r\n",
               drive, static_cast<int>(fr));
    return -1;
  }

  for (unsigned i = 0; i < n; ++i) {
    const SdFile &f = files[i];
    char path[96];
    join_path(path, sizeof(path), drive, f.name);

    FIL fil;
    fr = f_open(&fil, path, FA_READ);
    if (fr != FR_OK) {
      xil_printf("sd_load: f_open(%s) failed: %d (file missing?)\r\n", path,
                 static_cast<int>(fr));
      return -1;
    }
    long got = read_file_to_ddr(&fil, f.addr);
    f_close(&fil);
    if (got < 0)
      return -1;

    if (f.size != 0 && static_cast<std::uint32_t>(got) != f.size) {
      xil_printf("sd_load: %s size mismatch: got %u expected %u\r\n", path,
                 static_cast<unsigned>(got), static_cast<unsigned>(f.size));
      return -1;
    }
    xil_printf("sd_load: %s -> 0x%08x (%u bytes)\r\n", path,
               static_cast<unsigned>(f.addr), static_cast<unsigned>(got));
  }
  return 0;
}

} // namespace vta

#endif // NN_SD_LOADER
