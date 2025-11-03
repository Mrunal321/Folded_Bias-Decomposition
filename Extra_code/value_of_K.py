import math

def compute_folded_bias(n_values):
    print(f"{'n':>5} | {'th':>5} | {'w':>5} | {'2^w':>5} | {'K':>10} | {'K (bin)':>15}")
    print("-" * 55)
    for n in n_values:
        th = (n + 1) // 2  # Majority threshold = ceil(n/2)
        w = math.ceil(math.log2(th))  # minimal w so that 2^w >= th
        while (1 << w) <= (th - 1):  # ensure 2^w > th-1
            w += 1
        two_pow_w = 1 << w
        K = two_pow_w - th
        print(f"{n:5d} | {th:5d} | {w:5d} | {two_pow_w:5d} | {K:10d} | {bin(K):>15}")

# Example usage:
n_list = [5, 7, 9, 11, 13, 15, 17, 19, 21,23,25,27,29,31,33,35,37,39,41,43,45,47,49,51,53,55,57,59,61,63]

compute_folded_bias(n_list)
