# Parse optional -tclargs
foreach {key val} $argv {
    switch $key {
        --part    { set part    $val }
        --ip_root { set ip_root $val }
    }
}

set script_dir [file dirname [file normalize [info script]]]

# ---------------------------------------------------------------------------
# Helper: read filelist.f, skip verification/ files
# ---------------------------------------------------------------------------
proc read_filelist {base_dir filelist_path} {
    set fh [open $filelist_path r]
    set sources {}
    while {[gets $fh line] >= 0} {
        set line [string trim $line]
        if {$line eq "" || [string match "verification/*" $line]} { continue }
        lappend sources [file join $base_dir $line]
    }
    close $fh
    return $sources
}

# ---------------------------------------------------------------------------
# Step 1: Create a temporary in-memory project
# ---------------------------------------------------------------------------
set tmp_proj [file join $script_dir .vivado_pkg_tmp]
file mkdir $tmp_proj

create_project -force vta_pkg_tmp \
    [file join $tmp_proj vta_pkg_tmp] \
    -part $part

# set_property target_language SystemVerilog [current_project]
# set_property simulator_language Mixed       [current_project]

# ---------------------------------------------------------------------------
# Step 2: Add all RTL sources
# ---------------------------------------------------------------------------
set src_files [read_filelist $script_dir \
               [file join $script_dir filelist.f]]

foreach f $src_files {
    if {![file exists $f]} {
        puts "WARNING: source not found, skipping: $f"
        continue
    }
}
add_files -norecurse $src_files
set_property top $ip_module_top [current_fileset]
update_compile_order -fileset sources_1

# ---------------------------------------------------------------------------
# Step 3: Package the IP
#   -import_files  → copies SV sources into the IP directory (self-contained)
#   -set_current false → we open the core manually after
# ---------------------------------------------------------------------------
file mkdir $ip_root

ipx::package_project \
    -root_dir     $ip_root \
    -vendor       $ip_vendor \
    -library      $ip_lib \
    -taxonomy     /UserIP \
    -import_files \
    -set_current  false

# ---------------------------------------------------------------------------
# Step 4: Open core and refine metadata + interface associations
# ---------------------------------------------------------------------------
ipx::open_core [file join $ip_root component.xml]

set_property vendor              $ip_vendor   [ipx::current_core]
set_property library             $ip_lib      [ipx::current_core]
set_property name                $ip_name     [ipx::current_core]
set_property version             $ip_version  [ipx::current_core]
set_property display_name        $ip_display_name  [ipx::current_core]
set_property description         $ip_description [ipx::current_core]
set_property vendor_display_name "VTA"        [ipx::current_core]

# Associate clock and reset to both AXI bus interfaces.
ipx::associate_bus_interfaces -busif m_axi_gmem -clock ap_clk [ipx::current_core]
ipx::associate_bus_interfaces -busif s_axi_control -clock ap_clk [ipx::current_core]
# Set IPI design rule check, and ignore frequency
set_property ipi_drc {ignore_freq_hz true} [ipx::current_core]
# ---------------------------------------------------------------------------
# Step 5: Validate and save
# ---------------------------------------------------------------------------
set check_result [ipx::check_integrity [ipx::current_core]]
if {$check_result != 0} {
    puts "WARNING: ipx::check_integrity returned $check_result — review messages above."
}
ipx::save_core [ipx::current_core]

# ---------------------------------------------------------------------------
# Step 6: Clean up temporary project
# ---------------------------------------------------------------------------
close_project
file delete -force $tmp_proj

# ---------------------------------------------------------------------------
puts ""
puts "================================================================"
puts " IP packaged successfully!"
puts "  Location : $ip_root"
puts "  Top      : $ip_module_top"
puts "  Part     : $part"
puts ""
puts " To use in a new project:"
puts "   set_property ip_repo_paths {[file dirname $ip_root]} \[current_project\]"
puts "   update_ip_catalog"
puts "   create_bd_cell -type ip -vlnv $ip_vendor:$ip_lib:$ip_name:$ip_version vta_0"
puts "================================================================"
