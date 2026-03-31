package vta.util

import vta.util.config.Parameters
import os.Path
import scala.io.Source
import java.io.File

object XilinxIpFlow {

  def exportIpPackageTclScript(
      target: Path,
      vendor: String,
      name: String,
      version: String,
      topModule: String,
      part: String = "xc7z020clg400-1" // PYNQ
  ) = {
    val header = s"""
|##############################################################################
|# package_ip.tcl
|# Packages XilinxShell as a Vivado IP for use in IP Integrator.
|#
|# Usage (batch, no GUI):
|#   vivado -mode batch -source package_ip.tcl
|# Or with arguments:
|#   vivado -mode batch -source package_ip.tcl \\
|#          -tclargs --part ${part} --ip_root ./ip_repo/vta_shell
|#""".stripMargin +
      """
|# Result:
|#   An IP-XACT package in ${ip_root}/ containing component.xml and all SV
|#   sources. Add \${ip_root}/.. to Vivado's IP repository paths, then
""".stripMargin +
      s"""
|#   instantiate "${name}" from the IP Catalog in IP Integrator.
|##############################################################################
""".stripMargin
    val configurableDefaults = s"""
|# ---------------------------------------------------------------------------
|# Configurable defaults (override via -tclargs)
|# ---------------------------------------------------------------------------
|set part    "${part}"   
|set ip_root [file join [file dirname [file normalize [info script]]] \\
|             ip_repo vta_shell]
|set ip_vendor  "${vendor}"
|set ip_lib     "user"
|set ip_name    "${name}"
|set ip_version "${version}"
|set ip_module_top "${topModule}"
""".stripMargin

    val scriptResource =
      os.Path(
        getClass.getClassLoader.getResource("vivado/package_ip.tcl").getFile()
      )

    val content = os.read(scriptResource)
    val body = header + configurableDefaults + content

    os.write.over(target / "package_ip.tcl", body)
  }
}
