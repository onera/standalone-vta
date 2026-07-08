package vta.parsers

import vta.util.FileManager.{getConfigFile, readFile}

import scala.util.Try

object ConfigParser {

  /** Parse a config JSON from an explicit (absolute or cwd-relative) path,
    * without the `config/` directory resolution that [[parseConfigJson]]
    * applies. Lets tools outside the simulator (e.g. the baremetal host
    * generator) read an arbitrary `--config-json` while reusing the same
    * key/value parsing.
    */
  def parseConfigJsonAt(filePath: String): Try[Map[String, String]] =
    readFile(filePath, fromResources = false).map(parseConfig)

  /** Parse the simple one-key-per-line config JSON content into a string map.
    * Brace lines, comments, and blanks are dropped; each remaining `"KEY":
    * VALUE` line becomes `KEY -> VALUE` (quotes/commas/spaces removed).
    */
  def parseConfig(content: String): Map[String, String] =
    content
      .split("\n")
      .filterNot(line =>
        line.startsWith("//") || line.trim.isEmpty || line.contains("{") || line
          .contains("}")
      )
      .map { line =>
        val array = line.trim
          .replaceAll(" ", "")
          .replaceAll("\"", "")
          .replaceAll(",", "")
          .replaceAll("\n", "")
          .replaceAll("\r", "")
          .split(":")
        (array(0), array(1))
      }
      .toMap

  /** Reads a JSON file and puts the data in a Map
    * @param filePath
    *   the path to the JSON file
    * @param fromResources
    *   boolean that is true if the files are in a Resources folder, false
    *   otherwise
    * @return
    *   a Map with the parsed content from the file
    */
  def getConfigParametersFromFile(
    filePath: String,
    fromResources: Boolean
  ): Map[String, Int] = {
    (for {
      decodedJson <- parseConfigJson(filePath, fromResources)
    } yield {
      getConfigParametersFromMap(decodedJson)
    }).get
  }

  def getConfigParametersFromMap(parameters: Map[String, String]) = {
    val filteredJson = parameters -- Seq("TARGET", "HW_VER")
    val json = filteredJson.map { case (key, value) =>
      key -> math.pow(2, value.toInt).toInt
    }
    json
  }

  def parseConfigJson(
    filePath: String,
    fromResources: Boolean
  ): Try[Map[String, String]] = {
    val newFilePath = getConfigFile(filePath, fromResources)
    parseConfigJsonAt(newFilePath)
  }
}
