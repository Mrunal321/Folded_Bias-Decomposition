#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Majority (n-input) Verilog + BLIF generator (canonical BLIF)
------------------------------------------------------------
Outputs:
  - Verilog bundle with:
      1) maj_fb_<n>                : Folded-bias (CSA-only to bit w)
      2) maj_baseline_strict_<n>   : STRICT 2-step baseline
  - BLIFs with canonical .names encodings:
      - maj_fb_<n>.blif
      - maj_baseline_strict_<n>.blif

Notes on BLIF canonicalization:
  * Gate inputs are SORTED (alphabetically) at emission time.
  * Truth-table cubes are MINIMAL + DEDUPED.
  * Encodings used:
      - MAJ3: 11- 1 ; 1-1 1 ; -11 1
      - NOT : 0 1
      - XOR3: 001 1 ; 010 1 ; 100 1 ; 111 1   (only if maj_only=False)
  * Constants are explicit: .names CONST1\n1  (and empty .names CONST0 when needed)
"""

# ===================== CONFIG =====================
N = 9  # majority input size (odd, >=3)

OUTPUT_DIR = r"/home"
OUTPUT_NAME = f"maj{N}_generated_canon.v"

INCLUDE_FOLDED_BIAS       = True   # maj_fb_<n>
INCLUDE_BASELINE_STRICT   = True   # maj_baseline_strict_<n>
INCLUDE_FOLDED_BIAS_MAJP  = 0   # maj_fb_majpath_<n>
INCLUDE_BASELINE_MAJP     = 0   # maj_baseline_majpath_<n>

# BLIF adder style:
#   True  = expand FA as MAJ-only (3x MAJ + 2x INV)  [best for MIG passes]
#   False = expand FA with {XOR3 for sum, MAJ3 for cout}
MAJ_ONLY_FA = True
# ===================================================

import os, math, random
from collections import defaultdict, deque

# ---------- common helpers ----------
def _verilog_header(n, title):
    return [
        f"// -----------------------------------------------------------------------------",
        f"// {title}",
        f"// n = {n}",
        f"// Expect FA primitive: module fa(input a,b,cin, output sum,cout);",
        f"// -----------------------------------------------------------------------------",
        ""
    ]


def _fa_max_levels(fa_ops):
    """Return the maximum FA level depth in a sequential FA list."""
    if not fa_ops:
        return 0

    levels = {}

    def get_level(sig):
        if sig in ("1'b0", "1'b1", None):
            return 0
        return levels.get(sig, 0)

    max_level = 0
    for a, b, cin, s, k in fa_ops:
        curr = max(get_level(a), get_level(b), get_level(cin)) + 1
        levels[s] = curr
        levels[k] = curr
        if curr > max_level:
            max_level = curr
    return max_level

# ======== CSA MACRO SCHEDULER (used by both variants) ========
def csa_macro_schedule_all_columns(raw_inputs, const_names_per_col):
    """
    Build a CSA macro tree:
      Stage A (col 0): only RAW input triples -> (s@0, c@1)
      Stage B (col 0): fold [sums + leftover raw + const@0...] -> ONE bit; carries -> col 1
      Columns 1..: fold each column j to ONE bit (serial chain); carries -> j+1
    Returns:
      ops             : list[(col, kind, a,b,cin, s,k)]  // FA instances
      wires           : list[(s,k)]                      // wire names to declare
      residual_by_col : {col: residual_bit_name}        // final single bit per column
      const_decl      : list[str]                        // const wires to declare (e.g., K0..)
    """
    fa_id = 0
    ops   = []
    wires = []

    def new_wires(col, tag=""):
        nonlocal fa_id
        s = f"{tag}s_c{col}_{fa_id}"
        k = f"{tag}c_c{col}_{fa_id}"
        fa_id += 1
        wires.append((s, k))
        return s, k

    # ---- Stage A: RAW triples at col 0 ----
    raw = list(raw_inputs)
    col0_sums = deque()
    col_bits  = {1: deque()}  # carries from col 0 land here

    while len(raw) >= 3:
        a = raw.pop(0); b = raw.pop(0); c = raw.pop(0)
        s, k = new_wires(0, "raw_")
        ops.append((0, "raw_triple", a, b, c, s, k))
        col0_sums.append(s)
        col_bits[1].append(k)

    # ---- Stage B: fold col 0 to ONE bit (include constants at col 0 if any) ----
    col0_queue = deque(list(col0_sums) + raw)
    const_decl = []
    for cname in const_names_per_col.get(0, []):
        col0_queue.append(cname)
        const_decl.append(cname)

    residual_by_col = {}

    def fold_column(col, queue):
        carries_out = []
        if not queue:
            return None, carries_out

        acc = queue.popleft()
        while len(queue) >= 2:
            b = queue.popleft()
            c = queue.popleft()
            s, k = new_wires(col, "")
            ops.append((col, "triple", acc, b, c, s, k))
            carries_out.append(k)
            acc = s

        if len(queue) == 1:
            b = queue.popleft()
            s, k = new_wires(col, "p_")
            ops.append((col, "pair", acc, b, "1'b0", s, k))
            carries_out.append(k)
            acc = s

        return acc, carries_out

    # fold col 0
    res0, carries_to_1 = fold_column(0, col0_queue)
    if res0 is not None:
        residual_by_col[0] = res0
    for k in carries_to_1:
        col_bits.setdefault(1, deque()).append(k)

    # ---- Columns 1.. : fold each to ONE bit; push carries upward ----
    pending_cols = set(col_bits.keys()) | set(const_names_per_col.keys())
    current = 1
    while True:
        candidates = [c for c in pending_cols if c >= current and (
            (c in col_bits and len(col_bits[c]) > 0) or (c in const_names_per_col and len(const_names_per_col[c]) > 0)
        )]
        if not candidates:
            break
        j = min(candidates)

        qj = col_bits.get(j, deque())
        if j in const_names_per_col:
            for cname in const_names_per_col[j]:
                qj.append(cname)
                const_decl.append(cname)

        residual_j, carries_to_next = fold_column(j, qj)
        if residual_j is not None:
            residual_by_col[j] = residual_j
        if carries_to_next:
            col_bits.setdefault(j+1, deque()).extend(carries_to_next)
            pending_cols.add(j+1)

        # mark processed
        if j in col_bits: col_bits[j] = deque()
        if j in const_names_per_col: const_names_per_col[j] = []
        current = j + 1

    return ops, wires, residual_by_col, const_decl


# ---------- scaffold + reduction helpers ----------
def _scaffold_params(n: int):
    """
    Minimal scaffold via reduction rule Maj_{2k+1}(x) = Maj_{2(k+1)+1}(0,1,x).
    For target n = 2k+1 we embed into N_big = n + 2.
    """
    k = (n - 1) // 2
    n_big = k + 1
    N_big = 2 * n_big + 1  # n + 2
    m = math.ceil(math.log2(N_big + 1))
    num_fix = n_big - k    # always 1 for this minimal scaffold
    return m, N_big, m, num_fix


def _scaffold_layout_sequences(n: int, num_fix: int, N_big: int):
    if num_fix <= 0:
        return [("identity", [('x', i) for i in range(n)])]

    layouts = []

    def layout_clustered():
        seq = [('x', i) for i in range(n)]
        for idx in range(num_fix):
            seq.append(('1', idx))
            seq.append(('0', idx))
        return seq

    def layout_interleaved():
        seq = []
        ones_idx = zeros_idx = 0
        for idx in range(n):
            seq.append(('x', idx))
            if ones_idx < num_fix:
                seq.append(('1', ones_idx)); ones_idx += 1
            if zeros_idx < num_fix:
                seq.append(('0', zeros_idx)); zeros_idx += 1
        while ones_idx < num_fix or zeros_idx < num_fix:
            if ones_idx < num_fix:
                seq.append(('1', ones_idx)); ones_idx += 1
            if zeros_idx < num_fix:
                seq.append(('0', zeros_idx)); zeros_idx += 1
        return seq

    def layout_alternating():
        seq = []
        ones_idx = zeros_idx = 0
        x_idx = 0
        while len(seq) < N_big:
            if x_idx < n:
                seq.append(('x', x_idx)); x_idx += 1
            if ones_idx < num_fix and len(seq) < N_big:
                seq.append(('1', ones_idx)); ones_idx += 1
            if x_idx < n and len(seq) < N_big:
                seq.append(('x', x_idx)); x_idx += 1
            if zeros_idx < num_fix and len(seq) < N_big:
                seq.append(('0', zeros_idx)); zeros_idx += 1
        while x_idx < n and len(seq) < N_big:
            seq.append(('x', x_idx)); x_idx += 1
        while ones_idx < num_fix and len(seq) < N_big:
            seq.append(('1', ones_idx)); ones_idx += 1
        while zeros_idx < num_fix and len(seq) < N_big:
            seq.append(('0', zeros_idx)); zeros_idx += 1
        return seq

    def layout_alt_offset1():
        seq = []
        ones_idx = zeros_idx = 0
        x_idx = 0
        toggle = 0
        while len(seq) < N_big:
            if toggle % 2 == 0 and x_idx < n:
                seq.append(('x', x_idx)); x_idx += 1
            elif toggle % 4 == 1 and ones_idx < num_fix:
                seq.append(('1', ones_idx)); ones_idx += 1
            elif toggle % 4 == 3 and zeros_idx < num_fix:
                seq.append(('0', zeros_idx)); zeros_idx += 1
            else:
                if x_idx < n:
                    seq.append(('x', x_idx)); x_idx += 1
                elif ones_idx < num_fix:
                    seq.append(('1', ones_idx)); ones_idx += 1
                elif zeros_idx < num_fix:
                    seq.append(('0', zeros_idx)); zeros_idx += 1
            toggle += 1
        return seq[:N_big]

    layouts.append(("clustered", layout_clustered()))
    layouts.append(("interleaved", layout_interleaved()))
    layouts.append(("alternating", layout_alternating()))
    layouts.append(("alt_off1", layout_alt_offset1()))

    base = [('x', i) for i in range(n)] + [('1', i) for i in range(num_fix)] + [('0', i) for i in range(num_fix)]
    for seed in range(12):
        random.seed(seed)
        seq = base[:]
        random.shuffle(seq)
        layouts.append((f"rand{seed}", seq[:N_big]))

    return [(name, seq[:N_big]) for name, seq in layouts]


def _tokens_to_mapping(sequence):
    mapping = []
    for kind, idx in sequence:
        if kind == 'x':
            mapping.append(f"x[{idx}]")
        elif kind == '1':
            mapping.append("1'b1")
        else:
            mapping.append("1'b0")
    return mapping


def _remap_signal(sig: str, mapping):
    if sig.startswith('x[') and sig.endswith(']'):
        try:
            idx = int(sig[2:-1])
        except ValueError:
            return sig
        if 0 <= idx < len(mapping):
            return mapping[idx]
    return sig


def _apply_mapping_to_netlist(fa_ops, maj_signal, mapping):
    remapped_ops = []
    for a, b, cin, s, k in fa_ops:
        ra = _remap_signal(a, mapping)
        rb = _remap_signal(b, mapping)
        rc = _remap_signal(cin, mapping)
        remapped_ops.append((ra, rb, rc, s, k))
    remapped_maj = _remap_signal(maj_signal, mapping)
    return remapped_ops, remapped_maj


def _is_const(sig: str) -> bool:
    return sig in ("1'b0", "1'b1")


def _prune_fa_netlist(fa_ops, maj_signal):
    needed = {maj_signal}
    pruned_rev = []
    for a, b, cin, s, k in reversed(fa_ops):
        if s in needed or k in needed:
            pruned_rev.append((a, b, cin, s, k))
            for sig in (a, b, cin):
                if not _is_const(sig):
                    needed.add(sig)
    return list(reversed(pruned_rev))


def _constant_fold_and_prune(fa_ops, maj_signal):
    const_map = {}

    def resolve(sig):
        while sig in const_map:
            sig = const_map[sig]
        return sig

    processed = []
    for a, b, cin, s, k in fa_ops:
        a = resolve(a); b = resolve(b); cin = resolve(cin)
        if _is_const(a) and _is_const(b) and _is_const(cin):
            ones = (a == "1'b1") + (b == "1'b1") + (cin == "1'b1")
            const_map[s] = "1'b1" if (ones & 1) else "1'b0"
            const_map[k] = "1'b1" if ones >= 2 else "1'b0"
            continue
        processed.append((a, b, cin, s, k))

    maj_signal = resolve(maj_signal)
    folded = []
    for a, b, cin, s, k in processed:
        folded.append((resolve(a), resolve(b), resolve(cin), resolve(s), resolve(k)))

    folded = _prune_fa_netlist(folded, maj_signal)
    return folded, maj_signal


def _collect_const_names(fa_ops, maj_signal, candidates):
    used = set()
    candidate_set = set(candidates or [])
    for a, b, cin, s, k in fa_ops:
        for sig in (a, b, cin, s, k):
            if sig in candidate_set:
                used.add(sig)
    if maj_signal in candidate_set:
        used.add(maj_signal)
    return sorted(used)


def _prepare_for_emit(fa_ops, maj_signal, const_candidates):
    fa_ops_prepped, maj_signal_prepped = _constant_fold_and_prune(list(fa_ops), maj_signal)
    const_used = _collect_const_names(fa_ops_prepped, maj_signal_prepped, const_candidates)
    return fa_ops_prepped, maj_signal_prepped, const_used


def _select_scaffold_layout(n, fa_ops, maj_signal, const1_names, num_fix: int, N_big: int):
    layouts = _scaffold_layout_sequences(n, num_fix, N_big)
    best = None
    for idx, (label, seq) in enumerate(layouts):
        mapping = _tokens_to_mapping(seq)
        mapped_ops, mapped_maj = _apply_mapping_to_netlist(fa_ops, maj_signal, mapping)
        mapped_ops, mapped_maj = _constant_fold_and_prune(mapped_ops, mapped_maj)
        const_used = _collect_const_names(mapped_ops, mapped_maj, const1_names)
        score = (len(mapped_ops), idx)
        if best is None or score < best['score']:
            best = {
                'score': score,
                'label': label,
                'mapping': mapping,
                'fa_ops': mapped_ops,
                'maj_signal': mapped_maj,
                'const1_names': const_used,
            }
    return best

# ======== 1) Proposed: Folded-Bias (CSA-only to bit w) ========
def emit_folded_bias(n: int):
    """
    CSA-only up to bit (w-1). Majority decision is the carry into 2^w
    (the last cout created at column w-1). No finishing CPA.
    """
    assert n % 2 == 1 and n >= 3
    th = (n + 1) // 2
    w  = math.ceil(math.log2(th))
    K  = (1 << w) - th

    # Build K constants per column < w
    consts = defaultdict(list)
    for j in range(w):
        if ((K >> j) & 1) == 1:
            consts[j].append(f"K{j}")

    # Run CSA macro
    raw_inputs = [f"x[{i}]" for i in range(n)]
    ops, wires, residual_by_col, const_decl = csa_macro_schedule_all_columns(raw_inputs, consts)

    # Extract final maj bit (last carry produced at column w-1)
    # Re-simulate the last column cheaply:
    # Build the column queue again to learn last cout
    from collections import deque as _dq
    col_bits = defaultdict(_dq)
    # collect carries from ops by column
    for col, kind, a, b, cin, s, k in ops:
        if col+1 >= 1:
            col_bits[col+1].append(k)
    # inject Ks
    if w > 0:
        for j in range(w):
            if ((K >> j) & 1) == 1:
                col_bits[j].append(f"K{j}")
    # last column is (w-1)
    last_cout = None
    def fold_for_last(queue):
        nonlocal last_cout
        if not queue: return
        acc = queue.popleft()
        while len(queue) >= 2:
            queue.popleft(); queue.popleft()
            last_cout = "temp_carry"  # just mark something non-None
        if len(queue) == 1:
            queue.popleft()
            last_cout = "temp_carry"

    if w == 0:
        maj_cout = "1'b0"
    else:
        q = _dq(col_bits.get(w-1, []))
        fold_for_last(q)
        # We don’t know the exact name without replaying IDs; use a robust rule:
        # In our ops list, the largest FA id at column (w-1) produced the last carry.
        last_k = None
        for col, kind, a, b, cin, s, k in ops:
            if col == (w-1):
                last_k = k
        maj_cout = last_k if last_k is not None else "1'b0"

    # Verilog (unchanged behavior)
    lines = []
    lines += _verilog_header(n, "Folded-Bias Majority (CSA-only, macro-structured)")
    lines.append(f"module maj_fb_{n} (input  wire [{n-1}:0] x, output wire maj);")
    lines.append(f"  // Parameters: th={th}, w={w}, K={K}")
    for j in range(w):
        if ((K >> j) & 1) == 1:
            lines.append(f"  wire K{j} = 1'b1;")

    if ops:
        lines.append("")
        lines.append("  // -------- CSA macro schedule --------")
        for (s,k) in wires:
            lines.append(f"  wire {s}, {k};")
        for (col, kind, a, b, cin, s, k) in ops:
            lines.append(f"  fa u_c{col}_{kind}_{s}(.a({a}), .b({b}), .cin({cin}), .sum({s}), .cout({k}));")

    lines.append("")
    lines.append(f"  assign maj = {maj_cout};")
    lines.append("endmodule")
    lines.append("")
    lines.append(f"// FA count (folded-bias, CSA-only) for n={n}: total={len(ops)}")
    fa_level_count = _fa_max_levels([(a, b, cin, s, k) for (_, _, a, b, cin, s, k) in ops])

    stats = {
        "n": n,
        "threshold": th,
        "w_bits": w,
        "bias_K": K,
        "K_bits_set": [j for j in range(w) if ((K >> j) & 1) == 1],
        "fa_count": len(ops),
        "fa_levels": fa_level_count,
        "maj_signal": maj_cout,
    }

    return "\n".join(lines), len(ops), ops, [f"K{j}" for j in range(w) if ((K >> j) & 1) == 1], maj_cout, stats


# ======== 2) Baseline STRICT (paper scaffold) ========
def emit_baseline_strict(n: int):
    """
    Literal paper flow:
      * Embed Maj_n into Maj_N with N = 2^p - 1 (p = ceil(log2(n+1))).
      * Fix (n_big - k) inputs to 1 and (n_big - k) inputs to 0 so the scaffold
        still has N inputs, where n_big = (N-1)//2 and k=(n-1)//2.
      * Build CSA HW tree on those N inputs.
      * Compare HW against Maj_N threshold by adding (th_N - 1) with Cin=1 and
        reading the final carry (overflow).
    """
    assert n % 2 == 1 and n >= 3

    p       = math.ceil(math.log2(n + 1))
    N       = (1 << p) - 1                    # scaffold input count (2^p - 1)
    m       = p                               # comparator width so that 2^m = N + 1
    th_N    = (N + 1) // 2                    # majority threshold for the scaffold
    k       = (n - 1) // 2
    n_big   = (N - 1) // 2
    num_fix = n_big - k                       # number of paired 1/0 constants to add
    assert num_fix >= 0

    # Build HW tree inputs: real signals + num_fix ones + num_fix zeros.
    hw_inputs = [f"x[{i}]" for i in range(n)]
    hw_inputs += ["1'b1"] * num_fix
    hw_inputs += ["1'b0"] * num_fix

    consts = defaultdict(list)  # no per-column constants in baseline
    ops, wires, residual_by_col, _ = csa_macro_schedule_all_columns(hw_inputs, consts)
    hw_bits = [residual_by_col.get(i, "1'b0") for i in range(m)]

    th_mask_bits = [((th_N - 1) >> j) & 1 for j in range(m)]

    lines = []
    lines += _verilog_header(n, "Baseline STRICT (paper scaffold): CSA (N=2^p-1) → HW + th_N - 1 + Cin")
    lines.append(f"module maj_baseline_strict_{n} (input  wire [{n-1}:0] x, output wire maj);")
    lines.append(f"  // Scaffold parameters: p={p}, N=2^{p}-1={N}, th_N={th_N}, paired constants={num_fix}")

    if ops:
        lines.append("")
        lines.append("  // -------- CSA macro schedule on scaffold inputs --------")
        for (s, ksig) in wires:
            lines.append(f"  wire {s}, {ksig};")
        for (col, kind, a, b, cin, s, ksig) in ops:
            lines.append(f"  fa u_c{col}_{kind}_{s}(.a({a}), .b({b}), .cin({cin}), .sum({s}), .cout({ksig}));")

    lines.append("")
    lines.append("  // -------- HW bits after CSA (single-rail) --------")
    for i in range(m):
        lines.append(f"  wire hw_{i} = {hw_bits[i]};")

    if any(th_mask_bits):
        lines.append("")
        lines.append("  // Threshold constant bits (th_N - 1)")
        for j, bit in enumerate(th_mask_bits):
            if bit:
                lines.append(f"  wire T{j} = 1'b1;")

    lines.append("")
    lines.append("  // -------- Full ripple (m bits) for HW + (th_N - 1) + Cin=1 --------")
    lines.append("  wire c2_0 = 1'b1; // Cin = 1 (paper comparator)")
    for i in range(m):
        b_term = f"T{i}" if th_mask_bits[i] else "1'b0"
        lines.append(f"  wire s2_{i}, c2_{i+1};")
        lines.append(f"  fa u_th_{i}(.a(hw_{i}), .b({b_term}), .cin(c2_{i}), .sum(s2_{i}), .cout(c2_{i+1}));")

    lines.append(f"  wire c2_m = c2_{m};")
    lines.append("")
    lines.append("  assign maj = c2_m;")
    lines.append("endmodule")
    lines.append("")

    total_fas = len(ops) + m
    lines.append(f"// FA count (baseline STRICT, scaffold) for n={n}: CSA={len(ops)}, CPA(th)={m}, total={total_fas}")

    # Collect FA ops (CSA + comparator) for optional BLIF logging
    fa_ops = [(a, b, cin, s, ksig) for (_, _, a, b, cin, s, ksig) in ops]
    for i in range(m):
        a   = f"hw_{i}"
        b   = f"T{i}" if th_mask_bits[i] else "1'b0"
        cin = f"c2_{i}" if i > 0 else "c2_0"
        s   = f"s2_{i}"
        c   = f"c2_{i+1}"
        fa_ops.append((a, b, cin, s, c))

    maj_out = f"c2_{m}"
    const1_names = ["c2_0"] + [f"T{j}" for j, bit in enumerate(th_mask_bits) if bit]
    csa_levels = _fa_max_levels([(a, b, cin, s, k) for (_, _, a, b, cin, s, k) in ops])
    total_levels = csa_levels + m  # ripple comparator adds m sequential FA levels

    stats = {
        "n": n,
        "threshold": (n + 1) // 2,
        "scaffold_p": p,
        "scaffold_inputs": N,
        "scaffold_threshold": th_N,
        "comparator_width": m,
        "num_fixed_pairs": num_fix,
        "cin_init": 1,
        "csa_fa_count": len(ops),
        "comparator_fa_count": m,
        "total_fa_count": total_fas,
        "csa_levels": csa_levels,
        "total_levels": total_levels,
        "maj_signal": maj_out,
    }

    return '\n'.join(lines), total_fas, fa_ops, const1_names, maj_out, stats

# ========================= BLIF SUPPORT (Canonical) =========================
def _sanitize(sig: str) -> str:
    """Make signal names BLIF-safe: x[3]->x3; keep 1'b0/1'b1 literal."""
    if sig in ("1'b0", "1'b1"):
        return sig
    return sig.replace('[','').replace(']','').replace(' ','_').replace('.', '_')

def _sorted3(a,b,c):
    """Return tuple of three signal names sorted alphabetically, and their permutation map."""
    lst = [a,b,c]
    srt = sorted(lst)
    perm = tuple(lst.index(srt[i]) for i in range(3))  # new_index -> old_index
    return tuple(srt), perm

def _permute_pattern(p, perm):
    """Permute a 3-bit pattern 'p' according to perm (length 3)."""
    if len(p) != 3: return p
    return "".join(p[perm[i]] for i in range(3))

def _emit_names_lines_for_const1(name):
    return [f".names {name}", "1"]

def _write_blif_from_fas_canonical(model_name, n, fa_ops, maj_signal, const1_names, path, maj_only=True):
    """
    Emit canonical BLIF:
      * Every 3-input gate sorts its inputs alphabetically.
      * Truth-table rows are minimal, deduped, and patterns are permuted to the sorted order.
      * Constants are explicit (.names CONST1\n1) and CONST0 created on-demand.
    FA expansion:
      - maj_only=True  -> 3x MAJ + 2x NOT per FA (cout MAJ(A,B,C); sum = MAJ(MAJ(~A,B,C), A, ~cout))
      - maj_only=False -> sum as XOR3; cout as MAJ3
    """
    inputs = [f"x{i}" for i in range(n)]
    out = [f".model {model_name}"]
    if inputs: out.append(".inputs " + " ".join(inputs))
    out.append(".outputs maj")

    used_const0 = False
    used_const1 = False

    # Named const-1 declarations
    const1_set = set()
    for k in (const1_names or []):
        ksan = _sanitize(k)
        if ksan not in const1_set:
            const1_set.add(ksan)
            out.extend(_emit_names_lines_for_const1(ksan))

    def map_in(sig):
        nonlocal used_const0, used_const1
        s = _sanitize(sig)
        if s == "1'b0":
            used_const0 = True
            return "CONST0"
        if s == "1'b1":
            used_const1 = True
            return "CONST1"
        if "[" in sig:
            return s.replace("[","").replace("]","")
        return s

    def emit_maj3(A,B,C,OUT, mask=None):
        na, nb, nc = (False, False, False) if mask is None else mask
        (A1,B1,C1), perm = _sorted3(A,B,C)
        mask_orig = [na, nb, nc]
        mask_sorted = [mask_orig[perm_idx] for perm_idx in perm]

        rows = []
        for a in (0, 1):
            for b in (0, 1):
                for c in (0, 1):
                    adjusted = (a ^ mask_sorted[0]) + (b ^ mask_sorted[1]) + (c ^ mask_sorted[2])
                    if adjusted >= 2:
                        rows.append(f"{a}{b}{c}")

        rows = sorted(set(rows))
        out.append(f".names {A1} {B1} {C1} {OUT}")
        for r in rows:
            out.append(f"{r} 1")

    def emit_xor3(A,B,C,S):
        # XOR3 canonical minterms (odd parity): 001,010,100,111
        (A1,B1,C1), perm = _sorted3(A,B,C)
        rows = ["001","010","100","111"]
        rows = [_permute_pattern(r, perm) for r in rows]
        out.append(f".names {A1} {B1} {C1} {S}")
        for r in rows:
            out.append(f"{r} 1")

    # Expand each FA
    for i,(a,b,cin,s,k) in enumerate(fa_ops):
        A = map_in(a); B = map_in(b); C = map_in(cin)
        S = _sanitize(s); K = _sanitize(k)

        if maj_only:
            # MAJ-only FA without explicit NOT nodes
            emit_maj3(A,B,C,K)
            op1  = f"fa{i}_op1";  emit_maj3(A,B,C,op1, mask=(True, False, False))
            emit_maj3(op1,A,K,S, mask=(False, False, True))
        else:
            emit_xor3(A,B,C,S)                 # sum
            emit_maj3(A,B,C,K)                 # cout

    # Literal constants
    if used_const1 and "CONST1" not in const1_set:
        out.extend(_emit_names_lines_for_const1("CONST1"))
    if used_const0:
        out.append(".names CONST0")  # const-0, no cubes

    # Connect top output
    out.append(f".names {_sanitize(maj_signal)} maj")
    out.append("1 1")
    out.append(".end")

    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        f.write("\n".join(out))

# ---------- build BLIF netlists from FA ops ----------
def build_folded_bias_netlist(n: int):
    """Return (fa_ops, const1_names, maj_out) for folded-bias CSA-only design.

    fa_ops: list of 5-tuples (a, b, cin, s, k)
    const1_names: list of named CONST1 signals (e.g., K0, K1, ...)
    maj_out: signal name of the final majority decision (last cout at column w-1)
    """
    assert n % 2 == 1 and n >= 3
    import math
    from collections import deque, defaultdict

    th = (n + 1) // 2
    w  = math.ceil(math.log2(th))
    K  = (1 << w) - th

    const1_names = [f"K{j}" for j in range(w) if ((K >> j) & 1) == 1]

    fa_id = 0
    fa_ops = []
    last_cout_wm1 = None  # <-- track the last carry created specifically at column (w-1)

    def new_wires(col, tag=""):
        nonlocal fa_id, last_cout_wm1
        s = f"{tag}s_c{col}_{fa_id}"
        k = f"{tag}c_c{col}_{fa_id}"
        fa_id += 1
        # remember the most recent carry created in column (w-1)
        if col == (w - 1):
            last_cout_wm1 = k
        return s, k

    raw = [f"x[{i}]" for i in range(n)]
    col0_sums = deque()
    col_bits  = {1: deque()}

    # Stage A: raw triples at col 0
    while len(raw) >= 3:
        a = raw.pop(0); b = raw.pop(0); c = raw.pop(0)
        s, k = new_wires(0, "raw_")
        fa_ops.append((a, b, c, s, k))
        col0_sums.append(s)
        col_bits[1].append(k)

    # Fold column 0 (+K0 if set)
    col0_queue = deque(list(col0_sums) + raw)
    if ((K >> 0) & 1) == 1:
        col0_queue.append("K0")

    def fold_column(col, queue):
        if not queue:
            return None, []
        carries_out = []
        acc = queue.popleft()
        while len(queue) >= 2:
            b = queue.popleft()
            c = queue.popleft()
            s, k = new_wires(col, "")
            fa_ops.append((acc, b, c, s, k))
            carries_out.append(k)
            acc = s
        if len(queue) == 1:
            b = queue.popleft()
            s, k = new_wires(col, "p_")
            fa_ops.append((acc, b, "1'b0", s, k))
            carries_out.append(k)
            acc = s
        return acc, carries_out

    _, carries_to_1 = fold_column(0, col0_queue)
    for k in carries_to_1:
        col_bits.setdefault(1, deque()).append(k)

    # Columns 1 .. w-2 (serial fold)
    for j in range(1, max(1, w - 1)):
        qj = col_bits.get(j, deque())
        if ((K >> j) & 1) == 1:
            qj.append(f"K{j}")
        _, carries_to_next = fold_column(j, qj)
        if carries_to_next:
            col_bits.setdefault(j + 1, deque()).extend(carries_to_next)

    # Final decision is the LAST carry created at column (w-1)
    if w == 0:
        maj_out = "1'b0"
    else:
        # Ensure we actually fold column (w-1) so last_cout_wm1 gets set when needed
        q = col_bits.get(w - 1, deque())
        if ((K >> (w - 1)) & 1) == 1:
            q.append(f"K{w-1}")
        # If there's work, perform one more fold to generate couts at col (w-1)
        if len(q) >= 1:
            _, _ = fold_column(w - 1, q)
        maj_out = last_cout_wm1 if last_cout_wm1 is not None else "1'b0"

    return fa_ops, const1_names, maj_out





def emit_folded_bias_majpath_wrapper(n: int, N_big: int, mapping, layout_label: str):
    lines = []
    lines += _verilog_header(n, "Folded-Bias Majority (Maj-path constant fixing)")
    lines.append(f"module maj_fb_majpath_{n} (input  wire [{n-1}:0] x, output wire maj);")
    lines.append(f"  // Derived from maj_fb_{N_big} with layout='{layout_label}'")
    lines.append(f"  wire [{N_big-1}:0] x_big;")
    for idx, source in enumerate(mapping):
        lines.append(f"  assign x_big[{idx}] = {source};")
    lines.append(f"  maj_fb_{N_big} u_fb_big(.x(x_big), .maj(maj));")
    lines.append("endmodule")
    lines.append("")
    return '\n'.join(lines)


def emit_baseline_majpath_wrapper(n: int, N_big: int, mapping, layout_label: str):
    lines = []
    lines += _verilog_header(n, "Baseline STRICT (Maj-path constant fixing)")
    lines.append(f"module maj_baseline_majpath_{n} (input  wire [{n-1}:0] x, output wire maj);")
    lines.append(f"  // Derived from maj_baseline_strict_{N_big} with layout='{layout_label}'")
    lines.append(f"  wire [{N_big-1}:0] x_big;")
    for idx, source in enumerate(mapping):
        lines.append(f"  assign x_big[{idx}] = {source};")
    lines.append(f"  maj_baseline_strict_{N_big} u_base_big(.x(x_big), .maj(maj));")
    lines.append("endmodule")
    lines.append("")
    return '\n'.join(lines)

def build_baseline_strict_netlist(n: int):
    assert n % 2 == 1 and n >= 3

    p       = math.ceil(math.log2(n + 1))
    N       = (1 << p) - 1
    m       = p
    th_N    = (N + 1) // 2
    k       = (n - 1) // 2
    n_big   = (N - 1) // 2
    num_fix = n_big - k
    assert num_fix >= 0

    hw_inputs = [f"x[{i}]" for i in range(n)]
    hw_inputs += ["1'b1"] * num_fix
    hw_inputs += ["1'b0"] * num_fix

    consts = defaultdict(list)
    ops, wires, residual_by_col, _ = csa_macro_schedule_all_columns(hw_inputs, consts)

    fa_ops = [(a, b, cin, s, ksig) for (_, _, a, b, cin, s, ksig) in ops]

    th_mask_bits = [((th_N - 1) >> j) & 1 for j in range(m)]
    hw_bits = [residual_by_col.get(i, "1'b0") for i in range(m)]
    for i in range(m):
        a   = hw_bits[i]
        b   = f"T{i}" if th_mask_bits[i] else "1'b0"
        cin = f"c2_{i}" if i > 0 else "c2_0"
        s   = f"s2_{i}"
        c   = f"c2_{i+1}"
        fa_ops.append((a, b, cin, s, c))

    const1_names = ["c2_0"] + [f"T{j}" for j, bit in enumerate(th_mask_bits) if bit]
    maj_out = f"c2_{m}"
    return fa_ops, const1_names, maj_out

# ---------- main ----------
def main():
    assert N >= 3 and (N % 2 == 1), "N must be odd and >= 3"

    modules = []
    emitted = set()
    counts = []
    fb_stats = None
    bs_stats = None

    def add_module(src: str, name: str):
        if src and name not in emitted:
            modules.append(src)
            emitted.add(name)

    banner = [
        "// Auto-generated majority circuits (canonical BLIF emission)",
        f"// n = {N}",
        "// Top modules present (depending on config):",
        "//   - maj_fb_<n>                (folded-bias; CSA-only, macro schedule)",
        "//   - maj_baseline_strict_<n>   (baseline threshold path)",
        "//   - maj_fb_majpath_<n>        (folded-bias; scaffold constant-fix)",
        "//   - maj_baseline_majpath_<n>  (baseline STRICT; scaffold constant-fix)",
        "// You must provide: module fa(input a,b,cin, output sum,cout);",
        ""
    ]

    p_scaffold, N_scaffold, _, num_fix_pairs = _scaffold_params(N)

    fb_direct_data = None
    bs_direct_data = None
    fb_maj_data = None
    bs_maj_data = None

    if INCLUDE_FOLDED_BIAS:
        v_fb, cnt_fb, _, _, _, fb_stats = emit_folded_bias(N)
        add_module(v_fb, f"maj_fb_{N}")
        counts.append(("folded_bias", cnt_fb))
        fb_direct_data = build_folded_bias_netlist(N)

    if INCLUDE_BASELINE_STRICT:
        v_bs, cnt_bs, _, _, _, bs_stats = emit_baseline_strict(N)
        add_module(v_bs, f"maj_baseline_strict_{N}")
        counts.append(("baseline_strict", cnt_bs))
        bs_direct_data = build_baseline_strict_netlist(N)

    if INCLUDE_FOLDED_BIAS_MAJP and num_fix_pairs > 0:
        fb_big_ops, fb_big_const, fb_big_out = build_folded_bias_netlist(N_scaffold)
        fb_selection = _select_scaffold_layout(N, fb_big_ops, fb_big_out, fb_big_const, num_fix_pairs, N_scaffold)
        fb_maj_data = fb_selection
        if N_scaffold != N or not INCLUDE_FOLDED_BIAS:
            v_fb_big, _, _, _, _, _ = emit_folded_bias(N_scaffold)
            add_module(v_fb_big, f"maj_fb_{N_scaffold}")
        wrapper = emit_folded_bias_majpath_wrapper(N, N_scaffold, fb_selection['mapping'], fb_selection['label'])
        add_module(wrapper, f"maj_fb_majpath_{N}")
        counts.append(("folded_bias_majpath", len(fb_selection['fa_ops'])))

    if INCLUDE_BASELINE_MAJP and num_fix_pairs > 0:
        bs_big_ops, bs_big_const, bs_big_out = build_baseline_strict_netlist(N_scaffold)
        bs_selection = _select_scaffold_layout(N, bs_big_ops, bs_big_out, bs_big_const, num_fix_pairs, N_scaffold)
        bs_maj_data = bs_selection
        if N_scaffold != N or not INCLUDE_BASELINE_STRICT:
            v_bs_big, _, _, _, _, _ = emit_baseline_strict(N_scaffold)
            add_module(v_bs_big, f"maj_baseline_strict_{N_scaffold}")
        wrapper = emit_baseline_majpath_wrapper(N, N_scaffold, bs_selection['mapping'], bs_selection['label'])
        add_module(wrapper, f"maj_baseline_majpath_{N}")
        counts.append(("baseline_majpath", len(bs_selection['fa_ops'])))

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    out_v = os.path.join(OUTPUT_DIR, OUTPUT_NAME)
    with open(out_v, "w") as f:
        f.write("\n".join(banner + modules))
    print("Wrote Verilog:", out_v)
    for name, cnt in counts:
        print(f"FA count [{name}]: {cnt}")

    def _print_stats(title: str, stats):
        if not stats:
            return
        print(f"\n[{title}]")
        for key, value in stats.items():
            if isinstance(value, list):
                formatted = ", ".join(str(v) for v in value) if value else "-"
            else:
                formatted = value
            print(f"  {key}: {formatted}")

    if INCLUDE_FOLDED_BIAS:
        _print_stats("Folded-Bias Stats", fb_stats)
    if INCLUDE_BASELINE_STRICT:
        _print_stats("Baseline STRICT Stats", bs_stats)

    if INCLUDE_FOLDED_BIAS and fb_direct_data is not None:
        fb_fa_ops, fb_const1, fb_out = fb_direct_data
        fb_fa_ops, fb_out, fb_const_used = _prepare_for_emit(fb_fa_ops, fb_out, fb_const1)
        fb_blif = os.path.join(OUTPUT_DIR, f"maj_fb_{N}.blif")
        _write_blif_from_fas_canonical(
            model_name=f"maj_fb_{N}",
            n=N,
            fa_ops=fb_fa_ops,
            maj_signal=fb_out,
            const1_names=fb_const_used,
            path=fb_blif,
            maj_only=MAJ_ONLY_FA,
        )
        print("Wrote BLIF (folded-bias threshold):", fb_blif)

    if INCLUDE_BASELINE_STRICT and bs_direct_data is not None:
        bs_fa_ops, bs_const1, bs_out = bs_direct_data
        bs_fa_ops, bs_out, bs_const_used = _prepare_for_emit(bs_fa_ops, bs_out, bs_const1)
        bs_blif = os.path.join(OUTPUT_DIR, f"maj_baseline_strict_{N}.blif")
        _write_blif_from_fas_canonical(
            model_name=f"maj_baseline_strict_{N}",
            n=N,
            fa_ops=bs_fa_ops,
            maj_signal=bs_out,
            const1_names=bs_const_used,
            path=bs_blif,
            maj_only=MAJ_ONLY_FA,
        )
        print("Wrote BLIF (baseline threshold):", bs_blif)

    if INCLUDE_FOLDED_BIAS_MAJP and fb_maj_data is not None:
        fb_ops, fb_sig, fb_consts = fb_maj_data['fa_ops'], fb_maj_data['maj_signal'], fb_maj_data['const1_names']
        fb_blif = os.path.join(OUTPUT_DIR, f"maj_fb_majpath_{N}.blif")
        _write_blif_from_fas_canonical(
            model_name=f"maj_fb_majpath_{N}",
            n=N,
            fa_ops=fb_ops,
            maj_signal=fb_sig,
            const1_names=fb_consts,
            path=fb_blif,
            maj_only=MAJ_ONLY_FA,
        )
        print("Wrote BLIF (folded-bias maj-path):", fb_blif)

    if INCLUDE_BASELINE_MAJP and bs_maj_data is not None:
        bs_ops, bs_sig, bs_consts = bs_maj_data['fa_ops'], bs_maj_data['maj_signal'], bs_maj_data['const1_names']
        bs_blif = os.path.join(OUTPUT_DIR, f"maj_baseline_majpath_{N}.blif")
        _write_blif_from_fas_canonical(
            model_name=f"maj_baseline_majpath_{N}",
            n=N,
            fa_ops=bs_ops,
            maj_signal=bs_sig,
            const1_names=bs_consts,
            path=bs_blif,
            maj_only=MAJ_ONLY_FA,
        )
        print("Wrote BLIF (baseline maj-path):", bs_blif)

if __name__ == "__main__":
    main()
