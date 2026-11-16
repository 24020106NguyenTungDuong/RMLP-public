"""Baseline [14] of the paper: Algorithm 1 of Saraswathi, Meera and Lin, "Radio Mean Labeling
Algorithm, Its Complexity and Existence Results", Mathematics 13(13):2057, 2025.

Implemented step by step (its Section 3.2):
  * label the diametral path v_1..v_{d+1} (steps 5-39, the path labeling of [26]);
  * place labels of S = {1..r} minus the path labels on unlabeled vertices (steps 47-66). The
    text after its Figure 3 prescribes: "we must check for all possible ways of labeling vertices
    of V(G) minus V(P) with elements of S and maximum number of elements of S must be used". We do
    exactly that: each label of S on at most one vertex, each vertex at most one label, the radio
    mean condition against the path and between the placed vertices, and the number of placed
    labels maximised, solved exactly as a MaxSAT problem (PySAT RC2);
  * give the remaining vertices r+1, r+2, ... (steps 67-72); their order does not change the
    span r + |U|.
For P_n the diametral path is the whole graph, so the span is r.

Every labeling produced is checked against definition (1). Results are compared with the values
printed in [14] (n <= 30); they agree except C_29, where the algorithm gives 36 and [14] prints 37.
Writes saraswathi2025_algorithm1.csv next to this script (the [14] column of Tables 4-5).
"""

import csv
import os

HERE = os.path.dirname(os.path.abspath(__file__))

# Values printed in [14] for C_n (n=5..30) and P_n (n=3..30), as in the first submission's tables.
PAPER_13_CYCLE = dict(zip(range(5, 31), [5, 6, 7, 9, 9, 11, 12, 14, 14, 16, 17, 19, 20, 22,
                                         23, 24, 25, 27, 28, 30, 31, 33, 34, 36, 37, 38]))
PAPER_13_PATH = dict(zip(range(3, 31), [3, 4, 6, 8, 9, 11, 13, 15, 16, 18, 20, 22, 24, 25,
                                        27, 29, 31, 33, 35, 36, 38, 40, 42, 44, 46, 48,
                                        49, 51]))


def label_diametral_path(d):
    """Steps 5-39: labels R[1..d+1] of the path v_1..v_{d+1}."""
    R = {}
    if d + 1 in (2, 3):
        for j in range(1, d + 2):
            R[j] = j
    elif d + 1 in (4, 5, 6):
        R[1], R[2], R[3] = d - 2, 2 * d - 2, d - 1
        for j in range(4, d + 2):
            R[j] = 2 * d + 1 - j
    else:
        m = 1
        while not (4 + m * (m + 5) // 2 <= d + 1 <= 6 + m * (m + 5) // 2 + m):
            m += 1
        p = {1: 1}
        R[1] = d - m - 2
        for j in range(2, m + 3):
            p[j] = d + p[j - 1] - R[p[j - 1]]
            R[p[j]] = d + j - m - 3
        for j in range(p[m + 2] + 1, d + 2):
            R[j] = 2 * d - j + 1
        for l in range(m + 2, 1, -1):
            for j in range(p[l - 1] + 1, p[l]):
                R[j] = R[p[l] + 1] - j + p[l]
    return R


def ok_pair(a, b, dist, diam):
    return -(-(a + b) // 2) + dist >= diam + 1


def algorithm1(n, dist, diam):
    """Labels h[0..n-1] (vertex v_{i+1} is index i) for a graph whose
    diametral path is v_1..v_{d+1}."""
    R = {j - 1: x for j, x in label_diametral_path(diam).items()}
    r = max(R.values())
    if len(R) < n:
        unlabeled = [u for u in range(n) if u not in R]
        S = sorted(set(range(1, r + 1)) - set(R.values()))
        for u, s in max_placement(S, unlabeled, R, dist, diam).items():
            R[u] = s
        for u in unlabeled:
            if u not in R:
                r += 1
                R[u] = r
    return [R[i] for i in range(n)]


def max_placement(S, U, R, dist, diam):
    """Steps 47-66 with the maximum number of labels of S used: {vertex: label}."""
    from itertools import combinations
    from pysat.card import CardEnc
    from pysat.examples.rc2 import RC2
    from pysat.formula import WCNF
    var = {}
    for s in S:
        for u in U:
            if all(ok_pair(s, R[v], dist(u, v), diam) for v in R):
                var[(s, u)] = len(var) + 1
    if not var:
        return {}
    w, top = WCNF(), len(var)
    groups = [[var[(s, u)] for u in U if (s, u) in var] for s in S] + \
             [[var[(s, u)] for s in S if (s, u) in var] for u in U]
    for lits in groups:
        if len(lits) > 1:
            enc = CardEnc.atmost(lits, 1, top_id=top)
            top = max(top, enc.nv)
            for cl in enc.clauses:
                w.append(cl)
    for (s, u), (t, x) in combinations(var, 2):
        if u != x and s != t and not ok_pair(s, t, dist(u, x), diam):
            w.append([-var[(s, u)], -var[(t, x)]])
    for lit in var.values():
        w.append([lit], weight=1)
    with RC2(w) as rc2:
        model = set(rc2.compute())
    return {u: s for (s, u), lit in var.items() if lit in model}


def is_rml(h, dist, diam):
    n = len(h)
    return len(set(h)) == n and min(h) >= 1 and all(
        ok_pair(h[u], h[v], dist(u, v), diam) for u in range(n) for v in range(u + 1, n))


def main():
    out = os.path.join(HERE, "saraswathi2025_algorithm1.csv")
    with open(out, "w", newline="") as f:
        wr = csv.writer(f)
        wr.writerow(["family", "n", "alg1_span", "alg1_valid", "paper_13_column", "matches_paper",
                     "labels_v1_to_vn"])
        for fam, ns, table in (("P", range(3, 51), PAPER_13_PATH), ("C", range(5, 51), PAPER_13_CYCLE)):
            for n in ns:
                if fam == "P":
                    diam, dist = n - 1, (lambda u, v: abs(u - v))
                else:
                    diam = n // 2
                    dist = (lambda n_: (lambda u, v: min(abs(u - v), n_ - abs(u - v))))(n)
                h = algorithm1(n, dist, diam)
                valid = is_rml(h, dist, diam)
                paper = table.get(n)
                wr.writerow([fam, n, max(h), valid, paper if paper is not None else "",
                             "" if paper is None else max(h) == paper, " ".join(map(str, h))])
                print(fam, n, max(h), valid, paper)


if __name__ == "__main__":
    main()
