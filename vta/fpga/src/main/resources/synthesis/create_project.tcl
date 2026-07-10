#*****************************************************************************************
# build_fpga.tcl - generic, board-agnostic Vivado batch recipe for the VTA FPGA flow.
#
# Replaces the 919-line GUI-exported vta_zcu104.tcl with a fixed ~150-line recipe that
# is fully parameterized by a generated board_params.tcl. It builds the block design
# (PS + VTA IP + SmartConnect + reset), assigns addresses, runs synthesis and
# implementation through write_bitstream, and exports an XSA (with bitstream embedded).
#
# It wires the design by *stable* interface/port names and the VTA IP VLNV, so it does
# not rot when the RTL interface or config changes - unlike a frozen net snapshot.
#
# Usage (driven by build_fpga.py; not meant to be run by hand):
#   vivado -mode batch -source build_fpga.tcl -tclargs <board_params.tcl>
#
# board_params.tcl (emitted by build_fpga.py from boards/<board>.json) must set:
#   board_name part board_part ps_ip ps_cell ps_preset_rule ps_preset_config
#   pl_clock_mhz vta_cell vta_vlnv ip_repo out_dir proj_dir jobs
#   ps_config            - flat {KEY VALUE ...} list of CONFIG.PSU__* deltas
#   port_*               - vta_dram_master vta_ctrl_slave vta_clk vta_resetn
#                          ps_dram_slave ps_ctrl_master ps_clk ps_resetn
#   ps_clk_aclks         - list of PS aclk pins to drive with pl_clk
#   addresses            - list of {space seg offset range}
#   address_excludes     - list of {space seg}
#*****************************************************************************************

if {[llength $argv] < 1} {
  error "usage: vivado -mode batch -source build_fpga.tcl -tclargs <board_params.tcl>"
}
set params_file [lindex $argv 0]
if {![file exists $params_file]} { error "board params file not found: $params_file" }
puts "INFO: sourcing board params: $params_file"
source $params_file

# ---------------------------------------------------------------------------
# 1. Project
# ---------------------------------------------------------------------------
file mkdir $proj_dir
create_project $board_name [file join $proj_dir $board_name] -part $part -force
# Optional: point at a board-files repository (e.g. a downloaded/xhub board store)
# for boards not shipped with Vivado.
if {[info exists board_repo] && $board_repo ne ""} {
  set_property board_part_repo_paths [list $board_repo] [current_project]
}
if {[info exists board_part] && $board_part ne ""} {
  set_property board_part $board_part [current_project]
}

set_property ip_repo_paths [list $ip_repo] [current_fileset]
update_ip_catalog -rebuild

if {[llength [get_ipdefs -all $vta_vlnv]] == 0} {
  error "VTA IP '$vta_vlnv' not found in ip_repo '$ip_repo'.\n\
         Run the IP-packaging stage first (build_fpga.py does this automatically)."
}

# ---------------------------------------------------------------------------
# 2. Block design
# ---------------------------------------------------------------------------
set bd block_design
create_bd_design $bd

# --- Processing system: instantiate, apply the board preset (if defined), then our deltas ---
set ps [create_bd_cell -type ip -vlnv $ps_ip $ps_cell]
if {$ps_preset_rule ne "" && $ps_preset_config ne ""} {
  apply_bd_automation -rule $ps_preset_rule -config $ps_preset_config $ps
}
set ps_props {}
foreach {k v} $ps_config { lappend ps_props CONFIG.$k $v }
# PL clock frequency: single source of truth (pl_clock_mhz); the property name is
# PS-family-specific (ZynqMP vs Zynq-7000), so it comes from the board JSON.
if {$pl_clock_property ne ""} {
  lappend ps_props CONFIG.$pl_clock_property $pl_clock_mhz
}
if {[llength $ps_props] > 0} { set_property -dict $ps_props $ps }

# --- VTA IP (by VLNV - survives RTL/config changes) ---
set vta [create_bd_cell -type ip -vlnv $vta_vlnv $vta_cell]

