package vta.util

import scala.io.Source
import java.io.File
import java.io.FileWriter
import java.io.InputStream
import java.io.FileInputStream
import scala.util.Try


object FileManager {

  def getResourceAsFile(path: String) = {
    val resourceFile = new File(getClass.getClassLoader.getResource(path).toURI())
    if (resourceFile.isFile()){
      Some (resourceFile)
    } else None
  }

  def getResourcePath(path: String) = os.resource / path

 
  def getFile(path: String) = {
    val file = new File(path)
    if (file.isFile())
      Some(file)
    else None
  }


  def getFileOrResource(path: String,fromResources: Boolean= false) = if (fromResources){
    getResourceAsFile(path)
  } else {
    getFile(path)
  }
  def getSource(path: String,fromResources: Boolean = false) : Source = {
        if (fromResources) {
         Source.fromResource(path) 
        } else {
          Source.fromFile(path)
        }
      }

  def getFileOrResourceAsStream(path: String,fromResources: Boolean = false) = Try {
        if (fromResources) {
          getClass.getClassLoader.getResourceAsStream(path)
        } else {
          new FileInputStream(path)
        }
      }


  def getConfigFile(path: String,fromResources: Boolean = false) = if (!fromResources) {
        val hwRoot = sys.env.getOrElse("MILL_WORKSPACE_ROOT","")
        val projectRoot = new File(hwRoot,"../../../")
        val compilerOutputDir = new File(projectRoot, "config")
        val basePath = compilerOutputDir.getCanonicalPath
        s"$basePath/" + path
      } else {
        getClass.getClassLoader.getResource(path).getPath()
      }

  def getCompilerOutputFile(path: String,fromResources: Boolean = false) = if (!fromResources) {
        val hwRoot = sys.env.getOrElse("MILL_WORKSPACE_ROOT","")
        val projectRoot = new File(hwRoot,"../../../")
        val compilerOutputDir = new File(projectRoot, "compiler_output")
        val basePath = compilerOutputDir.getCanonicalPath
        s"$basePath/" + path
      } else {
        path
      }

  /** Reads the content of a text file and returns its content
    * @param filePath
    *   the path to the file
    * @param fromResources
    *   boolean that is true if the files are in a Resources folder, false
    *   otherwise
    * @return
    *   a String with the content of the file
    */
  def readFile(filePath: String, fromResources: Boolean): Try[String] = {
    Try{
      val file = getFileOrResource(filePath,fromResources).get
      val s = Source.fromFile(file)
      s.getLines().mkString("\n")
    }
  }
}
