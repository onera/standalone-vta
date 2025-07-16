package util

import vta.core
import vta.core.CoreParams

import java.io.{File, FileInputStream, InputStream}
import scala.collection.convert.ImplicitConversions.`map AsJavaMap`
import scala.language.postfixOps
import scala.math.pow
import scala.util.{Failure, Success, Try}

object BinaryReader {

  /**
   * Definition of an Enumeration listing the data types. The attributes of each type are
   * its ID, the size of its vectors (in Bytes) and whether the data is to be reversed for
   * CHISEL encoding
   */
  object DataType extends Enumeration {
    private def samePrecision(x: Int): Map[Int, Int] = Map.empty.withDefaultValue(x)

    class DataTypeValue(val id: Int, val nbValues: Int, val precision: Map[Int, Int]) extends Value

    val params = computeJSONFile("vta_config.json", fromResources = false)

    val INP: DataTypeValue = new DataTypeValue(0, params("LOG_BLOCK"), samePrecision(params("LOG_INP_WIDTH")))
    val WGT: DataTypeValue = new DataTypeValue(1, params("LOG_BLOCK") * params("LOG_BLOCK"), samePrecision(params("LOG_WGT_WIDTH")))
    val OUT: DataTypeValue = new DataTypeValue(2, params("LOG_BLOCK"), samePrecision(params("LOG_INP_WIDTH")))
    val UOP: DataTypeValue = new DataTypeValue(3, 3, Map(0 -> 11, 1 -> 11, 2 -> 10))
    val ACC: DataTypeValue = new DataTypeValue(4, params("LOG_BLOCK"), samePrecision(params("LOG_ACC_WIDTH")))
    val INSN: DataTypeValue = new DataTypeValue(5, 1, samePrecision(128))
  }

  import DataType._

  /**
   * Open and read the binary file, write the data in an Array[Byte]
   * @param filePath the path to the resource file
   * @param fromResources boolean that is true if the files are in a Resources folder, false otherwise
   * @return an Array[Byte] of all the bytes inside the file
   */
  def readBinaryFile(filePath: String, fromResources: Boolean): Try[Array[Byte]] = {
    Try {
      val inputStream: InputStream = {
        if (fromResources) {
          getClass.getClassLoader.getResourceAsStream(filePath)
        }
        else {
          new FileInputStream(filePath)
        }
      }
      val fileSize = inputStream.available()
      val fileContent = new Array[Byte](fileSize)

      inputStream.read(fileContent)
      inputStream.close()
      fileContent
    }
  }

  /**
   * Print the Bytes of the input binary file (before Little Endian reversal)
   * @param filePath the path to the resource file
   */
  def printBytes(filePath: String): Unit = {
    readBinaryFile(filePath, fromResources = true) match {
      case Success(fileContent) =>
        // Print in decimals
        fileContent.foreach(octet => print(s"$octet, "))
        println("\n")
        //Print in hexadecimals
        fileContent.foreach(octet => println(f"$octet%02x "))
        println("\n")
      case Failure(exception) =>
        println(s"Error while printing non-reversed file : ${exception.getMessage}")
    }
  }


  /**
   * Group the instructions in 16-Byte groups, reverse Little Endian for each instruction
   * @param binaryData an array containing the bytes extracted from the binary file
   * @param dataType the type of data in the binary file
   * @return an array containing the data grouped together according to its byte size
   */
  def reverseLE(binaryData: Array[Byte], dataType: DataTypeValue): Array[Array[Byte]] = {
    val sizeOfElement =
      (for {
        i <- 0 until dataType.nbValues
        s = dataType.precision(i)
      } yield
        s).sum
    if (dataType.id == UOP.id || dataType.id == INSN.id) {
      for {
        inst <- binaryData.grouped(sizeOfElement / 8).toArray
      } yield { inst.reverse }
    }
    else if (dataType.precision(0) > 8) {
      for {
        inst <- binaryData.grouped(dataType.precision(0) / 8).toArray // 4 pour acc
      } yield {
        inst.reverse
      }
    }.flatten.grouped(sizeOfElement).toArray // Size of 1 ACC vector = 4 Bytes * 16 = 64 Bytes
    else {
      for {
        inst <- binaryData.grouped(sizeOfElement / 8).toArray
      } yield inst
    }
//    if (dataType.id != ACC.id)
//      for {
//        inst <- binaryData.grouped(sizeOfElement / 8).toArray
//      } yield {
//        if (dataType.doReversal)
//          inst.reverse
//        else
//          inst
//      }
//    else { // For ACC, data size is 32 bits instead of 8
//      {
//        for {
//          inst <- binaryData.grouped(4).toArray
//        } yield {
//          inst.reverse
//        }
//      }.flatten.grouped(64).toArray // Size of 1 ACC vector = 4 Bytes * 16 = 64 Bytes
//    }
  }

