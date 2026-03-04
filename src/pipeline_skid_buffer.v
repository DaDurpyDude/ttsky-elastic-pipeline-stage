/*
 * Copyright (c) 2024 Rishikesh Sethuraman
 * SPDX-License-Identifier: Apache-2.0
 */

 `default_nettype none

module pipeline_skid_buffer

  #(parameter datapath_gate_p = 0
   ,parameter datapath_reset_p = 0
   )

  (input clk_i
  ,input reset_i
  ,output ready_o
  ,input valid_i
  ,input [7:0] data_i 
  ,input ready_i
  ,output valid_o 
  ,output [7:0] data_o 
  );

  reg [7:0] data_l;
  reg valid_l;

  always @(posedge clk_i) begin
    if (reset_i) begin
      valid_l <= 1'b0;
      if (datapath_reset_p) begin
        data_l <= 8'b0;
      end
    end else begin
      if (ready_o & valid_i) begin
        valid_l <= 1'b1;
      end else begin
        if (ready_i) begin
          valid_l <= 1'b0;
        end
      end
      if (datapath_gate_p) begin
        if (ready_o & valid_i) begin
          data_l <= data_i;
        end
      end else begin
        if (ready_o) begin
          data_l <= data_i;
        end
      end
    end
  end
  
  assign data_o = data_l;
  assign ready_o = ready_i | ~valid_o;
  assign valid_o = valid_l;

endmodule

