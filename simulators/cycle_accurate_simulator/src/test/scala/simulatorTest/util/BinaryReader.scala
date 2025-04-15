package simulatorTest.util

import java.io.FileInputStream
import scala.util.{Failure, Success, Try}

object BinaryReader {

  /**
   * Definition of an Enumeration listing the data types. The attributes of each type are
   * its ID, the size of its vectors (in Bytes) and whether the data is to be reversed for
   * CHISEL encoding
   */
  object DataType extends Enumeration {
    private def samePrecision(x:Int): Map[Int,Int] = Map.empty.withDefaultValue(x)
    class DataTypeValue(val id: Int, val nbValues:Int, val precision: Map[Int,Int], val doReversal: Boolean) extends Value
    val INP: DataTypeValue = new DataTypeValue(0, 16, samePrecision(8), false)
    val WGT: DataTypeValue = new DataTypeValue(1, 256, samePrecision(8), false)
    val OUT: DataTypeValue = new DataTypeValue(2, 16, samePrecision(8), false)
    val UOP: DataTypeValue = new DataTypeValue(3, 3, Map(0 -> 11, 1 -> 11, 2 -> 10), true)
    val ACC: DataTypeValue = new DataTypeValue(4, 16, samePrecision(32), true)
    val INSN: DataTypeValue = new DataTypeValue(5, 1, samePrecision(128), true)
  }

  import DataType._

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
  def printMapLELE(filePath: String): Unit = {
    readBinaryFile(filePath) match {
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
    for {
      inst <- binaryData.grouped(sizeOfElement/8).toArray
    } yield {
      if (dataType.doReversal)
        inst.reverse
      else
        inst
    }
  }

  /**
   * Compute the logical addresses associated with each instruction in a Map
   * @param filePath the path to the resource file
   * @param dataType the type of data in the binary file
   * @param baseAddress base address of a data type
   * @return a Map(Address, Array) that associates the logical address of a vector with its values
   */
  def computeAddressesTry(filePath: String, dataType: DataTypeValue, baseAddress: String, isDRAM: Boolean): Try[Map[BigInt, Array[BigInt]]] = {
    val groupedBinaryData =
      readBinaryFile(filePath) match {
        case Success(fileContent) =>
            Success(reverseLE(fileContent, dataType))
        case Failure(exception) =>
          println(s"Error while grouping data (if reversal) : ${exception.getMessage}")
          Failure(exception)
      }

    val baseAddrBigInt = BigInt(baseAddress,16)

    //FIXME for each address should have dataType.nbElement
    // recompose the full value and then split according to precision
    // and adapt the computation of the address with isDRAM
    groupedBinaryData match {
      case Success(data) =>
        val result =
          for {
            (d,i) <- data.zipWithIndex
          } yield
            (BigInt(i) + baseAddrBigInt) -> d.map(x => BigInt(x))

        Success(result.toMap)
      case Failure(exception) =>
        println(s"Error while computing addresses : ${exception.getMessage}")
        Failure(exception)
    }
  }

  /**
   * Print the Map with the instructions encoded in a format CHISEL can read
   * @param map a Map that associates the logical addresses of a vector and its values
   */
  def printMapLE(map: Try[Map[BigInt, Array[BigInt]]], dataType: DataTypeValue): Unit = {
    println("Content of the Map :")
    map match {
      case Success(data) =>
        val toPrint = data.toSeq.sortBy(_._1)
        // Print in decimals for Instructions and UOPs
        if (dataType.id == UOP.id || dataType.id == INSN.id) {
          toPrint.foreach { case (key, values) =>
            println(s"Instruction index : $key")
            println(s"Values : ${values.mkString(", ")}")
            println("---")
          }
        }
        // Print in hexadecimals for matrix data
        else {
          toPrint.foreach { case (key, values) =>
            val hexKey = Integer.toHexString(key.toInt)
            println(s"Logical address (Hex) : ${"0" * (8 - hexKey.length)}$hexKey")
            println(s"Values (Hex) : ${values.map(_.toInt & 0xFF).map("%02x".format(_)).mkString(", ")}")
          }
        }
      case Failure(exception) =>
        println(s"Error while printing reversed file : ${exception.getMessage}")
    }
  }
}
