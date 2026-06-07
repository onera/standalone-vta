`timescale 1ns/1ps
//*****************************************************************************************
// sim_top.sv - xsim wrapper for VTAPostSynthTb (behavioral control OR post-synth netlist).
//
// Drives clock + reset, snoops the DUT's io_dbgW AXI write-channel bundle into writes.log
// (one line "addr data strb last" per W beat - this is how OUT is captured for the
// strb-aware compare_out.py), and ends the run on one of:
//   DONE    - io_done  : all layers reached FNSH (success)
//   WEDGE   - io_error : the VtaHostDriver per-layer cycle watchdog fired (a hung layer);
//             tune the watchdog with -Dvta.perLayerTimeout at emit time so this fires in a
//             bounded number of *sim cycles* (gate-level funcsim is slow in wallclock).
//   TIMEOUT - sim-time backstop (a last resort if the design neither finishes nor errors)
//
// The DUT (VTAPostSynthTb) is behavioral SV in both legs; only VTAShell is swapped for its
// post-synth netlist (VTAShell_funcsim.v) by run_xsim.sh. io_dbgW already surfaces the OUT
// writes from inside VTAShell, so no hierarchical snoop into the netlist is needed.
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
  // DEBUG probe set (XilinxDebugShell.debug, board-comparable) surfaced as dbg_* on the TB.
  wire [1:0]   dbg_computeState;
  wire         dbg_instQDeqValid, dbg_instQDeqReady;
  wire [9:0]   dbg_sem0, dbg_sem1;
  wire         dbg_computeIsFinish, dbg_computeIsLoadUop, dbg_computeIsLoadAcc;
  wire         dbg_computeIsSync, dbg_computeIsGemm, dbg_computeIsAlu;
  wire [7:0]   dbg_headByte;
  wire         dbg_loadUopDone, dbg_tensorAccDone, dbg_computeDone;
  wire [15:0]  dbg_luopYsize, dbg_luopClInFlight, dbg_vmeAvailEntries;
  wire         dbg_luopCommandsDone;
  wire [1:0]   dbg_vmeRdCmdValid, dbg_tensorAluState;
  wire [3:0]   dbg_tensorAluInf;
  wire         dbg_vcrFinish;
  wire [31:0]  dbg_vcrCtrl;
  wire [15:0]  dbg_vcrRaddr;
  wire [31:0]  dbg_vcrRdata, dbg_vcrEcnt0;
  wire         dbg_vcrEcnt0Val;
  wire         dbg_luStartSeen, dbg_luState;

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
    .dbg_computeState   (dbg_computeState),
    .dbg_instQDeqValid  (dbg_instQDeqValid),
    .dbg_instQDeqReady  (dbg_instQDeqReady),
    .dbg_sem0           (dbg_sem0),
    .dbg_sem1           (dbg_sem1),
    .dbg_computeIsFinish (dbg_computeIsFinish),
    .dbg_computeIsLoadUop(dbg_computeIsLoadUop),
    .dbg_computeIsLoadAcc(dbg_computeIsLoadAcc),
    .dbg_computeIsSync   (dbg_computeIsSync),
    .dbg_computeIsGemm   (dbg_computeIsGemm),
    .dbg_computeIsAlu    (dbg_computeIsAlu),
    .dbg_headByte       (dbg_headByte),
    .dbg_loadUopDone    (dbg_loadUopDone),
    .dbg_tensorAccDone  (dbg_tensorAccDone),
    .dbg_computeDone    (dbg_computeDone),
    .dbg_luopYsize      (dbg_luopYsize),
    .dbg_luopCommandsDone(dbg_luopCommandsDone),
    .dbg_luopClInFlight (dbg_luopClInFlight),
    .dbg_vmeRdCmdValid  (dbg_vmeRdCmdValid),
    .dbg_vmeAvailEntries(dbg_vmeAvailEntries),
    .dbg_tensorAluState (dbg_tensorAluState),
    .dbg_tensorAluInf   (dbg_tensorAluInf),
    .dbg_vcrFinish      (dbg_vcrFinish),
    .dbg_vcrCtrl        (dbg_vcrCtrl),
    .dbg_vcrRaddr       (dbg_vcrRaddr),
    .dbg_vcrRdata       (dbg_vcrRdata),
    .dbg_vcrEcnt0       (dbg_vcrEcnt0),
    .dbg_vcrEcnt0Val    (dbg_vcrEcnt0Val),
    .dbg_luStartSeen    (dbg_luStartSeen),
    .dbg_luState        (dbg_luState)
  );

  // ---- run / OUT-capture state (declared before the task that uses them) ---------------
  integer fout;
  integer beats;
  integer cyc;
  reg [`LAYERIDX_W-1:0] prevLayer;
  reg prevBusy;
  reg [7:0] prevHead;
  reg [9:0] prevSem0, prevSem1;

  task dbg_snap(input [127:0] tag);
    // Board Capture-4 probe set: pins the loadUop wedge sub-mechanism.
    //  loadUopDone=0 & luClInFlight=0 & luYsize>0 & vmeRdCmd[0]=0 & vmeAvail=ffff
    //    => loader never entered sBusy (start pulse lost). (board signature)
    // luStartSeen/luState settle WHY: luStartSeen=0 => start never reached the loader (launch-net
    // divergence); luStartSeen=1 & luState=0(sIdle) => seen but fell back (localDone/reset glitch).
    $display("DBG %0s cyc=%0d cState=%0d head=0x%02x [LU%0d F%0d Sy%0d] cDone=%0d luDone=%0d sem0=%0d sem1=%0d | luYsize=%0d luCmdDone=%0d luClInFlight=%0d vmeRdCmd=%0b vmeAvail=0x%0x | luStartSeen=%0d luState=%0d | vcrCtrl=0x%08x",
             tag, cyc, dbg_computeState, dbg_headByte,
             dbg_computeIsLoadUop, dbg_computeIsFinish, dbg_computeIsSync,
             dbg_computeDone, dbg_loadUopDone, dbg_sem0, dbg_sem1,
             dbg_luopYsize, dbg_luopCommandsDone, dbg_luopClInFlight, dbg_vmeRdCmdValid, dbg_vmeAvailEntries,
             dbg_luStartSeen, dbg_luState,
             dbg_vcrCtrl);
  endtask
  reg [1023:0] writes_path;
  initial begin
    beats = 0; cyc = 0; prevLayer = 0; prevBusy = 0;
    prevHead = 8'hxx; prevSem0 = 10'h3ff; prevSem1 = 10'h3ff;
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
    // Log on head-instruction or semaphore change: traces the instruction stream and
    // naturally stops once Compute parks (last line = the wedged state).
    if (dbg_headByte !== prevHead || dbg_sem0 !== prevSem0 || dbg_sem1 !== prevSem1) begin
      dbg_snap("STEP");
      prevHead = dbg_headByte; prevSem0 = dbg_sem0; prevSem1 = dbg_sem1;
    end
    prevBusy = io_busy;
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
        dbg_snap("WEDGE");
      end
      begin : to_w
        #(timeout_ns);
        $display("SIM_TOP: TIMEOUT layer=%0d  beats=%0d @ %0t", io_layerIdx, beats, $time);
      end
    join_any
    $fclose(fout);
    repeat (5) @(posedge clock);
    $finish;
  end
endmodule
