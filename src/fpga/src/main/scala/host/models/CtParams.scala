package fpga.host.models

/** DDR addresses for a single ConvTranspose layer's parameter blobs. Allocated
  * by [[fpga.host.transform.MemoryLayout.buildCpuParamAddrs]].
  */
case class CtParams(wgtAddr: Long, biasAddr: Long, hasBias: Boolean)
