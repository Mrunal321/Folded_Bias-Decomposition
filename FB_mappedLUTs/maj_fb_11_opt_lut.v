module top (x0, x1, x2, x3, x4, x5, x6, x7, x8, x9, x10, y0);
  input x0, x1, x2, x3, x4, x5, x6, x7, x8, x9, x10;
  output y0;
  wire n13, n14, n15, n16, n17, n19, n18, n20, n21;
  LUT3 #(.INIT(8'hE8)) lut_n13 (.I0(x0), .I1(x1), .I2(x2), .O(n13));
  LUT3 #(.INIT(8'hE8)) lut_n14 (.I0(x3), .I1(x4), .I2(x5), .O(n14));
  LUT3 #(.INIT(8'hE8)) lut_n15 (.I0(x6), .I1(x7), .I2(x8), .O(n15));
  LUT3 #(.INIT(8'h96)) lut_n16 (.I0(x0), .I1(x1), .I2(x2), .O(n16));
  LUT3 #(.INIT(8'h96)) lut_n17 (.I0(x3), .I1(x4), .I2(x5), .O(n17));
  LUT5 #(.INIT(32'hFF969600)) lut_n19 (.I0(x6), .I1(x7), .I2(x8), .I3(n16), .I4(n17), .O(n19));
  LUT3 #(.INIT(8'h96)) lut_n18 (.I0(x6), .I1(x7), .I2(x8), .O(n18));
  LUT5 #(.INIT(32'hE88E8EE8)) lut_n20 (.I0(x9), .I1(x10), .I2(n16), .I3(n17), .I4(n18), .O(n20));
  LUT5 #(.INIT(32'hFEE8E880)) lut_n21 (.I0(n13), .I1(n14), .I2(n15), .I3(n19), .I4(n20), .O(n21));
  assign y0 = n21;
endmodule
