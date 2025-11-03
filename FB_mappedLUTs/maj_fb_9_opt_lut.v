module top (x0, x1, x2, x3, x4, x5, x6, x7, x8, y0);
  input x0, x1, x2, x3, x4, x5, x6, x7, x8;
  output y0;
  wire n11, n12, n13, n14, n15, n16, n17;
  LUT3 #(.INIT(8'hE8)) lut_n11 (.I0(x0), .I1(x1), .I2(x2), .O(n11));
  LUT3 #(.INIT(8'hE8)) lut_n12 (.I0(x3), .I1(x4), .I2(x5), .O(n12));
  LUT3 #(.INIT(8'hE8)) lut_n13 (.I0(x6), .I1(x7), .I2(x8), .O(n13));
  LUT3 #(.INIT(8'h96)) lut_n14 (.I0(x0), .I1(x1), .I2(x2), .O(n14));
  LUT3 #(.INIT(8'h96)) lut_n15 (.I0(x3), .I1(x4), .I2(x5), .O(n15));
  LUT3 #(.INIT(8'h96)) lut_n16 (.I0(x6), .I1(x7), .I2(x8), .O(n16));
  LUT6 #(.INIT(64'hFEE8E8E8E8E8E880)) lut_n17 (.I0(n11), .I1(n12), .I2(n13), .I3(n14), .I4(n15), .I5(n16), .O(n17));
  assign y0 = n17;
endmodule
