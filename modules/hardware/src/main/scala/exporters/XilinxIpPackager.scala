package vta.exporters

import os.Path

object XilinxIpPackager {

  /** Export a TCL script to be used for packaging the VTA shell in vivado IPI
    * flow
    *
    * @param target
    *   the path where the file will be written
    * @param vendor
    *   name of the vendor (default onera)
    * @param name
    *   name of the IP
    * @param version
    *   VTA version
    * @param topModule
    *   the top module name
    * @param part
    *   the targeted FPGA part
    * @param lib
    *   IP library (default: user)
    * @param description
    *   a quick description of the IP
    * @param displayName
    *   name of the IP as displayed in Vivado block design
    * @param nMemPorts
    *   number of AXI4 memory master ports the shell exposes: 1 for
    *   [[vta.shell.XilinxShell]], one per read client for
    *   [[vta.shell.XilinxSplitShell]]. Only used to tell the generated script
    *   how many AXI interfaces Vivado must infer, control port included.
    * @param config
    */
  def writeTclScript(
    target: Path,
    vendor: String,
    name: String,
    version: String,
    topModule: String,
    part: String = "",
    lib: String = "user",
    description: String =
      "Versatile Tensor Accelerator - Xilinx shell (AXI4-Lite ctrl + AXI4 DRAM)",
    displayName: String = "VTA",
    nMemPorts: Int = 1
  ) = {
    require(
      nMemPorts >= 1,
      s"[VTA] [XilinxIpPackager] nMemPorts must be >= 1, got $nMemPorts"
    )
    // Every memory master plus the single AXI4-Lite control slave.
    val expectedAxiCount = nMemPorts + 1

    val header =
      s"""|${"#" * 80}
          |# package_ip.tcl
          |# Packages VtaXilinxShell as a Vivado IP for use in IP Integrator.
          |#
          |# Usage (batch, no GUI):
          |#   vivado -mode batch -source package_ip.tcl
          |# Or with arguments:
          |#   vivado -mode batch -source package_ip.tcl \\
          |#          -tclargs --part ${part} --ip_root <ip_root>
          |#
          |# Result:
          |#   An IP-XACT package in <ip_root>/ containing component.xml and all SV
          |#   sources. Add <ip_root>/ to Vivado's IP repository paths, then
          |#   instantiate "${name}" from the IP Catalog in IP Integrator.
          |${"#" * 80}
          |""".stripMargin

    val configurableDefaults =
      s"""
         |# ${"-" * 78}
         |# Configurable defaults (override via -tclargs)
         |# ${"-" * 78}
         |set part    "${part}"   
         |set ip_root [file join [file dirname [file normalize [info script]]] \\
         |             ip_repo vta]
         |set ip_vendor  "${vendor}"
         |set ip_lib     "${lib}"
         |set ip_name    "${name}"
         |set ip_version "${version}"
         |set ip_module_top "${topModule}"
         |set ip_description "${description}"
         |set ip_display_name "${displayName}"
         |# AXI interfaces Vivado is expected to infer for this shell:
         |# ${nMemPorts} memory master(s) + 1 control slave.
         |set expected_axi_count ${expectedAxiCount}
      """.stripMargin

    val scriptResource = os.resource / "vivado" / "package_ip.tcl"
    // getClass.getClassLoader.getResource("vivado/package_ip.tcl").getFile()

    val content = os.read(scriptResource)
    val body = header + configurableDefaults + content

    os.write.over(target / "package_ip.tcl", body)
  }
}
