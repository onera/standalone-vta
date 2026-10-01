# xsdb script: put a run_nn_uart Vitis app on a Versal board over JTAG.
#
#   source <Vitis>/settings64.sh
#   xsdb modules/fpga/software/host/program_board_versal.tcl
#
# Reads BOARD_PDI/BOARD_ELF, exported by program_board_versal.sh.
#
# Why this is a separate script from program_board.tcl: Versal boots nothing
# like Zynq UltraScale+. There is no FSBL to run to XFsbl_Exit, no psu_init.tcl
# to source, and no standalone .bit to push - the PDI carries the PLM, the NoC
# and DDR configuration, the PL image and the PS setup, and the PLM applies all
# of it. Likewise there is no PS<->PL isolation removal step: on Versal that is
# part of what the PDI already did. So the ZynqMP sequence has no Versal
# analogue step-for-step, and forcing one script to serve both would leave the
# working ZynqMP path carrying dead branches.
#
# Sequence:
#   program the PDI on the device target (PLM configures NoC/DDR/PL/PS)
#   -> reset Cortex-A72 #0 -> download the app ELF -> continue

foreach v {BOARD_PDI BOARD_ELF} {
    if {![info exists ::env($v)]} { puts "ERROR: $v not set - run this via program_board_versal.sh"; exit 1 }
}
set PDI $::env(BOARD_PDI)
set APP $::env(BOARD_ELF)

# With more than one board on JTAG, "name =~ *Versal*" is ambiguous and
# `device program` refuses with "Multiple devices found". BOARD_JTAG_CABLE
# narrows the filter to one cable (match against jtag_cable_name, e.g. VCK190
# or VEK280). Left empty when only one Versal is attached.
set CABLE ""
if {[info exists ::env(BOARD_JTAG_CABLE)]} { set CABLE $::env(BOARD_JTAG_CABLE) }
proc tfilter {base} {
    global CABLE
    if {$CABLE eq ""} { return $base }
    return "$base && jtag_cable_name =~ \"*$CABLE*\""
}

foreach f [list $PDI $APP] {
    if {![file exists $f]} { puts "ERROR: missing $f"; exit 1 }
}

puts "=== connect ==="
connect

# The PDI is loaded through the PMC (Platform Management Controller), not through
# the `Versal xcvc1902` device node and not through a processor: the PMC is what
# runs the PLM that applies the image. Selecting the device node instead makes
# `device program` report "Multiple devices found" and list the PMC among the
# candidates, which is the symptom that identifies this.
puts "=== program PDI: $PDI ==="
if {[catch {
    eval targets -set -nocase -filter [list [tfilter {name =~ "*PMC*"}]]
} msg]} {
    puts "ERROR: no unique PMC target ($msg)"
    puts "  pass --jtag-cable <substring> (e.g. VCK190) to disambiguate."
    puts "  targets visible:"
    catch {targets}
    exit 1
}
# Reset the device before loading a PDI. Without this, programming a second PDI
# onto a board that has already booted one fails inside the live PLM with
# "PLM Error Major 0x302 Minor 0x4001" - the first PDI's PLM owns the
# configuration it is being asked to replace, and only a power cycle or this
# reset returns control. Harmless on a freshly powered board.
#
# The reset has to go to the *device node* ("Versal xcvc1902"), not the PMC:
# rst -por and rst -srst on the PMC both report success and leave programming
# still failing, while rst -system on the device node recovers it. That
# asymmetry is why the reset and the programming step select different targets.
puts "=== reset device before programming ==="
if {[catch {
    eval targets -set -nocase -filter [list [tfilter {name =~ "*Versal*"}]]
    rst -system
} msg]} {
    puts "  device reset: $msg (continuing - a freshly powered board needs none)"
}
after 15000

# Programming itself goes through the PMC, selected again here because the reset
# above moved the current target to the device node.
if {[catch {
    eval targets -set -nocase -filter [list [tfilter {name =~ "*PMC*"}]]
} msg]} {
    puts "ERROR: no unique PMC target after reset ($msg)"
    exit 1
}

if {[catch { device program $PDI } msg]} {
    puts "ERROR: device program failed: $msg"
    exit 1
}
# The PLM keeps working after `device program` returns - DDR training and PL
# configuration finish asynchronously. Downloading into DDR before it settles
# gives a silently corrupt image, so wait rather than race it.
after 5000

puts "=== download app: $APP ==="
if {[catch {
    eval targets -set -nocase -filter [list [tfilter {name =~ "*Cortex-A72*#0*"}]]
} msg]} {
    puts "ERROR: no unique Cortex-A72 #0 target ($msg)"
    puts "  pass --jtag-cable <substring> to disambiguate."
    puts "  targets visible:"
    catch {targets}
    exit 1
}
rst -processor
dow $APP

puts "=== continue ==="
con
after 3000
puts "=== app running - waits for a UART trigger (0x01); '_sd' loaders take ~90 s first ==="
exit
