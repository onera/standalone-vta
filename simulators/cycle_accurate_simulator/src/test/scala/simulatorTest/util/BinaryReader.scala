package simulatorTest.util

import java.io.{FileInputStream, IOException}
import scala.util.{Try, Success, Failure}

object BinaryReader {
  //FIXME essayer d'utiliser Success/Failure
  //FIXME add parameters to values

  /**
   * Definition of an Enumeration listing the data types. The attributes of each type are
   * its ID, the size of its vectors (in Bytes) and whether the data is to be reversed for
   * CHISEL encoding
   */
  object DataType extends Enumeration {
    class DataTypeValue(val id: Int, val bytes: Int, val doReversal: Boolean) extends Value
    val INP: DataTypeValue = new DataTypeValue(0, 16, false)
    val WGT: DataTypeValue = new DataTypeValue(1, 256, false)
    val OUT: DataTypeValue = new DataTypeValue(2, 16, false)
    val UOP: DataTypeValue = new DataTypeValue(3, 4, true)
    val ACC: DataTypeValue = new DataTypeValue(4, 64, true)
    val INSN: DataTypeValue = new DataTypeValue(5, 16, true)
  }

  import DataType._

//  //exemple enum
//  def toto(d: DataType.Value): Unit= d match {
//    case INP => ???
//    case WGT => ???
//    case OUT => ???
//    case UOP => ???
//    case INSN => ???
//    case ACC => ???
//  }

  /**
   * Open and read the binary file, write the data in an Array[Byte]
   * @param filePath the path to the resource file
   * @return an Array[Byte] of all the bytes inside the file
   */
  def readBinaryFile(filePath: String): Try[Array[Byte]] = {
    Try {
      val inputStreamFile = new FileInputStream(getClass.getClassLoader.getResource(filePath).getFile)
      val fileSize = inputStreamFile.available()
      val fileContent = new Array[Byte](fileSize)

      inputStreamFile.read(fileContent)
      inputStreamFile.close()
      fileContent
    }
  }

  /**
   * Print the Bytes of the input binary file (before Little Endian reversal)
   * @param filePath the path to the resource file
   */
  def printMapLELE(filePath: String): Try[Unit] = {
    readBinaryFile(filePath) match {
      case Success(fileContent) =>
        // Print in decimals
        fileContent.foreach(octet => print(s"$octet, "))
        println("\n")
        //Print in hexadecimals
        fileContent.foreach(octet => println(f"$octet%02x "))
        println("\n")
        Success(())
      case Failure(exception) =>
        println(s"Error while printing non-reversed file : ${exception.getMessage}")
        Failure(exception)
    }
  }


  /**
   * Group the instructions in 16-Byte groups, reverse Little Endian for each instruction
   * @param binaryData an array containing the bytes extracted from the binary file
   * @param dataType the type of data in the binary file
   * @return an array containing the data grouped together according to its byte size
   */
  def reverseLE(binaryData: Array[Byte], dataType: DataTypeValue): Array[Array[Byte]] =
    for {
      inst <- binaryData.grouped(dataType.bytes).toArray
    } yield {
      //println(s"Instruction : ${inst.mkString(" ")}")
      val r = inst.reverse // pour ACC à modifier probablement
      //println(s"Instruction : ${r.mkString(" ")}")
      r
    }


  /**
   * Compute the logical addresses associated with each instruction in a Map
   * @param filePath the path to the resource file
   * @param dataType the type of data in the binary file
   * @param offset base address of a data type
   * @return a Map(Address, Array) that associates the logical address of a vector with its values
   */
//  def computeAddresses(filePath: String, dataType: DataTypeValue, offset: String): Map[BigInt, Array[BigInt]] = { // signature à modifier
//    val groupedBinaryData = if (dataType.doReversal) {
//      reverseLE(readBinaryFile(filePath), dataType)
//    }
//    else {
//      readBinaryFile(filePath).grouped(dataType.bytes).toArray
//    }
//    // Definition of Map
//    val addresses = collection.mutable.Map[BigInt, Array[Byte]]()
//
//    // Filling the Map
//    for (i <- groupedBinaryData.indices) {
//      addresses += ((BigInt(i) + java.lang.Integer.parseInt(offset, 16)) -> groupedBinaryData(i))
//    }
//    // Values type conversion from Byte to BigInt
//    val bigIntMap = addresses.map { case (key, byteValue) =>
//      key -> byteValue.flatMap { byte => Some(BigInt(byte))
//      }.toArray
//    }.toMap
//    bigIntMap
//  }

  def computeAddressesTry(filePath: String, dataType: DataTypeValue, offset: String): Try[Map[BigInt, Array[BigInt]]] = {
    val groupedBinaryData = if (dataType.doReversal) {
      readBinaryFile(filePath) match {
        case Success(fileContent) =>
          // Reverse and group the bytes according to data type
          Success(reverseLE(fileContent, dataType))
        case Failure(exception) =>
          println(s"Error while grouping data (if reversal) : ${exception.getMessage}")
          Failure(exception)
      }
    }
    else {
      readBinaryFile(filePath) match {
        case Success(fileContent) =>
          // Group the bytes according to data size
          Success(fileContent.grouped(dataType.bytes).toArray)
        case Failure(exception) =>
          println(s"Error while grouping data (no reversal) : ${exception.getMessage}")
          Failure(exception)
      }
    }
    // Definition of an empty Map
    val addresses = collection.mutable.Map[BigInt, Array[Byte]]()

    groupedBinaryData match {
      case Success(data) =>
        for (i <- data.indices) {
          // Filling the Map with the addresses in hexadecimals and its corresponding group of Bytes
          addresses += ((BigInt(i) + java.lang.Integer.parseInt(offset, 16)) -> data(i))
        }
        // Converting the bytes to BigInt
        val bigIntMap = addresses.map { case (key, byteValue) =>
            key -> byteValue.flatMap { byte => Some(BigInt(byte))
            }.toArray
          }.toMap
        Success(bigIntMap)
      case Failure(exception) =>
        println(s"Error while computing addresses : ${exception.getMessage}")
        Failure(exception)
    }
  }

  /**
   * Print the Map with the instructions encoded in a format CHISEL can read
   * @param map a Map that associates the logical addresses of a vector and its values
   */
  def printMapLE(map: Try[Map[BigInt, Array[BigInt]]], dataType: DataTypeValue): Try[Unit] = {
    println("Content of the Map :")
    map match {
      case Success(data) =>
        // Print in decimals for Instructions and UOPs
        if (dataType.id == 5 || dataType.id == 3) {
          data.foreach { case (key, values) =>
            println(s"Instruction index : $key")
            println(s"Values : ${values.mkString(", ")}")
            println("---")
          }
        }
        // Print in hexadecimals for matrix data
        else {
          data.foreach { case (key, values) =>
            val hexKey = Integer.toHexString(key.toInt)
            println(s"Logical address (Hex) : ${"0" * (8 - hexKey.length)}$hexKey")
            println(s"Values (Hex) : ${values.map(_.toInt & 0xFF).map("%02x".format(_)).mkString(", ")}")
          }
        }
        Success(())
      case Failure(exception) =>
        println(s"Error while printing reversed file : ${exception.getMessage}")
        Failure(exception)
    }
  }
}
