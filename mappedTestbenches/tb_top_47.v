`timescale 1ns/1ps
`default_nettype none

module tb_top;
  // 47-bit input vector
  reg  [46:0] x = 47'b0;
  wire       y0;
  reg  [63:0] idx;

  // DUT instantiation
  top dut (
    .x0(x[0]), .x1(x[1]), .x2(x[2]), .x3(x[3]), .x4(x[4]), .x5(x[5]), .x6(x[6]), .x7(x[7]), .x8(x[8]), .x9(x[9]), .x10(x[10]), .x11(x[11]), .x12(x[12]), .x13(x[13]), .x14(x[14]), .x15(x[15]), .x16(x[16]), .x17(x[17]), .x18(x[18]), .x19(x[19]), .x20(x[20]), .x21(x[21]), .x22(x[22]), .x23(x[23]), .x24(x[24]), .x25(x[25]), .x26(x[26]), .x27(x[27]), .x28(x[28]), .x29(x[29]), .x30(x[30]), .x31(x[31]), .x32(x[32]), .x33(x[33]), .x34(x[34]), .x35(x[35]), .x36(x[36]), .x37(x[37]), .x38(x[38]), .x39(x[39]), .x40(x[40]), .x41(x[41]), .x42(x[42]), .x43(x[43]), .x44(x[44]), .x45(x[45]), .x46(x[46]),
    .y0(y0)
  );

  // Optional reference function (majority reference for sanity check)
  function [5:0] popcount(input [46:0] v);
    integer i; reg [5:0] c;
    begin
      c = 0;
      for (i = 0; i < 47; i = i + 1)
        c = c + v[i];
      popcount = c;
    end
  endfunction

  // Reference majority: at least 24 ones
  wire y_ref = (popcount(x) >= 24);

  localparam [63:0] TOTAL_VECTORS = 64'd140737488355328;

  initial begin
    $display("Time | x46 x45 x44 x43 x42 x41 x40 x39 x38 x37 x36 x35 x34 x33 x32 x31 x30 x29 x28 x27 x26 x25 x24 x23 x22 x21 x20 x19 x18 x17 x16 x15 x14 x13 x12 x11 x10 x9 x8 x7 x6 x5 x4 x3 x2 x1 x0 | y0 (DUT) y_ref (Maj47)");
    $display("-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------");
    // Loop through all 140737488355328 combinations
    for (idx = 0; idx < TOTAL_VECTORS; idx = idx + 1) begin
      x = idx[46:0];
      #10 $display("%4t |  %b  |   %b       %b",
                   $time, x, y0, y_ref);
    end
    #10 $finish;
  end

  // Optional mismatch check
  always #1 if (^x !== 1'bx && y0 !== y_ref)
    $display("Mismatch at t=%0t x=%b HW=%0d y0=%0b ref=%0b",
             $time, x, popcount(x), y0, y_ref);

endmodule

`default_nettype wire
