/*
 * Copyright (c) 2024 Rishikesh Sethuraman
 * SPDX-License-Identifier: Apache-2.0
 */

`default_nettype none

module tt_um_pipeline_skid_buffer (
    input  wire [7:0] ui_in,    // Dedicated inputs
    output wire [7:0] uo_out,   // Dedicated outputs
    input  wire [7:0] uio_in,   // IOs: Input path
    output wire [7:0] uio_out,  // IOs: Output path
    output wire [7:0] uio_oe,   // IOs: Enable path (active high: 0=input, 1=output)
    input  wire       ena,      // always 1 when the design is powered, so you can ignore it
    input  wire       clk,      // clock
    input  wire       rst_n     // reset_n - low to reset
);

  localparam GATE_DATA = 1;
  localparam RESET_DATA = 0;

  pipeline_skid_buffer #(
    .datapath_gate_p(GATE_DATA), 
    .datapath_reset_p(RESET_DATA)
  ) skid_buffer (
    .clk_i(clk),
    .reset_i(~rst_n),
    .ready_o(uio_out[2]),
    .valid_i(uio_in[1]),
    .data_i(ui_in),
    .ready_i(uio_in[0]),
    .valid_o(uio_out[3]),
    .data_o(uo_out)
  );

  assign uio_oe = 8'b00001100;
  assign {uio_out[1:0], uio_out[7:4]} = 6'b0;

  // List all unused inputs to prevent warnings
  wire _unused = &{ena, uio_in[7:2], 1'b0};

endmodule
