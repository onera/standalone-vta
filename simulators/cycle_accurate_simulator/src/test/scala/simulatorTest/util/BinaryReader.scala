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
    if (dataType.id != ACC.id)
      for {
        inst <- binaryData.grouped(sizeOfElement / 8).toArray
      } yield {
        if (dataType.doReversal)
          inst.reverse
        else
          inst
      }
    else {
      val groupedACC = {
        for {
          inst <- binaryData.grouped(4).toArray
        } yield {
          inst.reverse
        }
      }.flatten.grouped(64).toArray
      groupedACC
    }
  }


  /**
   * Compute the logical addresses associated with each instruction in a Map
   * @param filePath the path to the resource file
   * @param dataType the type of data in the binary file
   * @param baseAddress base address of a data type
   * @return a Map(Address, Array) that associates the logical address of a vector with its values
   */
  def computeAddresses(filePath: String, dataType: DataTypeValue, baseAddress: String, isDRAM: Boolean): Try[Map[BigInt, Array[BigInt]]] = {
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
        // Array containing all the Bytes of the binary file after reversal
        val ungroupedData =
          for {
            arr <- data
            byte <- arr
          } yield {
            byte
          }
        // Converting all the Bytes into bits, ok pour ACC ? 8 ou 32 ? je crois ok car 1 byte = 8 bits
        val arrayGroupBit =
          for {
            byte <- ungroupedData
          } yield {
            //println(String.format("%8s", java.lang.Integer.toBinaryString(byte & 0xFF)).replace(' ', '0'))
            //"0" * (8 - byte.toBinaryString.length) + byte.toBinaryString
            String.format("%8s", java.lang.Integer.toBinaryString(byte & 0xFF)).replace(' ', '0')
          }
        // nb of bits in an element (32 bits for 1 UOP...)
        val sizeOfElement =
          (for {
            i <- 0 until dataType.nbValues
            s = dataType.precision(i)
          } yield
            s).sum
        // ["0","1",...]
        // Séparation individuelle des bits
        val arrayBit = arrayGroupBit.flatMap(_.toList.map(_.toString)).grouped(sizeOfElement).toArray
        def groupByElemSize(arr: Array[String], index: Int): Array[String] = {
          if (index < dataType.nbValues)
            Array(arr.take(dataType.precision(index)).mkString) ++ groupByElemSize(arr.drop(dataType.precision(index)), index + 1)
          else
            arr
        }
        // [ ["11 bits", "11 bits", "10 bits"], [...], ... ]
        val groupedArrayBit =
          for {
            elem <- arrayBit
          } yield {
            //println(elem.mkString("Array(", ", ", ")"))
            //println(groupByElemSize(elem, 0).mkString("Array(", ", ", ")"))
            groupByElemSize(elem, 0)
          } // ok
        val groupedByElemSizeBI = groupedArrayBit.map(_.map(BigInt(_, 2)).map {bigInt => if (bigInt >= 128 && dataType.id != INSN.id) bigInt - 256 else bigInt})
        // [ (address, [11 bits, 11 bits, 10 bits]), (...), ... ]
        val result = {
          val resultMap = groupedByElemSizeBI.zipWithIndex
          for {
            (d, i) <- resultMap
          } yield {
            if (!isDRAM) { // Logical address for data types INP, WGT, OUT
              //println(d(0).toString(2))
              (BigInt(i) + baseAddrBigInt) -> d
            } else { // Physical address if data type is UOP or ACC
              (baseAddrBigInt + BigInt(sizeOfElement/8 * i)) -> d
            }
          }
        }
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
  def printMapLE(map: Map[BigInt, Array[BigInt]], dataType: DataTypeValue): Unit = {
    println("Content of the Map :")
    val toPrint = map.toSeq.sortBy(_._1)
    // Print in decimals for instructions
    if (dataType.id == INSN.id) {
      toPrint.foreach { case (key, values) =>
        println(s"Instruction index : $key")
        println(s"Values : ${values.mkString(", ")}")
      }
    }
    // Print in hexadecimals for other types of data
    else {
      toPrint.foreach { case (key, values) =>
        val hexKey = Integer.toHexString(key.toInt)
        println(s"Logical address (Hex) : ${"0" * (8 - hexKey.length)}$hexKey")
        //println(s"Values (Hex) : ${values.map(_.toInt & 0xFF).map("%02x".format(_)).mkString(", ")}")
        println(s"Values (Bits) : ${values.map(_.toInt & 0xFF).map("%8s".format(_).replace(' ', '0')).mkString(", ")}")
      }
    }
  }
}
