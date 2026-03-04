`default_nettype none

module pipeline_skid_buffer
  #(parameter datapath_gate_p  = 0
   ,parameter datapath_reset_p = 0
   )
  ( input  wire       clk_i
  , input  wire       reset_i
  , output wire       ready_o
  , input  wire       valid_i
  , input  wire [7:0] data_i
  , input  wire       ready_i
  , output wire       valid_o
  , output wire [7:0] data_o
  );

  reg [7:0] data_l;
  reg       valid_l;

  // Ready computation: ready_pre is high if the buffer is empty or downstream is ready
  wire ready_pre = ready_i | ~valid_l;

  always @(posedge clk_i or posedge reset_i) begin
    if (reset_i) begin
      valid_l <= 1'b0;
      if (datapath_reset_p)
        data_l <= 8'b0;
      // Otherwise don't touch data_l per datapath_reset_p=0
    end else begin
      if (ready_pre && valid_i) begin
        // True transfer: accept new data
        valid_l <= 1'b1;
        data_l  <= data_i;
      end else if (ready_i) begin
        // Buffer drains: clear valid if downstream accepts data
        valid_l <= 1'b0;
        // NOTE: data_l should NOT be updated here or else you break stall correctness
      end
      // Else (no transfer, no readout): hold valid_l, data_l
    end
  end

  assign valid_o = valid_l;
  assign data_o  = data_l;
  assign ready_o = ready_i | ~valid_l;

endmodule
