`timescale 1ns/1ps
//*****************************************************************************************
// sim_top.sv - xsim wrapper for VTAPostSynthTb (behavioral control OR post-synth netlist).
//
// Drives clock + reset, snoops the DUT's io_dbgW AXI write-channel bundle into writes.log
// (one line "addr data strb last" per W beat - this is how OUT is captured for the
// strb-aware compare_out.py), and ends the run on one of:
//   DONE    - io_done  : all layers reached FNSH (success)
//   WEDGE   - io_error : the VtaHostDriver per-layer cycle watchdog fired (a layer did not
//             finish within perLayerTimeout); tune it with -Dvta.perLayerTimeout at emit
//             time so this fires in a bounded number of *sim cycles* (gate-level funcsim is
//             slow in wallclock)
//   TIMEOUT - sim-time backstop (a last resort if the design neither finishes nor errors)
//
// The DUT (VTAPostSynthTb) is behavioral SV in both legs; only VTAShell is swapped for its
// post-synth netlist (VTAShell_funcsim.v) by run_xsim.sh. io_dbgW already surfaces the OUT
// writes from inside VTAShell, so no hierarchical snoop into the netlist is needed. A small
// status set (compute state / done, VCR ctrl) is surfaced for liveness triage and printed
// on WEDGE/TIMEOUT.
//
// Plusargs / defines (all optional):
//   +WRITES=<path>     writes.log output path           (default "writes.log")
//   +TIMEOUT_NS=<n>    hard sim-time backstop in ns      (default 2_000_000_000)
//   `define RESET_CYCLES <n>   reset-high clocks         (default 20)
//   `define CLK_HALF_NS  <n>   half clock period in ns   (default 5  = 100 MHz)
//   `define LAYERIDX_W   <n>   width of io_layerIdx       (default 2  = up to 4 layers)
//                              run_xsim.sh sets this exactly from the layer count.
//*****************************************************************************************
module sim_top;
`ifndef CLK_HALF_NS
  `define CLK_HALF_NS 5
`endif
`ifndef RESET_CYCLES
  `define RESET_CYCLES 20
`endif
`ifndef LAYERIDX_W
  `define LAYERIDX_W 2
`endif

  reg clock = 1'b0;
  reg reset = 1'b1;
  always #(`CLK_HALF_NS) clock = ~clock;

  wire                    io_done;
  wire                    io_error;
  wire                    io_busy;
  wire [`LAYERIDX_W-1:0]  io_layerIdx;
  wire                    io_dbgW_valid;
  wire [31:0]             io_dbgW_addr;
  wire [63:0]             io_dbgW_data;
  wire [7:0]              io_dbgW_strb;
  wire                    io_dbgW_last;
  // Status probe set (XilinxDebugShell.debug): liveness triage only.
  wire [1:0]   dbg_computeState;
  wire         dbg_computeDone;
  wire [31:0]  dbg_vcrCtrl;

  VTAPostSynthTb dut (
    .clock        (clock),
    .reset        (reset),
    .io_done      (io_done),
    .io_error     (io_error),
    .io_busy      (io_busy),
    .io_layerIdx  (io_layerIdx),
    .io_dbgW_valid(io_dbgW_valid),
    .io_dbgW_addr (io_dbgW_addr),
    .io_dbgW_data (io_dbgW_data),
    .io_dbgW_strb (io_dbgW_strb),
    .io_dbgW_last (io_dbgW_last),
    .dbg_computeState (dbg_computeState),
    .dbg_computeDone  (dbg_computeDone),
    .dbg_vcrCtrl      (dbg_vcrCtrl)
  );

  // ---- run / OUT-capture state (declared before the task that uses them) ---------------
  integer fout;
  integer beats;
  integer cyc;
  reg [`LAYERIDX_W-1:0] prevLayer;

  task status_snap(input [127:0] tag);
    $display("STATUS %0s cyc=%0d cState=%0d cDone=%0d vcrCtrl=0x%08x",
             tag, cyc, dbg_computeState, dbg_computeDone, dbg_vcrCtrl);
  endtask

  reg [1023:0] writes_path;
  initial begin
    beats = 0; cyc = 0; prevLayer = 0;
    if (!$value$plusargs("WRITES=%s", writes_path)) writes_path = "writes.log";
    fout = $fopen(writes_path, "w");
  end
  always @(posedge clock) if (!reset) begin
    cyc = cyc + 1;
    if (io_dbgW_valid) begin
      $fwrite(fout, "%08x %016x %02x %0d\n",
              io_dbgW_addr, io_dbgW_data, io_dbgW_strb, io_dbgW_last);
      beats = beats + 1;
    end
    // A layerIdx increment means the just-finished layer asserted FNSH and the
    // driver advanced. This is the per-layer "finished" marker.
    if (io_layerIdx !== prevLayer) begin
      $display("SIM_TOP: LAYER %0d FINISHED -> %0d  @ cyc=%0d beats=%0d",
               prevLayer, io_layerIdx, cyc, beats);
      prevLayer = io_layerIdx;
    end
  end

  // ---- run control: DONE / WEDGE / TIMEOUT ---------------------------------------------
  // 64-bit (a 32-bit `integer` overflows for multi-second sim-time backstops, yielding a
  // negative #delay).
  time timeout_ns;
  initial begin
    if (!$value$plusargs("TIMEOUT_NS=%d", timeout_ns)) timeout_ns = 2000000000;
    repeat (`RESET_CYCLES) @(posedge clock);
    reset = 1'b0;
    fork
      begin : done_w
        @(posedge io_done);
        $display("SIM_TOP: DONE @ %0t  beats=%0d", $time, beats);
      end
      begin : wedge_w
        @(posedge io_error);
        $display("SIM_TOP: WEDGE (driver watchdog) layer=%0d  beats=%0d @ %0t",
                 io_layerIdx, beats, $time);
        status_snap("WEDGE");
      end
      begin : to_w
        #(timeout_ns);
        $display("SIM_TOP: TIMEOUT layer=%0d  beats=%0d @ %0t", io_layerIdx, beats, $time);
        status_snap("TIMEOUT");
      end
    join_any
    $fclose(fout);
    repeat (5) @(posedge clock);
    $finish;
  end
endmodule
