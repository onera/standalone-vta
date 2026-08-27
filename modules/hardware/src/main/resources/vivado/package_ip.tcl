# Parse optional -tclargs
foreach {key val} $argv {
    switch $key {
        --part    { set part    $val }
        --ip_root { set ip_root $val }
        --ip_name { set ip_name $val }
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
set tmp_proj [file join [file dirname $ip_root] .vivado_pkg_tmp]
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

# Associate ap_clk with every AXI bus interface Vivado inferred.
#
# The interfaces are discovered rather than named: the single-master shell
# infers one m_axi_gmem, while the split shell infers m_axi_gmem_0..N-1, and
# naming them explicitly would silently associate nothing the day the inferred
# names differ. $expected_axi_count (emitted by XilinxIpPackager) is the guard:
# a mismatch means inference did not produce the interfaces this shell was
# packaged for, which must fail the run rather than yield an IP whose clocks
# are unassociated.
set axi_bus_ifs [list]
foreach bif [ipx::get_bus_interfaces -of_objects [ipx::current_core]] {
    set bif_name [get_property NAME $bif]
    if {[string match "m_axi*" $bif_name] || [string match "s_axi*" $bif_name]} {
        lappend axi_bus_ifs $bif_name
    }
}

foreach bif_name $axi_bus_ifs {
    puts "Associating ap_clk with AXI interface: $bif_name"
    ipx::associate_bus_interfaces -busif $bif_name -clock ap_clk [ipx::current_core]
}

if {[llength $axi_bus_ifs] != $expected_axi_count} {
    error [concat "package_ip.tcl: expected $expected_axi_count AXI interface(s)" \
                  "for $ip_module_top but Vivado inferred [llength $axi_bus_ifs]:" \
                  "$axi_bus_ifs. The packaged IP would have unassociated clocks."]
}
# Set IPI design rule check, and ignore frequency
set_property ipi_drc {ignore_freq_hz true} [ipx::current_core]
# ---------------------------------------------------------------------------
# Step 5: Validate and save
# ---------------------------------------------------------------------------
set check_result [ipx::check_integrity [ipx::current_core]]
if {$check_result != 0} {
    puts "WARNING: ipx::check_integrity returned $check_result - review messages above."
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
