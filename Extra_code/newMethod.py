from itertools import product
from collections import defaultdict
import math

def majority_n_folded_bias(m, verbose=False, print_all=False):
    # Parameters for m=7
    # m = 1  # Number of bits
    th = (m + 1) // 2  # ceil(m/2) for majority; for m=7, th=4
    # Choose minimal w so that 2^w > th - 1
    # A sufficient and common choice: w = ceil(log2(th)) but we avoid math import
    w = int(math.ceil(math.log2(th)))
    while (1 << w) <= (th - 1):
        w += 1
    # Bias constant
    K = (1 << w) - th  # K = 2^w - th
    # Prepare K's bit list (LSB first)
    K_bits = [(K >> j) & 1 for j in range(w)]  # Only 0..w-1 used

    if verbose:
        print(f"m={m}, th={th}, w={w}, 2^w={1<<w}, K={K} (bits LSB->MSB: {K_bits})")

    def reduce_columns_to_two_rows(col_counts):
        """
        Given a dict column_index -> integer count of single-bit '1's in that column,
        reduce using exact 3:2 compressors (full adders) until at most 2 bits remain per column.
        This models a CSA tree in terms of counts only (no approximations).
        Returns two binary rows (as integers) encoding the same value.
        """
        # We’ll iteratively apply "carry the third bit up" until each column count <= 2
        cols = dict(col_counts)  # copy
        while True:
            changed = False
            # Work on a bounded range of columns
            keys = list(cols.keys())
            if not keys:
                break
            for i in range(min(keys), max(keys)+1):
                c = cols.get(i, 0)
                if c >= 3:
                    # Every triple in column i becomes 1 bit in i and 1 bit in i+1:
                    triple = c // 3
                    rem = c % 3
                    cols[i] = rem + triple  # rem + the 'sum' bits from triples
                    cols[i+1] = cols.get(i+1, 0) + triple  # carry bits into higher column
                    changed = True
            if not changed:
                break

            # After one sweep, there still might be columns with >2 due to carries; continue loops.

        # Now each column has 0,1, or 2 bits left. Create two rows by assigning bits.
        rowA = 0
        rowB = 0
        for i, c in cols.items():
            if c >= 1:
                rowA |= (1 << i)
            if c >= 2:
                rowB |= (1 << i)
        return rowA, rowB

    def simulate_once(x_bits, verbose_local=False):
        # x_bits: tuple/list of m bits (each 0/1)
        HW = sum(x_bits)

        # Build initial column counts: all input ones in column 0
        col_counts = defaultdict(int)
        col_counts[0] = HW

        # Inject K bits into their columns
        for j, kb in enumerate(K_bits):
            if kb == 1:
                col_counts[j] += 1

        if verbose_local:
            print(f"Input {''.join(map(str, x_bits))} HW={HW}, initial columns:", dict(col_counts))

        # Reduce to two rows via CSA-style counting
        rowA, rowB = reduce_columns_to_two_rows(col_counts)

        # The two rows represent HW + K exactly: value = rowA + rowB
        value = rowA + rowB

        # Majority should be 1 iff HW >= th
        majority_truth = 1 if HW >= th else 0

        # Detect "carry into column 2^w": i.e., value >= 2^w
        carry_into_2w = 1 if value >= (1 << w) else 0

        if verbose_local:
            # Show small finishing add equivalently:
            print(f"rowA bin: {rowA:0{w+2}b}  rowB bin: {rowB:0{w+2}b}")
            print(f"value={value} (bin {value:0{w+2}b}), carry_into_2^w={carry_into_2w}, truth={majority_truth}")

        return {
            "inputs": ''.join(map(str, x_bits)),
            "HW": HW,
            "rowA": rowA,
            "rowB": rowB,
            "value": value,
            "carry_pred": carry_into_2w,
            "truth": majority_truth,
            "match": (carry_into_2w == majority_truth),
        }

    # Iterate all inputs and test
    rows = [simulate_once(bits) for bits in product([0,1], repeat=m)]

    mismatches = [r for r in rows if not r["match"]]
    print(f"Total combos: {2**m}")
    print(f"Mismatches: {len(mismatches)}")
    if mismatches:
        print("Sample mismatches (up to 10):")
        for r in mismatches[:10]:
            print(r)
    else:
        print("All combinations matched.")

    # Error count by HW
    by_hw = defaultdict(lambda: {"total": 0, "errors": 0})
    for r in rows:
        h = r["HW"]
        by_hw[h]["total"] += 1
        if not r["match"]:
            by_hw[h]["errors"] += 1

    print("\nError count by HW:")
    for h in range(0, m+1):
        print(f"HW={h}: {by_hw[h]['errors']} errors out of {by_hw[h]['total']}")

    if print_all:
        print("\nAll rows:")
        for r in rows:
            print(r)

if __name__ == "__main__":
    # Set verbose=True to see parameters; print_all=True to dump all rows
    majority_n_folded_bias(m = 17,verbose=1, print_all=0)
 