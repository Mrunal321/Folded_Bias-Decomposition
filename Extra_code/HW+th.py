# Running the corrected simulation: use K = 2^w - th and check carry-out (Cin=0).
import math
from itertools import product

def add_with_cout(a, b, bits):
    # """Binary addition of a and b with fixed 'bits' width; return carry-out."""
    carry = 0
    for i in range(bits):
        abit = (a >> i) & 1
        bbit = (b >> i) & 1
        total = abit + bbit + carry
        carry = 1 if total >= 2 else 0
    return carry

def test_K_corrected(ns):
    results = []
    for n in ns:
        th = math.ceil(n / 2)
        hw_bits = math.ceil(math.log2(n + 1))  # bits to represent HW (0..n)
        w = hw_bits
        K = (1 << w) - th  # correct bias for w-bit adder
        Cin = 0
        
        mismatches = []
        for bits in product([0,1], repeat=n):
            HW = sum(bits)
            majority_truth = 1 if HW >= th else 0
            cout = add_with_cout(HW, K + Cin, w)
            if cout != majority_truth:
                mismatches.append((bits, HW, th, w, K, cout, majority_truth))
        
        results.append((n, th, w, K, len(mismatches), mismatches[:8]))  # store first few mismatches if any
    return results

ns = [3,5,7,11]
res = test_K_corrected(ns)

for r in res:
    n, th, w, K, mism_count, sample = r
    if mism_count == 0:
        print(f"n={n}: All combinations matched ✅ (th={th}, w={w}, K={K})")
    else:
        print(f"n={n}: {mism_count} mismatches ❌ (th={th}, w={w}, K={K})")
        for entry in sample:
            bits, HW, th, w, K, cout, maj = entry
            print(f"  Sample mismatch: Input={bits}, HW={HW}, th={th}, w={w}, K={K}, cout={cout}, correct={maj}")

# Return the result object for inspection if needed
res

