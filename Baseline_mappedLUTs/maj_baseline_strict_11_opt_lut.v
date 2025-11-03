module top (x0, x1, x2, x3, x4, x5, x6, x7, x8, x9, x10, y0);
  input x0, x1, x2, x3, x4, x5, x6, x7, x8, x9, x10;
  output y0;
  wire n13, n14, n15, n16, n17, n18, n19, n20, n21;
  LUT3 #(.INIT(8'hE8)) lut_n13 (.I0(x0), .I1(x1), .I2(x2), .O(n13));
  LUT3 #(.INIT(8'hE8)) lut_n14 (.I0(x3), .I1(x4), .I2(x5), .O(n14));
  LUT3 #(.INIT(8'hE8)) lut_n15 (.I0(x6), .I1(x7), .I2(x8), .O(n15));
  LUT5 #(.INIT(32'hE81717E8)) lut_n16 (.I0(x3), .I1(x4), .I2(x5), .I3(n13), .I4(n15), .O(n16));
  LUT3 #(.INIT(8'h96)) lut_n17 (.I0(x0), .I1(x1), .I2(x2), .O(n17));
  LUT3 #(.INIT(8'h96)) lut_n18 (.I0(x3), .I1(x4), .I2(x5), .O(n18));
  LUT3 #(.INIT(8'h96)) lut_n19 (.I0(x6), .I1(x7), .I2(x8), .O(n19));
  LUT6 #(.INIT(64'hFF9F9F1E9F1E1E18)) lut_n20 (.I0(x9), .I1(x10), .I2(n16), .I3(n17), .I4(n18), .I5(n19), .O(n20));
  LUT6 #(.INIT(64'hFFFEFEE0E0000000)) lut_n21 (.I0(x9), .I1(x10), .I2(n13), .I3(n14), .I4(n15), .I5(n20), .O(n21));
  assign y0 = n21;
endmodule
