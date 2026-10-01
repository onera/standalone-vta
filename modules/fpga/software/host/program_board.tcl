# xsdb script: put a run_nn_uart Vitis app on the target board over JTAG.
#
#   source <Vitis>/settings64.sh
#   xsdb modules/fpga/software/host/program_board.tcl
#
# Reads BOARD_BIT/BOARD_ELF/BOARD_FSBL/BOARD_PSINIT, exported by program_board.sh.
#
# Sequence (mirrors the Vitis launch.json for a run_nn_uart app):
#   reset PS -> run the FSBL to XFsbl_Exit (psu_init + DDR training)
#   -> program the PL bitstream
#   -> remove PS<->PL isolation and de-assert the PL reset (without it the
#      accelerator hangs on its first instruction)
#   -> download the app ELF -> continue

foreach v {BOARD_BIT BOARD_FSBL BOARD_ELF BOARD_PSINIT} {
    if {![info exists ::env($v)]} { puts "ERROR: $v not set - run this via program_board.sh"; exit 1 }
}
set BIT    $::env(BOARD_BIT)
set FSBL   $::env(BOARD_FSBL)
set APP    $::env(BOARD_ELF)
set PSINIT $::env(BOARD_PSINIT)

foreach f [list $BIT $FSBL $APP $PSINIT] {
    if {![file exists $f]} { puts "ERROR: missing $f"; exit 1 }
}

puts "=== connect ==="
connect

puts "=== reset PS ==="
targets -set -nocase -filter {name =~ "*PSU*"}
rst -system
after 2000

puts "=== run FSBL on Cortex-A53 #0 (wait for XFsbl_Exit) ==="
targets -set -nocase -filter {name =~ "*Cortex-A53*#0*"}
rst -processor
dow $FSBL
if {[catch {
    bpadd -addr &XFsbl_Exit
    con -block -timeout 60
    bpremove -all
} msg]} {
    puts "  (XFsbl_Exit sync skipped: $msg) - fixed wait instead"
    # The core may still be running after the timed-out `con -block` (a bare
    # `con` then aborts with "Already running"), and the breakpoint may still
    # be set: tolerate both.
    catch {bpremove -all}
    catch {con}
    after 8000
    catch {stop}
}

puts "=== program PL: $BIT ==="
targets -set -nocase -filter {name =~ "*Cortex-A53*#0*"}
fpga -file $BIT
after 500

puts "=== PS<->PL isolation removal + PL reset de-assert ==="
source $PSINIT
if {[catch { psu_ps_pl_isolation_removal } m]} { puts "  isolation_removal: $m" }
if {[catch { psu_ps_pl_reset_config } m]}     { puts "  pl_reset_config: $m" }
after 500

puts "=== download app: $APP ==="
targets -set -nocase -filter {name =~ "*Cortex-A53*#0*"}
rst -processor
dow $APP

puts "=== continue ==="
con
after 3000
puts "=== app running ==="
exit
