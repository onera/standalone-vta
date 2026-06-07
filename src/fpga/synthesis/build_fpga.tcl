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

# --- Processing system: instantiate, apply the board preset, then our deltas ---
set ps [create_bd_cell -type ip -vlnv $ps_ip $ps_cell]
apply_bd_automation -rule $ps_preset_rule -config $ps_preset_config $ps
set ps_props {}
foreach {k v} $ps_config { lappend ps_props CONFIG.$k $v }
# PL clock frequency: single source of truth (pl_clock_mhz); the property name is
# PS-family-specific (ZynqMP vs Zynq-7000), so it comes from the board JSON.
lappend ps_props CONFIG.$pl_clock_property $pl_clock_mhz
if {[llength $ps_props] > 0} { set_property -dict $ps_props $ps }

# --- VTA IP (by VLNV - survives RTL/config changes) ---
set vta [create_bd_cell -type ip -vlnv $vta_vlnv $vta_cell]

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

# ---------------------------------------------------------------------------
# 4. Synthesis + implementation through bitstream
# ---------------------------------------------------------------------------
launch_runs impl_1 -to_step write_bitstream -jobs $jobs
wait_on_run impl_1
if {[get_property PROGRESS [get_runs impl_1]] ne "100%"} {
  error "impl_1 did not finish (PROGRESS=[get_property PROGRESS [get_runs impl_1]]).\n\
         See logs under [file join $proj_dir $board_name]."
}

# ---------------------------------------------------------------------------
# 5. Export XSA (with bitstream) + copy bit / reports
# ---------------------------------------------------------------------------
file mkdir $out_dir
set xsa [file join $out_dir vta_$board_name.xsa]
write_hw_platform -fixed -include_bit -force $xsa
puts "INFO: wrote hardware platform: $xsa"

set impl_dir [get_property DIRECTORY [get_runs impl_1]]
set bit [file join $impl_dir $top_name.bit]
if {[file exists $bit]} {
  file copy -force $bit [file join $out_dir vta_$board_name.bit]
}

open_run impl_1
report_timing_summary -warn_on_violation -file [file join $out_dir timing_summary.rpt]
report_utilization -file [file join $out_dir utilization.rpt]

set wns [get_property SLACK [get_timing_paths -delay_type max]]
puts "INFO: post-route worst-case setup slack (WNS) = $wns ns"
puts "INFO: synthesis complete -> $xsa"
