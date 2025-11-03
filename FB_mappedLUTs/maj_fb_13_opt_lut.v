module top (x0, x1, x2, x3, x4, x5, x6, x7, x8, x9, x10, x11, x12, y0);
  input x0, x1, x2, x3, x4, x5, x6, x7, x8, x9, x10, x11, x12;
  output y0;
  wire n15, n16, n17, n18, n19, n20, n21, n22, n23, n24, n25, n26;
  LUT3 #(.INIT(8'hE8)) lut_n15 (.I0(x0), .I1(x1), .I2(x2), .O(n15));
  LUT3 #(.INIT(8'hE8)) lut_n16 (.I0(x6), .I1(x7), .I2(x8), .O(n16));
  LUT5 #(.INIT(32'hFFE8E800)) lut_n17 (.I0(x3), .I1(x4), .I2(x5), .I3(n15), .I4(n16), .O(n17));
  LUT3 #(.INIT(8'h96)) lut_n18 (.I0(x0), .I1(x1), .I2(x2), .O(n18));
  LUT3 #(.INIT(8'h96)) lut_n19 (.I0(x6), .I1(x7), .I2(x8), .O(n19));
  LUT5 #(.INIT(32'hFF969600)) lut_n20 (.I0(x3), .I1(x4), .I2(x5), .I3(n18), .I4(n19), .O(n20));
  LUT3 #(.INIT(8'hE8)) lut_n21 (.I0(x9), .I1(x10), .I2(x11), .O(n21));
  LUT5 #(.INIT(32'hE81717E8)) lut_n22 (.I0(x3), .I1(x4), .I2(x5), .I3(n15), .I4(n16), .O(n22));
  LUT5 #(.INIT(32'h96696996)) lut_n23 (.I0(x3), .I1(x4), .I2(x5), .I3(n18), .I4(n19), .O(n23));
  LUT5 #(.INIT(32'hFF969600)) lut_n24 (.I0(x9), .I1(x10), .I2(x11), .I3(x12), .I4(n23), .O(n24));
  LUT5 #(.INIT(32'h96696996)) lut_n25 (.I0(x9), .I1(x10), .I2(x11), .I3(x12), .I4(n23), .O(n25));
  LUT6 #(.INIT(64'hFEEAEAA8EAA8A880)) lut_n26 (.I0(n17), .I1(n20), .I2(n21), .I3(n22), .I4(n24), .I5(n25), .O(n26));
  assign y0 = n26;
endmodule