  /**
   * Reads the content of a CSV or JSON file and returns it
   * @param filePath the path to the file
   * @param fromResources boolean that is true if the files are in a Resources folder, false otherwise
   * @return a String with the content of the file
   */
  def readFile(filePath: String, fromResources: Boolean): Try[String] = {
    Try {
      val inputStream: InputStream = {
        if (fromResources) {
          getClass.getClassLoader.getResourceAsStream(filePath)
        }
        else {
          new FileInputStream(filePath)
        }
      }
      val fileContent = scala.io.Source.fromInputStream(inputStream, "UTF-8").mkString
      inputStream.close()
      fileContent
    }
  }

  /**
   * Reads a JSON file and puts the data in a Map
   * @param filePath the path to the JSON file
   * @param fromResources boolean that is true if the files are in a Resources folder, false otherwise
   * @return a Map with the parsed content from the file
   */
  def computeJSONFile(filePath: String, fromResources: Boolean): Map[String, Int] = {
    val newFilePath =
      if (!fromResources) {
        val projectRoot = new File("../../../")
        val compilerOutputDir = new File(projectRoot, "config")
        val basePath = compilerOutputDir.getCanonicalPath
        s"$basePath/" + filePath
      }
      else {
        filePath
      }
    val content = readFile(newFilePath, fromResources)
    content match {
      case Success(data) =>
        val decodedJson: Map[String, String] = {
          data.split("\n").filterNot(line => line.startsWith("//") || line.trim.isEmpty || line.contains("{") || line.contains("}")).map { line =>
            val array = line.trim
              .replaceAll(" ", "")
              .replaceAll("\"", "")
              .replaceAll(",", "")
              .replaceAll("\n", "")
              .replaceAll("\r", "")
              .split(":")
            (array(0), array(1))
          }
        }.toMap
        val filteredJson = decodedJson -- Seq("TARGET", "HW_VER")
        val json = filteredJson.map { case (key, value) => key -> pow(2, value.toInt).toInt }
        json
      case Failure(exception) =>
        println(s"Error while reading JSON file : ${exception.getMessage}")
        Map.empty
    }
  }

  /**
   * Reads the base memory addresses of the data and UOP inside a .csv file and returns a Map that associates the data type and its base address
   * @param filePath the path to the CSV file or file name if not in a resource folder
   * @param fromResources boolean that is true if the files are in a Resources folder, false otherwise
   * @return a Map[String, String] of the data type and its base address
   */
  def computeCSVFile(filePath: String, fromResources: Boolean, isBaseAddr: Boolean = true): Map[String, String] = {
    val newFilePath =
      if (!fromResources) {
        val projectRoot = new File("../../../")
        val compilerOutputDir = new File(projectRoot, "compiler_output")
        val basePath = compilerOutputDir.getCanonicalPath
        s"$basePath/" + filePath
      }
      else {
        filePath
      }
    val fileContent = readFile(newFilePath, fromResources)
    fileContent match {
      case Success(data) =>
        val baseAddr =
          data.split("\n").filterNot(line => line.startsWith("//") || line.trim.isEmpty).map { line =>
            val array = line.split(",")
            (array(0), array(1).trim
              .replaceAll("\n", "")
              .replaceAll("\r", "")
              .replaceAll("0x", "0000"))
          // Raises an error if there is a duplicate of a key in the CSV file
          }.foldLeft(Map.empty[String, String]) { (acc, pair) =>
            if (acc.containsKey(pair._1)) {
              throw new Exception(s"Duplicated key : ${pair._1}")
            } else {
              acc + pair
            }
          }.toMap
        // Remove the following lines if you load INP, WGT, OUT from DRAM
        val updatedBaseAddr = {
          if (isBaseAddr) {
            if (baseAddr.size <= 5) {
              baseAddr.updated("inp", "00000000").updated("wgt", "00000000").updated("out", "00000000")
            }
            else {
              (0 until 5).foldLeft(baseAddr) { case (acc, i) =>
                acc.updated(s"inp$i", "00000000")
                  .updated(s"wgt$i", "00000000")
                  .updated("out", "00000000")
              }
            }
          }
          else { baseAddr }
        }
        updatedBaseAddr
      case Failure(exception) =>
        println(s"Error while reading CSV file : ${exception.getMessage}")
        Map.empty
    }
  }

