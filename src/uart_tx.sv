`default_nettype none

module uart_tx #(
    parameter int CLKS_PER_BIT = 434
) (
    input  logic       clk,
    input  logic       rst_n,      // active-low, asynchronous
    input  logic       start,
    input  logic [7:0] data,
    output logic       tx,
    output logic       busy
);

  logic [8:0] shreg;     // {stop, data[7:0]}
  logic [3:0] bit_cnt;
  logic [$clog2(CLKS_PER_BIT)-1:0] baud_cnt;

  always_ff @(posedge clk or negedge rst_n) begin
    if (!rst_n) begin
      tx       <= 1'b1;
      busy     <= 1'b0;
      shreg    <= '1;
      bit_cnt  <= '0;
      baud_cnt <= '0;
    end else if (!busy) begin
      if (start) begin
        tx       <= 1'b0;
        shreg    <= {1'b1, data};
        busy     <= 1'b1;
        bit_cnt  <= '0;
        baud_cnt <= '0;
      end
    end else if (baud_cnt == CLKS_PER_BIT - 1) begin
      baud_cnt <= '0;
      if (bit_cnt == 4'd9) begin
        busy <= 1'b0;
      end else begin
        tx      <= shreg[0];
        shreg   <= {1'b1, shreg[8:1]};
        bit_cnt <= bit_cnt + 1'b1;
      end
    end else begin
      baud_cnt <= baud_cnt + 1'b1;
    end
  end

endmodule