## `final_generator.py` Reference

This script is the single entry point used to emit both Verilog and BLIF
netlists for all majority designs evaluated in the project.  It lives in  
`verilog n-input files/verilog to blif/final_generator.py` and can be run
directly with Python 3:

```bash
python3 final_generator.py         # uses the parameters defined in the file
```

Running the script produces (i) a bundled Verilog file containing the
configured majority architectures, and (ii) canonical BLIF netlists for each
architecture.  It also prints per‑architecture statistics (FA counts, depth,
etc.) to the terminal.

---

### 1.  Configurable Parameters

The configuration block near the top of the file controls everything:

| Name | Description |
|------|-------------|
| `N` | Majority input size `n` (must be odd and ≥ 3). A single run synthesizes `n`-input majority logic for this setting. |
| `OUTPUT_DIR` | Filesystem directory where the Verilog bundle and BLIFs are written. |
| `OUTPUT_NAME` | Base filename for the Verilog bundle. |
| `INCLUDE_FOLDED_BIAS` | Emit the folded-bias CSA-only implementation `maj_fb_<n>` and its BLIF. |
| `INCLUDE_BASELINE_STRICT` | Emit the baseline “HW + threshold compare” implementation `maj_baseline_strict_<n>` and its BLIF. |
| `INCLUDE_FOLDED_BIAS_MAJP` / `INCLUDE_BASELINE_MAJP` | Enable the optional “majpath” wrappers that map an `n`-input design into the next scaffold size (disabled by default) (Still under production , NOT ADVISABLE). |
| `MAJ_ONLY_FA` | Controls how each full adder is expanded inside the BLIF (MAJ+NOT only vs XOR/MAJ). |

Changing any knob requires re-running the script.

---

### 2.  Architecture Summary

`final_generator.py` implements two majority constructions, both of which share
the same CSA backbone implemented by `csa_macro_schedule_all_columns()`:

1. **Folded-Bias (`maj_fb_<n>`).**  
   * Runs the CSA tree directly on the true `n` inputs.  
   * Injects the folded-bias constant `K = 2^w - th` (where `th = ceil((n+1)/2)`
     and `w = ceil(log2(th))`) directly into the relevant columns.  
   * The majority output is the carry produced at column `w-1`; no comparator or
     ripple adder is added after the CSA tree.

2. **Baseline STRICT (`maj_baseline_strict_<n>`).**  
   * Embeds the `n` inputs into the next “full” scaffold `N = 2^p - 1`.  
   * CSA stage collapses all `N` inputs into `p` single-rail HW bits.  
   * A ripple comparator of width `p` adds `(th_N - 1)` with `Cin = 1` and uses
     the final carry-out as the majority decision.

Both flavors rely on a generic FA primitive:

```verilog
module fa(input a, input b, input cin,
          output sum, output cout);
  assign {cout,sum} = a + b + cin;
endmodule
```

No vendor-specific primitives are assumed.

---

### 3.  Generated Outputs

Each run creates the following artifacts under `OUTPUT_DIR`:

| File | Contents |
|------|----------|
| `maj<n>_generated_canon.v` | Verilog bundle containing the enabled modules (folded-bias, baseline, optional wrappers). |
| `maj_fb_<n>.blif` | Canonical folded-bias BLIF using MAJ3/NOT/XOR3 encodings. |
| `maj_baseline_strict_<n>.blif` | Canonical baseline BLIF. |
| `maj_fb_majpath_<n>.blif`, `maj_baseline_majpath_<n>.blif` | Optional scaffolding wrappers when the MAJ-path flags are enabled. |

BLIF emission is fully canonicalized (sorted inputs, deduplicated cubes, and
explicit constants), which keeps downstream tools deterministic.

---

### 4.  Printed Statistics

After writing the files, the script prints per-architecture summaries, e.g.

```
FA count [folded_bias]: 9
FA count [baseline_strict]: 15

[Folded-Bias Stats]
  n: 9
  threshold: 5
  w_bits: 3
  bias_K: 3
  K_bits_set: 0, 1
  fa_count: 9
  fa_levels: 6
  maj_signal: c_c2_8

[Baseline STRICT Stats]
  n: 9
  threshold: 5
  scaffold_p: 4
  scaffold_inputs: 15
  scaffold_threshold: 8
  comparator_width: 4
  num_fixed_pairs: 3
  cin_init: 1
  csa_fa_count: 11
  comparator_fa_count: 4
  total_fa_count: 15
  csa_levels: 5
  total_levels: 9
  maj_signal: c2_4
```

Key metrics:

* **`fa_count`** – Total number of instantiated FAs in the CSA tree (folded-bias)
  or CSA+comparator (baseline).
* **`fa_levels` / `csa_levels`** – Maximum FA depth measured by propagating
  levels through the actual netlist.  Baseline also reports `total_levels =
  csa_levels + comparator_width`.
* **Threshold/bias parameters** – `th`, `w`, `K`, `popcount(K)`, scaffold size `N`, etc.

These numbers come directly from the constructed netlist, so they can be used
as ground truth in tables/plots.

---

### 5.  Implementation Notes

* `csa_macro_schedule_all_columns()` performs the column-by-column scheduling:
  it greedily forms FA triples, handles leftover pairs with a hard-wired zero,
  and pushes carries to the next column.  This exact sequence determines the
  FA counts and levels printed by the script.

* `build_*_netlist()` functions reconstruct the FA op lists used for BLIF
  emission.  They share the same scheduling logic, ensuring consistency between
  Verilog, BLIF, and the printed stats.

* Canonical BLIF writing (`_write_blif_from_fas_canonical`) supports both MAJ-only
  FA expansion and the MAJ/XOR hybrid, controlled by `MAJ_ONLY_FA`.

* The “majpath” wrappers are optional modules that map an `n`-input design onto
  the next scaffold size by transparently inserting constant 0/1 inputs.  They
  are disabled unless one of the `INCLUDE_*_MAJP` flags is set.

---

### 6.  Typical Workflow

1. Edit `final_generator.py` to set `N`, output directory/name, and the desired
   architecture flags.
2. Run `python3 final_generator.py`.
3. Consume `maj<n>_generated_canon.v` in simulation or synthesis, and/or feed
   the canonical BLIFs to downstream logic optimization or FPGA mapping tools.
4. Record the printed FA counts and depth numbers for reporting.

For visualization, the separate helper `verilog_draw.py` can draw either module
directly from the emitted Verilog:

```bash
python3 verilog_draw.py \
  "/path/to/maj9_generated_canon.v" \
  --top maj_baseline_strict_9 \
  --out-img figures/maj_baseline_strict_9.png
```

---

This document should serve as a quick reference for collaborators who need to
understand or tweak the majority generator without reading the entire source.
