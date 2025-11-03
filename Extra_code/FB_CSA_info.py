from collections import defaultdict

def analyze_csa(n):
    # Initial: all ones in column 0
    columns = defaultdict(int)
    columns[0] = n  # All n inputs in col 0
    fa_count = 0
    levels = 0

    print(f"Starting CSA reduction for n={n}")
    print(f"Initial columns: {dict(columns)}")

    # Perform reduction
    while True:
        changed = False
        new_columns = columns.copy()
        for i in sorted(columns.keys()):
            while new_columns[i] >= 3:
                # Apply one full adder (3:2)
                new_columns[i] -= 3
                new_columns[i] += 1  # sum bit
                new_columns[i+1] += 1  # carry bit
                fa_count += 1
                changed = True
        columns = new_columns
        if changed:
            levels += 1
        else:
            break

    # Now columns have at most 2 tokens each
    row_a = sum(1 for v in columns.values() if v >= 1)
    row_b = sum(1 for v in columns.values() if v >= 2)
    max_col = max(columns.keys())

    print("\nFinal state after CSA:")
    print(f"Columns: {dict(columns)}")
    print(f"Levels of FA used: {levels}")
    print(f"Total FAs: {fa_count}")
    print(f"Row A bits: {row_a}, Row B bits: {row_b}")
    print(f"Max column index: {max_col} (width ~ {max_col+1} bits)")

    return {
        "n": n,
        "levels": levels,
        "fa_count": fa_count,
        "row_a_bits": row_a,
        "row_b_bits": row_b,
        "width": max_col+1
    }

# Test for n = 5 and n = 7
analyze_csa(5)
print()
analyze_csa(7)
analyze_csa(9)
