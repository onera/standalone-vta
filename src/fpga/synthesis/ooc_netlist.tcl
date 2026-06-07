#*****************************************************************************************
# ooc_netlist.tcl - out-of-context synth/impl of VTAShell -> gate-level netlists.
#
# Produces the netlists used by the post-synthesis / post-implementation simulation
# flow (sim_netlist.py):
#   mode=synth : write_verilog -mode funcsim  -> VTAShell_funcsim.v   (functional, no timing)
#   mode=impl  : + opt/place/route, write_verilog -mode timesim + write_sdf
#                -> VTAShell_timesim.v + VTAShell_timesim.sdf          (SDF-annotated)
#
# DUT = VTAShell (the sim shell, io_host AXI-Lite + io_mem AXI4). Synthesizing it OOC
# keeps the io_*/clock/reset port names, so both the functional simulator's DPI harness
# and the Chisel VTAPostSynthTb can drive the netlist by substituting VTAShell by name.
# It contains the same Core datapath the full FPGA build synthesizes.
#
# Usage (driven by sim_netlist.py; not meant to be run by hand):
#   vivado -mode batch -source ooc_netlist.tcl -tclargs <params.tcl>
#
# params.tcl (emitted by sim_netlist.py) sets:
#   part sv_dir top out_dir proj_dir clk_port clk_period_ns mode jobs
#*****************************************************************************************

if {[llength $argv] < 1} {
  error "usage: vivado -mode batch -source ooc_netlist.tcl -tclargs <params.tcl>"
}
set params_file [lindex $argv 0]
if {![file exists $params_file]} { error "params file not found: $params_file" }
source $params_file

file mkdir $out_dir
file mkdir $proj_dir
create_project ooc_$top [file join $proj_dir ooc] -part $part -force

# Read the emitted synthesizable SV (VTAShell + Core). The post-synth TB top modules
# instantiate VTAShell but are not in its cone; exclude them so read_verilog never trips
# on $readmemh / sim-only constructs, and synth elaborates a clean VTAShell.
set tb_only {VTAPostSynthTb.sv VtaHostDriver.sv MultiMemAxiClient.sv}
set svs {}
foreach f [glob -nocomplain [file join $sv_dir *.sv]] {
  if {[lsearch -exact $tb_only [file tail $f]] >= 0} { continue }
  lappend svs $f
}
if {[llength $svs] == 0} { error "no .sv found in $sv_dir" }
read_verilog -sv $svs
set_property top $top [current_fileset]
update_compile_order -fileset sources_1

# ---------------------------------------------------------------------------
# Out-of-context synthesis -> functional (post-synth) netlist
# ---------------------------------------------------------------------------
# Optional extra synth_design args (e.g. "-max_bram 0" to force distributed RAM
# for the block-16-vs-block-4 RAM-style A/B experiment). Default empty.
if {![info exists synth_extra]} { set synth_extra {} }
synth_design -top $top -mode out_of_context -part $part {*}$synth_extra
write_checkpoint -force [file join $out_dir post_synth.dcp]
report_utilization -force -file [file join $out_dir ooc_synth_utilization.rpt]
write_verilog -mode funcsim -force [file join $out_dir ${top}_funcsim.v]
puts "INFO: wrote funcsim netlist: [file join $out_dir ${top}_funcsim.v]"

# ---------------------------------------------------------------------------
# Implementation -> timing (post-impl) netlist + SDF
# ---------------------------------------------------------------------------
if {$mode eq "impl"} {
  create_clock -name vta_clk -period $clk_period_ns [get_ports $clk_port]
  opt_design
  place_design
  route_design
  write_checkpoint -force [file join $out_dir post_route.dcp]
  report_timing_summary -warn_on_violation -file [file join $out_dir ooc_route_timing.rpt]
  set wns [get_property SLACK [get_timing_paths -delay_type max]]
  puts "INFO: OOC post-route WNS = $wns ns @ ${clk_period_ns}ns"
  write_verilog -mode timesim -sdf_anno true -force [file join $out_dir ${top}_timesim.v]
  write_sdf -force [file join $out_dir ${top}_timesim.sdf]
  puts "INFO: wrote timesim netlist + SDF: [file join $out_dir ${top}_timesim.v]"
}

puts "INFO: ooc_netlist done (mode=$mode, top=$top)"
exit