if {[info exists is_versal] && $is_versal} {
  # --- Versal-specific Block Design ---

  # 1. Create external interface ports for LPDDR4 memory
  set ch0_port [ create_bd_intf_port -mode Master -vlnv xilinx.com:interface:lpddr4_rtl:1.0 $versal_ch0 ]
  set ch1_port [ create_bd_intf_port -mode Master -vlnv xilinx.com:interface:lpddr4_rtl:1.0 $versal_ch1 ]
  set lpddr4_clk [ create_bd_intf_port -mode Slave -vlnv xilinx.com:interface:diff_clock_rtl:1.0 $versal_clk ]
  set_property -dict [ list CONFIG.FREQ_HZ {200000000} ] $lpddr4_clk

  # 2. Instantiate and configure AXI NoC
  set noc [create_bd_cell -type ip -vlnv xilinx.com:ip:axi_noc:1.1 axi_noc_0]
  set noc_props [list \
    CONFIG.CH0_LPDDR4_0_BOARD_INTERFACE $versal_ch0 \
    CONFIG.CH1_LPDDR4_0_BOARD_INTERFACE $versal_ch1 \
    CONFIG.NUM_CLKS {7} \
    CONFIG.NUM_MC {1} \
    CONFIG.NUM_MCP {4} \
    CONFIG.NUM_MI {0} \
    CONFIG.NUM_SI {7} \
    CONFIG.sys_clk0_BOARD_INTERFACE $versal_clk \
  ]
  foreach {k v} $noc_config { lappend noc_props CONFIG.$k $v }
  set_property -dict $noc_props $noc

  # Configure NoC ports
  set_property -dict [ list \
    CONFIG.REGION {0} \
    CONFIG.CONNECTIONS {MC_3 {read_bw {100} write_bw {100} read_avg_burst {4} write_avg_burst {4} initial_boot {true} }} \
    CONFIG.NOC_PARAMS {} \
    CONFIG.CATEGORY {ps_cci} \
  ] [get_bd_intf_pins axi_noc_0/S00_AXI]

  set_property -dict [ list \
    CONFIG.REGION {0} \
    CONFIG.CONNECTIONS {MC_2 {read_bw {100} write_bw {100} read_avg_burst {4} write_avg_burst {4} initial_boot {true} }} \
    CONFIG.NOC_PARAMS {} \
    CONFIG.CATEGORY {ps_cci} \
  ] [get_bd_intf_pins axi_noc_0/S01_AXI]

  set_property -dict [ list \
    CONFIG.REGION {0} \
    CONFIG.CONNECTIONS {MC_0 {read_bw {100} write_bw {100} read_avg_burst {4} write_avg_burst {4} initial_boot {true} }} \
    CONFIG.NOC_PARAMS {} \
    CONFIG.CATEGORY {ps_cci} \
  ] [get_bd_intf_pins axi_noc_0/S02_AXI]

  set_property -dict [ list \
    CONFIG.REGION {0} \
    CONFIG.CONNECTIONS {MC_1 {read_bw {100} write_bw {100} read_avg_burst {4} write_avg_burst {4} initial_boot {true} }} \
    CONFIG.NOC_PARAMS {} \
    CONFIG.CATEGORY {ps_cci} \
  ] [get_bd_intf_pins axi_noc_0/S03_AXI]

  set_property -dict [ list \
    CONFIG.REGION {0} \
    CONFIG.CONNECTIONS {MC_3 {read_bw {100} write_bw {100} read_avg_burst {4} write_avg_burst {4} initial_boot {true} }} \
    CONFIG.NOC_PARAMS {} \
    CONFIG.CATEGORY {ps_rpu} \
  ] [get_bd_intf_pins axi_noc_0/S04_AXI]

  set_property -dict [ list \
    CONFIG.REGION {0} \
    CONFIG.CONNECTIONS {MC_2 {read_bw {100} write_bw {100} read_avg_burst {4} write_avg_burst {4} initial_boot {true} }} \
    CONFIG.NOC_PARAMS {} \
    CONFIG.CATEGORY {ps_pmc} \
  ] [get_bd_intf_pins axi_noc_0/S05_AXI]

  set_property -dict [ list \
    CONFIG.CONNECTIONS {MC_0 {read_bw {500} write_bw {500} read_avg_burst {4} write_avg_burst {4} }} \
    CONFIG.NOC_PARAMS {} \
    CONFIG.CATEGORY {pl} \
  ] [get_bd_intf_pins axi_noc_0/S06_AXI]

  set_property -dict [ list CONFIG.ASSOCIATED_BUSIF {S00_AXI} ] [get_bd_pins axi_noc_0/aclk0]
  set_property -dict [ list CONFIG.ASSOCIATED_BUSIF {S01_AXI} ] [get_bd_pins axi_noc_0/aclk1]
  set_property -dict [ list CONFIG.ASSOCIATED_BUSIF {S02_AXI} ] [get_bd_pins axi_noc_0/aclk2]
  set_property -dict [ list CONFIG.ASSOCIATED_BUSIF {S03_AXI} ] [get_bd_pins axi_noc_0/aclk3]
  set_property -dict [ list CONFIG.ASSOCIATED_BUSIF {S04_AXI} ] [get_bd_pins axi_noc_0/aclk4]
  set_property -dict [ list CONFIG.ASSOCIATED_BUSIF {S05_AXI} ] [get_bd_pins axi_noc_0/aclk5]
  set_property -dict [ list CONFIG.ASSOCIATED_BUSIF {S06_AXI} ] [get_bd_pins axi_noc_0/aclk6]

  # 3. Instantiate SmartConnect (1 SI / 1 MI)
  set smc [create_bd_cell -type ip -vlnv xilinx.com:ip:smartconnect:1.0 axi_smc]
  set_property -dict {CONFIG.NUM_SI 1 CONFIG.NUM_MI 1} $smc

  # Instantiate SmartConnect for VTA DRAM data path (1 SI / 1 MI) to prevent AXI read interleaving
  set dram_smc [create_bd_cell -type ip -vlnv xilinx.com:ip:smartconnect:1.0 vta_dram_smc]
  set_property -dict {CONFIG.NUM_SI 1 CONFIG.NUM_MI 1} $dram_smc

  # 4. Instantiate proc_sys_reset
  set rst [create_bd_cell -type ip -vlnv xilinx.com:ip:proc_sys_reset:5.0 proc_sys_reset_0]

  # 5. Interface connections
  # Connect VTA DRAM master (m_axi_gmem) to DRAM SmartConnect S00_AXI
  connect_bd_intf_net [get_bd_intf_pins $vta_cell/$port_vta_dram_master] [get_bd_intf_pins vta_dram_smc/S00_AXI]
  # Connect DRAM SmartConnect M00_AXI to NoC S06_AXI
  connect_bd_intf_net [get_bd_intf_pins vta_dram_smc/M00_AXI] [get_bd_intf_pins axi_noc_0/S06_AXI]
  # Connect NoC channels to external memory interface ports
  connect_bd_intf_net [get_bd_intf_ports $versal_ch0] [get_bd_intf_pins axi_noc_0/CH0_LPDDR4_0]
  connect_bd_intf_net [get_bd_intf_ports $versal_ch1] [get_bd_intf_pins axi_noc_0/CH1_LPDDR4_0]
  # Connect external clock to NoC system clock
  connect_bd_intf_net [get_bd_intf_ports $versal_clk] [get_bd_intf_pins axi_noc_0/sys_clk0]
  # Connect SmartConnect to VTA control slave
  connect_bd_intf_net [get_bd_intf_pins axi_smc/M00_AXI] [get_bd_intf_pins $vta_cell/$port_vta_ctrl_slave]
  # Connect CIPS master AXI FPD to SmartConnect S00
  connect_bd_intf_net [get_bd_intf_pins $ps_cell/$port_ps_ctrl_master] [get_bd_intf_pins axi_smc/S00_AXI]

  # Connect internal CIPS memory ports to NoC S00-S05
  connect_bd_intf_net [get_bd_intf_pins $ps_cell/FPD_CCI_NOC_0] [get_bd_intf_pins axi_noc_0/S00_AXI]
  connect_bd_intf_net [get_bd_intf_pins $ps_cell/FPD_CCI_NOC_1] [get_bd_intf_pins axi_noc_0/S01_AXI]
  connect_bd_intf_net [get_bd_intf_pins $ps_cell/FPD_CCI_NOC_2] [get_bd_intf_pins axi_noc_0/S02_AXI]
  connect_bd_intf_net [get_bd_intf_pins $ps_cell/FPD_CCI_NOC_3] [get_bd_intf_pins axi_noc_0/S03_AXI]
  connect_bd_intf_net [get_bd_intf_pins $ps_cell/LPD_AXI_NOC_0] [get_bd_intf_pins axi_noc_0/S04_AXI]
  connect_bd_intf_net [get_bd_intf_pins $ps_cell/PMC_NOC_AXI_0] [get_bd_intf_pins axi_noc_0/S05_AXI]

  # 6. Clocks and Reset Net connections
  connect_bd_net [get_bd_pins proc_sys_reset_0/peripheral_aresetn] \
    [get_bd_pins $vta_cell/$port_vta_resetn] [get_bd_pins axi_smc/aresetn] [get_bd_pins vta_dram_smc/aresetn]

  connect_bd_net [get_bd_pins $ps_cell/fpd_cci_noc_axi0_clk] [get_bd_pins axi_noc_0/aclk0]
  connect_bd_net [get_bd_pins $ps_cell/fpd_cci_noc_axi1_clk] [get_bd_pins axi_noc_0/aclk1]
  connect_bd_net [get_bd_pins $ps_cell/fpd_cci_noc_axi2_clk] [get_bd_pins axi_noc_0/aclk2]
  connect_bd_net [get_bd_pins $ps_cell/fpd_cci_noc_axi3_clk] [get_bd_pins axi_noc_0/aclk3]
  connect_bd_net [get_bd_pins $ps_cell/lpd_axi_noc_clk] [get_bd_pins axi_noc_0/aclk4]
  connect_bd_net [get_bd_pins $ps_cell/pmc_axi_noc_axi0_clk] [get_bd_pins axi_noc_0/aclk5]

  connect_bd_net [get_bd_pins $ps_cell/$port_ps_clk] \
    [get_bd_pins $vta_cell/$port_vta_clk] \
    [get_bd_pins axi_noc_0/aclk6] \
    [get_bd_pins proc_sys_reset_0/slowest_sync_clk] \
    [get_bd_pins axi_smc/aclk] \
    [get_bd_pins vta_dram_smc/aclk] \
    [get_bd_pins $ps_cell/m_axi_fpd_aclk]

  connect_bd_net [get_bd_pins $ps_cell/$port_ps_resetn] [get_bd_pins proc_sys_reset_0/ext_reset_in]

} else {
  # --- Original ZynqMP / Zynq-7000 recipe ---

  # --- AXI SmartConnect (2 SI / 2 MI) + synchronized reset ---
  set smc [create_bd_cell -type ip -vlnv xilinx.com:ip:smartconnect:1.0 axi_smc]
  set_property -dict {CONFIG.NUM_SI 2 CONFIG.NUM_MI 2} $smc
  set rst [create_bd_cell -type ip -vlnv xilinx.com:ip:proc_sys_reset:5.0 proc_sys_reset_0]

  # --- Interface connections (topology is identical for ZynqMP and Zynq-7000) ---
  #   VTA DRAM master -> SmC S00 ; SmC M00 -> VTA ctrl slave
  #   SmC M01 -> PS DRAM slave   ; PS ctrl master -> SmC S01
  connect_bd_intf_net [get_bd_intf_pins $vta_cell/$port_vta_dram_master] [get_bd_intf_pins axi_smc/S00_AXI]
  connect_bd_intf_net [get_bd_intf_pins axi_smc/M00_AXI]                  [get_bd_intf_pins $vta_cell/$port_vta_ctrl_slave]
  connect_bd_intf_net [get_bd_intf_pins axi_smc/M01_AXI]                  [get_bd_intf_pins $ps_cell/$port_ps_dram_slave]
  connect_bd_intf_net [get_bd_intf_pins $ps_cell/$port_ps_ctrl_master]    [get_bd_intf_pins axi_smc/S01_AXI]

  # --- Clock fan-out: single PL clock drives VTA, SmC, reset, and the PS AXI aclks ---
  set clk_src [get_bd_pins $ps_cell/$port_ps_clk]
  set clk_sinks [list \
    $vta_cell/$port_vta_clk \
    axi_smc/aclk \
    proc_sys_reset_0/slowest_sync_clk]
  foreach a $ps_clk_aclks { lappend clk_sinks $ps_cell/$a }
  set clk_pins {}
  foreach s $clk_sinks { lappend clk_pins [get_bd_pins $s] }
  connect_bd_net $clk_src {*}$clk_pins

  # --- Reset: PS pl_resetn -> proc_sys_reset ; peripheral_aresetn -> VTA + SmC ---
  connect_bd_net [get_bd_pins $ps_cell/$port_ps_resetn] [get_bd_pins proc_sys_reset_0/ext_reset_in]
  connect_bd_net [get_bd_pins proc_sys_reset_0/peripheral_aresetn] \
    [get_bd_pins $vta_cell/$port_vta_resetn] [get_bd_pins axi_smc/aresetn]
}

