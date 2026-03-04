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

  wire ready_pre;
  assign ready_pre = ready_i | ~valid_l;

  always @(posedge clk_i or posedge reset_i) begin
    if (reset_i) begin
      valid_l <= 1'b0;
      if (datapath_reset_p) begin
        data_l <= 8'b0;
      end
    end else if (ready_pre) begin
      valid_l <= valid_i;

      if (datapath_gate_p) begin
        if (valid_i) begin
          data_l <= data_i;
        end
      end else begin
        data_l <= data_i;
      end
    end
  end

  assign valid_o = valid_l;
  assign data_o  = data_l;
  assign ready_o = ready_i | ~valid_l;

endmodule
