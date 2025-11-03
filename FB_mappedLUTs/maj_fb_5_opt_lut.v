module top (x0, x1, x2, x3, x4, y0);
  input x0, x1, x2, x3, x4;
  output y0;
  wire n7;
  LUT5 #(.INIT(32'hFEE8E880)) lut_n7 (.I0(x0), .I1(x1), .I2(x2), .I3(x3), .I4(x4), .O(n7));
  assign y0 = n7;
endmodule
