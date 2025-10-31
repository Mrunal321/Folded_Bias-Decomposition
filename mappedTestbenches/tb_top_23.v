`timescale 1ns/1ps
`default_nettype none

module tb_top;
  // 23-bit input vector
  reg  [22:0] x = 23'b0;
  wire       y0;

  // DUT instantiation
  top dut (
    .x0(x[0]), .x1(x[1]), .x2(x[2]), .x3(x[3]), .x4(x[4]), .x5(x[5]), .x6(x[6]), .x7(x[7]), .x8(x[8]), .x9(x[9]), .x10(x[10]), .x11(x[11]), .x12(x[12]), .x13(x[13]), .x14(x[14]), .x15(x[15]), .x16(x[16]), .x17(x[17]), .x18(x[18]), .x19(x[19]), .x20(x[20]), .x21(x[21]), .x22(x[22]),
    .y0(y0)
  );

  // Optional reference function (majority reference for sanity check)
  function [4:0] popcount(input [22:0] v);
    integer i; reg [4:0] c;
    begin
      c = 0;
      for (i = 0; i < 23; i = i + 1)
        c = c + v[i];
      popcount = c;
    end
  endfunction

  // Reference majority: at least 12 ones
  wire y_ref = (popcount(x) >= 12);

  initial begin
    $display("Time | x22 x21 x20 x19 x18 x17 x16 x15 x14 x13 x12 x11 x10 x9 x8 x7 x6 x5 x4 x3 x2 x1 x0 | y0 (DUT) y_ref (Maj23)");
    $display("-----------------------------------------------------------------------------------------------------------------");
    // Loop through all 8388608 combinations
    repeat (8388608) begin
      #10 $display("%4t |  %b  |   %b       %b",
                   $time, x, y0, y_ref);
      x = x + 1;
    end
    #10 $finish;
  end

  // Optional mismatch check
  always #1 if (^x !== 1'bx && y0 !== y_ref)
    $display("Mismatch at t=%0t x=%b HW=%0d y0=%0b ref=%0b",
             $time, x, popcount(x), y0, y_ref);

endmodule

`default_nettype wire
