module top (x0, x1, x2, x3, x4, x5, x6, y0);
  input x0, x1, x2, x3, x4, x5, x6;
  output y0;
  wire n9, n10, n11;
  LUT3 #(.INIT(8'hE8)) lut_n9 (.I0(x0), .I1(x1), .I2(x2), .O(n9));
  LUT3 #(.INIT(8'h96)) lut_n10 (.I0(x0), .I1(x1), .I2(x2), .O(n10));
  LUT6 #(.INIT(64'hFFFEE880FEE88000)) lut_n11 (.I0(x3), .I1(x4), .I2(x5), .I3(x6), .I4(n9), .I5(n10), .O(n11));
  assign y0 = n11;
endmodule
