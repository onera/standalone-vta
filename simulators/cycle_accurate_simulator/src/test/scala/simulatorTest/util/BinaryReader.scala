package simulatorTest.util

import java.io.{FileInputStream, IOException}
import scala.util.Try

object BinaryReader {

  // Open and read the binary file, write the data in an Array[Byte]
  //FIXME essayer d'utiliser Success/Failure
//  def readBinaryFile(filePath: String): Try[(Array[Byte], Int)] = {
//    Try {
//      val inputStreamFile = new FileInputStream(getClass.getClassLoader.getResource(filePath).getFile)
//      val fileSize = inputStreamFile.available()
//      val fileContent = new Array[Byte](fileSize)
//
//      inputStreamFile.read(fileContent)
//      inputStreamFile.close()
//      (fileContent, fileSize) // à modifier en fileContent
//    }
//  }

  /**
   * Open and read the binary file, write the data in an Array[Byte]
   * @param filePath the path of the resource file
   * @return the ...
   */
  def readBinaryFile(filePath: String): Array[Byte] = {
    try {
      val inputStreamFile = new FileInputStream(getClass.getClassLoader.getResource(filePath).getFile)
      val fileSize = inputStreamFile.available()
      val fileContent = new Array[Byte](fileSize)

      inputStreamFile.read(fileContent)
      inputStreamFile.close()
      fileContent

    } catch {
      case e: IOException => {
        println(s"Error while reading file : $e")
        Array.empty
      }
    }
  }

  // Print the Bytes in the binary file (before reversal) : ok
  def printMapLELE(filePath: String) = {
    val fileContent = readBinaryFile(filePath)
    // print en dec
    fileContent.foreach(octet => print(s"$octet, "))
    println("\n")

    // print en hex : ok
    fileContent.foreach { byte =>
      println(f"$byte%02x ")
    }
  }

  // Group the instructions in 16-Byte groups, reverse Little Endian for each instruction : ok
  def reverseLE(binaryData: Array[Byte]): Array[Array[Byte]] =
    for {
      inst <- binaryData.sliding(16, 16).toArray
    } yield {
      //println(s"Instruction : ${inst.mkString(" ")}")
      val r = inst.reverse
      //println(s"Instruction : ${r.mkString(" ")}")
      r
    }


  // Enumeration for data type
  //FIXME add parameters to values
  object DataType extends Enumeration {
    val INP, WGT, OUT, UOP, INSN, ACC = Value
  }

  import DataType._

  def toto(d: DataType.Value): Unit= d match {
    case INP => ???
    case WGT => ???
    case OUT => ???
    case UOP => ???
    case INSN => ???
    case ACC => ???
  }

  // Compute the logical addresses associated with each instruction in a Map : ok
  def computeAddresses(filePath: String): Map[BigInt, Array[BigInt]] = { // signature à modifier
    val groupedBinaryData = reverseLE(readBinaryFile(filePath))
    // Definition of Map
    val addresses = collection.mutable.Map[BigInt, Array[Byte]]()
    // Filling the Map
    for (i <- groupedBinaryData.indices) {
      addresses += (BigInt(i) -> groupedBinaryData(i))
    }
    // Values type conversion from Byte to BigInt
    val bigIntMap = addresses.map { case (key, byteValue) =>
      key -> byteValue.flatMap { byte => Some(BigInt(byte))
      }.toArray
    }.toMap
    bigIntMap
  }


  // Print the Map with the instructions encoded correctly
  def printMapLE(map: Map[BigInt, Array[BigInt]]) = {
    println("Content of the Map :")
    // print en dec
    map.foreach { case (key, values) =>
      println(s"Instruction index : $key")
      println(s"Values : ${values.mkString(", ")}")
      println("---")
    }
    // print en hex
//    map.foreach { case (key, values) =>
//      println(s"Logical address (Hex) : ${key.toInt & 0xFF}%02x")
//      println(s"Values (Hex) : ${values.map(_.toInt & 0xFF).map("%02x".format(_)).mkString(", ")}")
//    }
  }
}
