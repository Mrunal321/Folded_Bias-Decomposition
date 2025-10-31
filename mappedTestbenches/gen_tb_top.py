import math
from pathlib import Path

def bits_needed(n: int) -> int:
    return max(1, math.ceil(math.log2(n + 1)))

def make_x_port_map_one_line(n: int) -> str:
    # ".x0(x[0]), .x1(x[1]), ..., .x<n-1>(x[n-1])"
    return ", ".join([f".x{i}(x[{i}])" for i in range(n)])

def header_strings(n: int):
    # Example: "Time | x4 x3 x2 x1 x0 | y0 (DUT) y_ref (Maj5)"
    xs = " ".join([f"x{i}" for i in range(n-1, -1, -1)])
    title = f"Time | {xs} | y0 (DUT) y_ref (Maj{n})"
    dashes = "-" * len(title)
    return title, dashes

def gen_tb_top(n: int, module_name: str = "top") -> str:
    if n < 1:
        raise ValueError("n must be >= 1")
    cw = bits_needed(n)
    th = math.ceil(n/2)

    x_ports_one_line = make_x_port_map_one_line(n)
    title, dashes = header_strings(n)

    # Produce the exact style you want
    tb = f"""`timescale 1ns/1ps
`default_nettype none

module tb_top;
  // {n}-bit input vector
  reg  [{n-1}:0] x = {n}'b0;
  wire       y0;

  // DUT instantiation
  {module_name} dut (
    {x_ports_one_line},
    .y0(y0)
  );

  // Optional reference function (majority reference for sanity check)
  function [{cw-1}:0] popcount(input [{n-1}:0] v);
    integer i; reg [{cw-1}:0] c;
    begin
      c = 0;
      for (i = 0; i < {n}; i = i + 1)
        c = c + v[i];
      popcount = c;
    end
  endfunction

  // Reference majority: at least {th} ones
  wire y_ref = (popcount(x) >= {th});

  initial begin
    $display("{title}");
    $display("{dashes}");
    // Loop through all {1<<n} combinations
    repeat ({1<<n}) begin
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
"""
    return tb

# --------- Run as a script ---------
if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser(
        description="Generate EXACT-STYLE tb_top for module 'top' with inputs x0..x<n-1> and output y0."
    )
    ap.add_argument(
        "n",
        type=int,
        nargs="+",
        help="One or more input widths. Example: '5' or '5 7 9'.",
    )
    ap.add_argument(
        "--module",
        default="top",
        help="DUT module name (default: top)",
    )
    ap.add_argument(
        "--out",
        help="Output filename (only valid when generating a single width).",
    )
    ap.add_argument(
        "--range",
        action="store_true",
        help="Treat the provided single n as the inclusive upper bound and emit widths "
             "starting at --start and stepping by --step (defaults: 5, 2).",
    )
    ap.add_argument(
        "--start",
        type=int,
        default=5,
        help="Starting width when using --range (default: 5).",
    )
    ap.add_argument(
        "--step",
        type=int,
        default=2,
        help="Step between widths when using --range (default: 2).",
    )
    ap.add_argument(
        "--out-dir",
        default=".",
        help="Directory to write generated testbenches (default: current directory).",
    )
    args = ap.parse_args()

    if args.range:
        if len(args.n) != 1:
            ap.error("--range requires exactly one terminal n value.")
        terminal = args.n[0]
        if terminal < args.start:
            ap.error("Terminal n must be greater than or equal to --start.")
        if args.step <= 0:
            ap.error("--step must be a positive integer.")
        distance = terminal - args.start
        if distance % args.step != 0:
            ap.error("Terminal n is not reachable from --start using --step.")
        widths = list(range(args.start, terminal + args.step, args.step))
    else:
        widths = args.n

    if len(widths) > 1 and args.out:
        ap.error("--out can only be used when generating a single width.")

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    for width in widths:
        tb = gen_tb_top(width, module_name=args.module)
        if args.out and len(widths) == 1:
            out_path = Path(args.out)
            if not out_path.is_absolute():
                out_path = out_dir / out_path
        else:
            out_path = out_dir / f"tb_top_{width}.v"
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with open(out_path, "w") as f:
            f.write(tb)
        print(f"✅ Wrote {out_path}")