# --- Address map (explicit for reproducibility) ---
# Resolve a segment by its literal IP-XACT path, falling back to "the single
# segment under this interface pin" when the leaf name differs across IP/tool
# versions (e.g. s_axi_control/reg0 vs a differently-named reg space).
proc resolve_seg {seg} {
  set s [get_bd_addr_segs -quiet $seg]
  if {[llength $s] == 0} {
    set parts [split $seg /]
    if {[llength $parts] >= 2} {
      set intf [join [lrange $parts 0 end-1] /]
      set s [get_bd_addr_segs -quiet -of_objects [get_bd_intf_pins -quiet $intf]]
    }
  }
  if {[llength $s] == 0} { error "could not resolve address segment: $seg" }
  return [lindex $s 0]
}

foreach a $addresses {
  lassign $a space seg offset range
  assign_bd_address -offset $offset -range $range \
    -target_address_space [get_bd_addr_spaces $space] [resolve_seg $seg] -force
}
foreach e $address_excludes {
  lassign $e space seg
  catch { exclude_bd_addr_seg \
    -target_address_space [get_bd_addr_spaces $space] [resolve_seg $seg] }
}

validate_bd_design
save_bd_design

# ---------------------------------------------------------------------------
# 3. HDL wrapper + top
# ---------------------------------------------------------------------------
set wrapper [make_wrapper -fileset sources_1 -files [get_files -norecurse $bd.bd] -top]
add_files -norecurse -fileset sources_1 $wrapper
set top_name [file rootname [file tail $wrapper]]
set_property top $top_name [current_fileset]
generate_target all [get_files $bd.bd]
update_compile_order -fileset sources_1
