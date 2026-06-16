#ifndef _VTA_SD_H_
#define _VTA_SD_H_
#include <cstdint>
namespace vta {

// One binary to stage from the SD card into DRAM. The generated
// nn_sd_manifest.h populates arrays of these (cf. how nn_ddr_map.h
// populates LayerDesc).
struct SdFile {
  const char *name; // filename at the SD card root, e.g. "instructions_L0.bin"
  std::uint32_t addr; // absolute DDR destination address
  std::uint32_t size; // expected byte size (0 = don't check)
};

// Mount the SD card (drive, e.g. "0:/") and copy each file into its DDR
// address, flushing the written range from cache so VTA (and CPU ops) see
// fresh data. Returns 0 on success, -1 on any error (printed over UART).
//
// Requires the xilffs (FatFs) BSP library and the SD MIO/clocks already
// initialised by ps7_init/psu_init. Defined only when NN_SD_LOADER is set.
int sd_load_files(const char *drive, const SdFile *files, unsigned n);

} // namespace vta
#endif
