package vta.models

/** Utility case class for defining mock memories for simulation
  *
  * @param name
  *   the name of the memory
  * @param path
  *   initialization file
  * @param baseAddress
  *   base address of the memory
  * @param initialSize
  *   number of data (before resizing in 64 bits)
  * @param words64
  *   number of 64bits words
  * @param logfile
  *   an optional logfile to store the memory (written during simulation)
  */
case class MemoryConfig(
    name: String,
    path: String,
    baseAddress: Int,
    numberOfData: Int,
    words64: Int,
    logging: Boolean = false
)
