package vta.models

import vta.parsers.ConfigParser.getConfigParametersFromFile

/** Definition of an Enumeration listing the data types. The attributes of each
  * type are its ID, the size of its vectors (in Bytes) and its bit-length
  */
object DataType extends Enumeration {
  private def samePrecision(x: Int): Map[Int, Int] =
    Map.empty.withDefaultValue(x)

  class DataTypeValue(
    val id: Int,
    val nbValues: Int,
    val precision: Map[Int, Int]
  ) extends Value

  val configFileName =
    System.getProperty("vta.config.file", "vta_config.json")
  val useResources =
    System.getProperty("vta.config.fromResources", "false").toBoolean

  val params =
    getConfigParametersFromFile(configFileName, fromResources = useResources)

  val INP: DataTypeValue = new DataTypeValue(
    0,
    params("LOG_BLOCK"),
    samePrecision(params("LOG_INP_WIDTH"))
  )
  val WGT: DataTypeValue = new DataTypeValue(
    1,
    params("LOG_BLOCK") * params("LOG_BLOCK"),
    samePrecision(params("LOG_WGT_WIDTH"))
  )
  val OUT: DataTypeValue = new DataTypeValue(
    2,
    params("LOG_BLOCK"),
    samePrecision(params("LOG_INP_WIDTH"))
  )
  val UOP: DataTypeValue =
    new DataTypeValue(3, 3, Map(0 -> 11, 1 -> 11, 2 -> 10))
  val ACC: DataTypeValue = new DataTypeValue(
    4,
    params("LOG_BLOCK"),
    samePrecision(params("LOG_ACC_WIDTH"))
  )
  val INSN: DataTypeValue = new DataTypeValue(5, 1, samePrecision(128))

  private val _nameOf: Map[DataTypeValue, String] = Map(
    INP -> "INP",
    WGT -> "WGT",
    ACC -> "ACC",
    OUT -> "OUT",
    UOP -> "UOP",
    INSN -> "INSN"
  )

  /** Canonical ordered list of buffer-type names. Order matches
    * CompilerOutput.bufferTypes (INP,WGT,ACC,OUT,UOP,INSN).
    */
  val names: Seq[String] = Seq("INP", "WGT", "ACC", "OUT", "UOP", "INSN")

  private val _fromName: Map[String, DataTypeValue] =
    _nameOf.map { case (k, v) => v -> k }

  implicit class datatypeHasName(dataType: DataTypeValue) {
    def name = _nameOf(dataType)
  }
  def fromName(name: String) = _fromName(name)
}
