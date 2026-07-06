package vta.util

import org.scalatest.matchers.should.Matchers
import org.scalatest.flatspec.AnyFlatSpec
import vta.util.FileManager.getConfigFile
import vta.util.FileManager.getResourcePath
import vta.util.FileManager.getResourceAsFile




class FileManagerTest extends AnyFlatSpec with Matchers {
  "getConfig" should "correctly return the default config" in {
    val path = getConfigFile("vta_config.json")
    println(path)
  }

  "getConfig" should "correctly return the test default config" in {
    val path = getConfigFile("vta_config_test.json",true)
    println(path)
  }
}
