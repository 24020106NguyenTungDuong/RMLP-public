"""Baseline [27] of the paper: the upper bound on rmn(C_n) of Theorem 2 of Saraswathi and Meera,
"Comments on 'An Integer Linear Programming Model for Solving Radio Mean Labeling Problem'",
IEEE Access 10:72206-72210, 2022 (Cases I-IV of its Section IV).

For n = 10..50 this script
  1. evaluates Theorem 2 (bound_n; for n <= 9 the theorem gives rmn(C_n) = n),
  2. rebuilds the labeling of Section IV for every l and checks it against definition (1)
     (with the fixed order and 20 random orders of the remaining vertices, which [27] lets
     be labeled in any order),
  3. records the smallest span a valid construction reaches.
The bound is the [27] column of Table 4 (for n <= 9: n). Writes saraswathi2022_theorem2.csv.
"""

import csv
import math
import os
import random

HERE = os.path.dirname(os.path.abspath(__file__))


def distance(i, j, n):
    dis = abs(i - j)
    if dis > math.floor(n / 2):
        dis = n - dis
    return dis


def compute_d(n, h, mode, max_i):
    """mode 0,1,3 use the decreasing recurrence (Cases I, II, IV);
    mode 2 uses the increasing recurrence (Case III)."""
    d = [0] * (max_i + 2)
    if mode in (0, 1, 3):
        d[0] = n - h - 2
        for i in range(1, max_i + 2):
            d[i] = d[i - 1] - 2 - i
    else:  # mode == 2
        d[0] = h + 4
        for i in range(1, max_i + 2):
            d[i] = d[i - 1] + 2 + i
    return d


def condition(d, l, h, n, mode, offset):
    dv = d[l]
    if mode in (0, 1):
        base = h + 1
        ok = dv > base
    elif mode == 2:
        base = n - h
        ok = dv < base
    else:  # mode == 3
        base = h + 2
        ok = dv > base
    if not ok:
        return False
    thresh = math.floor(n / 2) + 1 - math.ceil(n - 2 * h - (offset + l) / 2)
    return distance(dv, base, n) >= thresh


def find_l(n, h, mode, offset, max_i=1000):
    """l = greatest i >= 0 such that condition(i) holds and condition(i+1) fails."""
    d = compute_d(n, h, mode, max_i)
    l = 0
    while True:
        if condition(d, l, h, n, mode, offset) and not condition(d, l + 1, h, n, mode, offset):
            return l
        l += 1
        if l > max_i:
            raise RuntimeError(f"n={n}: could not locate l within {max_i} steps")


def bound_n(n):
    # Theorem 2, part 1: rmn(C_n) = n for n <= 9
    if n <= 9:
        return n

    h = math.floor(n / 4)
    r = n % 4
    # Theorem 2, parts 2-4: n >= 10
    if r == 0:
        l = find_l(n, h, mode=0, offset=2)
        return 2 * n - 2 * h - l - 4
    elif r == 1:
        l = find_l(n, h, mode=1, offset=5)
        return 2 * n - 2 * h - l - 5
    elif r == 2:
        l = find_l(n, h, mode=2, offset=5)
        return 2 * n - 2 * h - l - 5
    else:  # r == 3
        l = find_l(n, h, mode=3, offset=7)
        return 2 * n - 2 * h - l - 6



# Label of v_{d_i}, per residue n mod 4 (h = floor(n/4)).
D_LABEL = {
    0: lambda n, h, l, i: n - 2 * h - 2 - i,
    1: lambda n, h, l, i: n - 2 * h - 3 - i,
    2: lambda n, h, l, i: n - 2 * h - 3 - i,
    3: lambda n, h, l, i: n - 2 * h - 4 - i,
}


def build(n, l, d_label, seed=None):
    """gamma from [27] Sec. IV as a list indexed v_1..v_n, or None if the
    positional indices d_i leave the cycle or collide with fixed vertices."""
    h, r = n // 4, n % 4
    g = {1: 1}
    if r == 2:
        d = [h + 4]
        for i in range(1, l + 1):
            d.append(d[-1] + 2 + i)
    else:
        d = [n - h - 2]
        for i in range(1, l + 1):
            d.append(d[-1] - 2 - i)
    top = h + 1 if r in (0, 1) else h + 2
    for i in range(2, top + 1):
        g[i] = {0: n - 2 * i + 2, 1: n - 2 * i + 1, 2: n - 2 * i + 3, 3: n - 2 * i + 1}[r]
    for i in range(n - h, n + 1):
        g[i] = 2 * i - n - 1 if r == 0 else 2 * i - n - 2
    for i in range(l + 1):
        if not 1 <= d[i] <= n or d[i] in g:
            return None
        g[d[i]] = d_label(n, h, l, i)
    rest = [v for v in range(1, n + 1) if v not in g]
    labels = list(range(n if r in (0, 2) else n - 1, (n if r in (0, 2) else n - 1) + len(rest)))
    if seed is not None:          # [27]: V' may be labeled in any order
        random.Random(seed).shuffle(labels)
    g.update(zip(rest, labels))
    return [g[v] for v in range(1, n + 1)]


def is_rml(n, h):
    diam = n // 2
    if len(set(h)) != n or min(h) < 1:
        return False
    for u in range(n):
        for v in range(u + 1, n):
            d = min(v - u, n - (v - u))
            if -(-(h[u] + h[v]) // 2) < diam + 1 - d:
                return False
    return True


def best_span(n, d_label):
    """Smallest span over l whose construction is valid for the fixed and 20
    shuffled V' orders."""
    best = None
    for l in range(0, n):
        if build(n, l, d_label) is None:
            continue
        if all(is_rml(n, build(n, l, d_label, s)) for s in [None] + list(range(20))):
            span = max(build(n, l, d_label))
            best = span if best is None else min(best, span)
    return best


def main():
    with open(os.path.join(HERE, "saraswathi2022_theorem2.csv"), "w", newline="") as f:
        wr = csv.writer(f)
        wr.writerow(["n", "theorem2_bound", "best_valid_span", "construction_reaches_bound"])
        for n in range(10, 51):
            bound = bound_n(n)
            span = best_span(n, D_LABEL[n % 4])
            wr.writerow([n, bound, span, span == bound])
            print(n, bound, span, flush=True)


if __name__ == "__main__":
    main()
