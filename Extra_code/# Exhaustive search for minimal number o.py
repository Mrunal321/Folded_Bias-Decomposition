from itertools import product

# ----------------------------------
# Majority gate
# ----------------------------------
def M(a, b, c):
    return (a & b) | (b & c) | (a & c)

# ----------------------------------
# MG-EC Macro for 4 inputs using only majority logic
# ----------------------------------
def mg_ec(a, b, c, d):
    # Sum bit (XOR of all inputs)
    S = a ^ b ^ c ^ d

    # High carry (2^2 place)
    # C = a & b & c & d 
    C = M(M(M(a, b, 0), c, 0),d,0)

    # Low carry (2^1 place) — must be 1 if total is 2 or 3
    # T = M( M(a, b, c), M(a, b, d), M(a, c, d) ) | M(b, c, d)
    # K = T &  ~C
    X = M(a, b, c)
    Y = M(a, d, M(b,c,1))  # uses OR
    T = M(X,Y,1)
    K = M(T, 0, (~C))
    return S, K, C

# ----------------------------------
# Truth Table & Verification
# ----------------------------------
print("a b c d | C  K  S | Check")
print("-" * 32)
bad_rows = []

for a, b, c, d in product([0, 1], repeat=4):
    S, K, C = mg_ec(a, b, c, d)
    total = a + b + c + d
    check_ok = (S + 2*K + 4*C) == total
    print(f"{a} {b} {c} {d} | {C}  {K}  {S} | {'OK' if check_ok else 'BAD'}")
    if not check_ok:
        bad_rows.append(((a, b, c, d), (C, K, S), total))

print("\nVerification:", "ALL OK" if not bad_rows else f"{len(bad_rows)} BAD ROWS")
if bad_rows:
    for row in bad_rows:
        print(row)
