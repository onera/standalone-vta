#*****************************************************************************************
# synthesis.tcl - stage 4/5 of the VTA FPGA Vivado recipe: synthesis, implementation
# through bitstream, and XSA export.
#
# Runs as its own `vivado -mode batch -source ...` process: reopens the Vivado
# project written by create_project.tcl, so it works whether that project was left
# untouched or hand-edited/saved in the Vivado GUI in between.
#
# Usage (driven by BuildFpga.scala; not meant to be run by hand):
#   vivado -mode batch -source synthesis.tcl -tclargs <board_params.tcl>
#
# board_params.tcl (emitted by BuildFpga.scala from boards/<board>.json) must set:
#   board_name proj_dir out_dir jobs
# (see create_project.tcl for the full set of fields board_params.tcl carries; this
# stage only needs the four above, plus the project's saved `top` fileset property.)
#*****************************************************************************************

if {[llength $argv] < 1} {
  error "usage: vivado -mode batch -source synthesis.tcl -tclargs <board_params.tcl>"
}
set params_file [lindex $argv 0]
if {![file exists $params_file]} { error "board params file not found: $params_file" }
puts "INFO: sourcing board params: $params_file"
source $params_file

set xpr [file join $proj_dir $board_name "$board_name.xpr"]
if {![file exists $xpr]} {
  error "project not found: $xpr\n\
         Run the create-project stage first (BuildFpga without --skip-project)."
}
puts "INFO: opening project: $xpr"
open_project $xpr
set top_name [get_property top [current_fileset]]

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
set pdi [file join $impl_dir $top_name.pdi]
if {[file exists $pdi]} {
  file copy -force $pdi [file join $out_dir vta_$board_name.pdi]
}

open_run impl_1
report_timing_summary -warn_on_violation -file [file join $out_dir timing_summary.rpt]
report_utilization -file [file join $out_dir utilization.rpt]

set wns [get_property SLACK [get_timing_paths -delay_type max]]
puts "INFO: post-route worst-case setup slack (WNS) = $wns ns"
puts "INFO: synthesis complete -> $xsa"
