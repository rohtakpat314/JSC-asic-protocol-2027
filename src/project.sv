/*
 * Copyright (c) 2026 Rohtak Patwardhan
 * SPDX-License-Identifier: Apache-2.0
 */

`default_nettype none

module tt_um_rohtakpat314_protoemu (
    input  wire [7:0] ui_in,    // DATA[7:0]
    output wire [7:0] uo_out,   // [0] UART_TX, [1] BUSY
    input  wire [7:0] uio_in,   // [0] SEND
    output wire [7:0] uio_out,
    output wire [7:0] uio_oe,
    input  wire       ena,
    input  wire       clk,
    input  wire       rst_n
);

  // Synchronize SEND and detect rising edge -> one byte per press
  logic [2:0] send_sync;
  always_ff @(posedge clk or negedge rst_n) begin
    if (!rst_n) send_sync <= 3'b000;
    else        send_sync <= {send_sync[1:0], uio_in[0]};
  end
  wire send_rise = send_sync[1] & ~send_sync[2];

  wire tx, busy;

  uart_tx #(.CLKS_PER_BIT(434)) u_tx (   // 50 MHz / 115200
      .clk  (clk),
      .rst_n(rst_n),
      .start(send_rise),
      .data (ui_in),
      .tx   (tx),
      .busy (busy)
  );

  assign uo_out  = {6'b0, busy, tx};
  assign uio_out = 8'b0;
  assign uio_oe  = 8'b0;

  wire _unused = &{ena, uio_in[7:1], 1'b0};

endmodule