`default_nettype none
`timescale 1ns / 1ps

module tb ();
  initial begin
    $dumpfile("tb.fst");
    $dumpvars(0, tb);
    #1;
  end

  reg clk;
  reg rst_n;
  reg ena;
  reg  [7:0] ui_in;
  reg  [7:0] uio_in;
  wire [7:0] uo_out;
  wire [7:0] uio_out;
  wire [7:0] uio_oe;

  // Power supplies required for GL simulation with USE_POWER_PINS.
  // sky130 cells have explicit VPWR/VGND ports when this flag is set.
  // Without these, every FF powers up with X and never resolves.
`ifdef GL_TEST
  supply1 vccd1;
  supply0 vssd1;
`endif

  tt_um_pipeline_skid_buffer user_project (
`ifdef GL_TEST
      .vccd1  (vccd1),
      .vssd1  (vssd1),
`endif
      .ui_in  (ui_in),
      .uo_out (uo_out),
      .uio_in (uio_in),
      .uio_out(uio_out),
      .uio_oe (uio_oe),
      .ena    (ena),
      .clk    (clk),
      .rst_n  (rst_n)
  );

endmodule