  /**
   * Compute the logical addresses associated with each instruction in a Map
   * @param filePath the path to the resource file or file name if not in a resource folder
   * @param dataType the type of data in the binary file
   * @param baseAddress base address of a data type
   * @param fromResources boolean that is true if the files are in a Resources folder, false otherwise
   * @return a Map(Address, Array) that associates the logical address of a vector with its values
   */
  def computeAddresses(filePath: String, dataType: DataTypeValue, baseAddress: String, isDRAM: Boolean, fromResources: Boolean): Try[Map[BigInt, Array[BigInt]]] = {
    val newFilePath =
      if (!fromResources) { // if binary files are located in /compiler_output and not a resource folder
        val projectRoot = new File("../../../")
        val compilerOutputDir = new File(projectRoot, "compiler_output")
        val basePath = compilerOutputDir.getCanonicalPath
        s"$basePath/" + filePath
      }
      else { // if files are located in a resource folder
        filePath
      }
    val groupedBinaryData =
      readBinaryFile(newFilePath, fromResources) match {
        case Success(fileContent) =>
          Success(reverseLE(fileContent, dataType)) // Bytes are extracted (and reversed depending on data type) from binary file
        case Failure(exception) =>
          println(s"Error while grouping data (if reversal) : ${exception.getMessage}")
          Failure(exception)
      }
    val baseAddrBigInt = BigInt(baseAddress,16) // Value of base address in BigInt
    groupedBinaryData match {
      case Success(data) =>
        val flattenedBits = // Flattened array containing all the bits of the binary file after LE reversal
          for {
            byte <- data.flatten
          } yield {
            String.format("%8s", java.lang.Integer.toBinaryString(byte & 0xFF)).replace(' ', '0')
          }
        // Number of bits in 1 element (32 bits for 1 UOP...)
        val sizeOfElement =
          (for {
            i <- 0 until dataType.nbValues
            s = dataType.precision(i)
          } yield
            s).sum
        // An array containing all the individual bits in groups of the size of the element (e.g. 1 INP int8 = 8 * 16 bits)
        val groupedBits = flattenedBits.flatMap(_.toList.map(_.toString)).grouped(sizeOfElement).toArray
        // Returns an array with nbValues groups of size precision
        val reversePrecision = Map(0 -> 10, 1 -> 11, 2 -> 11) // For UOP reversal
        def groupByElemSize(arr: Array[String], index: Int): Array[String] = {
          if (index < dataType.nbValues) {
            if (dataType.id == UOP.id)
              Array(arr.take(reversePrecision(index)).mkString) ++ groupByElemSize(arr.drop(reversePrecision(index)), index + 1)
            else
              Array(arr.take(dataType.precision(index)).mkString) ++ groupByElemSize(arr.drop(dataType.precision(index)), index + 1)
          } else
            arr
        }
        // An array of arrays containing nbValues groups of size bit-length (precision) (e.g. 16 arrays containing 16 8-bit strings for an INP block)
        // [ ["11 bits", "11 bits", "10 bits"], [...], ... ] for UOP
        val vectorsBits = {
          for {
            elem <- groupedBits
          } yield {
            groupByElemSize(elem, 0)
          }
        }
        // Additional reversal step for UOP
        val correctedVectorsBits =
          vectorsBits.map(elem => if (dataType.id == UOP.id) elem.reverse else elem)
        // Converts the bits to signed Int8
        def convertToInt8Signed(hexArray: Array[String]): Array[BigInt] = {
          hexArray.map { hex =>
            val bitLength = hex.length
            require(bitLength == 8 || bitLength == 16 || bitLength == 32, s"Binary length should be 8, 16 or 32-bit but is $bitLength")

            val last8Bits =
              if (bitLength <= 8) hex
              else hex.takeRight(8)

            val decimal = Integer.parseInt(last8Bits, 2)
            if (decimal >= 128) {
              BigInt((decimal - 256).toByte)
            } else {
              BigInt(decimal.toByte)
            }
          }
        }
        val convertedArray = {
          if (dataType.id == UOP.id || dataType.id == INSN.id) {
            correctedVectorsBits.map(_.map(BigInt(_, 2)))
          }
          else {
            correctedVectorsBits.map(convertToInt8Signed)
          }
        }
        // [ (address, [11 bits, 11 bits, 10 bits]), (...), ... ]
        // Assigns an address to each element
        val map = {
          for {
            (d, i) <- convertedArray.zipWithIndex
          } yield {
            if (!isDRAM) { // Logical address for data types INP, WGT, OUT, INSN
              (BigInt(i) + baseAddrBigInt) -> d
            } else { // Physical address if data type is UOP or ACC
              (baseAddrBigInt + BigInt(sizeOfElement/8 * i)) -> d
            }
          }
        }.toMap
        val result = {
          if (map.size % 2 != 0 && dataType.id == UOP.id) { // If the number of UOPs is odd, add an empty one to the map
            map + (baseAddrBigInt + BigInt(4 * map.size) -> Array(0, 0, 0).map(BigInt(_)))
          }
          else {
            map
          }
        }
        Success(result)
      case Failure(exception) =>
        println(s"Error while computing addresses : ${exception.getMessage}")
        Failure(exception)
    }
  }

  /**
   * Print the addresses and values of a Map with the data encoded in a format CHISEL can read
   * @param map a Map that associates the addresses of a vector and its values
   */
  def printMap(map: Map[BigInt, Array[BigInt]], dataType: DataTypeValue): Unit = {
    println("Content of the Map :")
    val toPrint = map.toSeq.sortBy(_._1)
    // Print in decimals for instructions
    if (dataType.id == INSN.id) {
      toPrint.foreach { case (key, values) =>
        println(s"Instruction index : $key")
        println(s"Values : ${values.mkString(", ")}")
      }
    }
    // Print the hexadecimal addresses for other types of data
    else {
      toPrint.foreach { case (key, values) =>
        val hexKey = Integer.toHexString(key.toInt)
        println(s"Logical address (Hex) : ${"0" * (8 - hexKey.length)}$hexKey")
        println(s"Values : ${values.mkString(", ")}")
      }
    }
  }
}
