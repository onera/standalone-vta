package fpga.host.models

/** A CPU-op parameter blob (currently the float weights / bias of a
  * convtranspose op): the ELF/asm section label, the absolute source `.bin`
  * path, its DDR load address, and byte size. These are read-only model
  * parameters loaded by the same static-load path as the VTA INSN/UOP/WGT/ACC
  * buffers, so the loader, asm, linker, and SD emitters all consume them.
  *
  * Allocated by [[fpga.host.transform.MemoryLayout.buildCpuParamAddrs]].
  */
final case class ExtraBlob(label: String, path: String, addr: Long, size: Long)
