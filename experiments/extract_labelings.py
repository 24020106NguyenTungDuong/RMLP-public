"""Optimal labelings for every path and cycle (supplementary file; Reviewer 3, Concern 4).

Reads results/raw/<arm>/<instance>.out for every OPT row of one arm (default grb_sb, Gurobi
with SB, which proves all 94 values), takes the last labeling the solver printed (the witness
of the proven span), re-checks it against definition (1), and compares rmn(G) with the best
previously published bound:
  cycles: min of [27] Theorem 2 (n for n <= 9) and [14] Algorithm 1;
  paths:  min of the [26] stated value and [14] Algorithm 1
(baselines/*.csv). Writes results/optimal_labelings.csv; the rows with
improves_published = True are Table 11 of the paper.
Vertices are v_1..v_n in path/cycle order (the datasets' 0-based vertex i is v_{i+1}).
"""

import argparse
import csv
import os
import re

from config import REPO, RESULTS

BASE = os.path.join(REPO, "baselines")
H_RE = re.compile(r"^h\((\d+)\) = (\d+)$", re.M)


def is_rml(fam, h):
    n = len(h)
    diam = n - 1 if fam == "P" else n // 2
    dist = (lambda u, v: abs(u - v)) if fam == "P" else (lambda u, v: min(abs(u - v), n - abs(u - v)))
    return len(set(h)) == n and min(h) >= 1 and all(
        -(-(h[u] + h[v]) // 2) >= diam + 1 - dist(u, v) for u in range(n) for v in range(u + 1, n))


def prior_bounds():
    rd = lambda name: list(csv.DictReader(open(os.path.join(BASE, name))))
    alg14 = {(r["family"], int(r["n"])): int(r["alg1_span"]) for r in rd("saraswathi2025_algorithm1.csv")}
    th27 = {int(r["n"]): int(r["theorem2_bound"]) for r in rd("saraswathi2022_theorem2.csv")}
    st26 = {int(r["n"]): int(r["stated_value"]) for r in rd("saraswathi2021_paths_formula.csv")}

    def best(fam, n):
        other = (n if n <= 9 else th27[n]) if fam == "C" else st26[n]
        return min(alg14[(fam, n)], other)
    return best


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--arm", default="grb_sb")
    p.add_argument("--out-csv", default=os.path.join(RESULTS, "optimal_labelings.csv"))
    a = p.parse_args()
    best = prior_bounds()
    rows = [r for r in csv.DictReader(open(os.path.join(RESULTS, "results.csv")))
            if r["arm"] == a.arm and r["status"] == "OPT" and r["family"] in "PC"]
    out = []
    for r in sorted(rows, key=lambda r: (r["family"], int(r["n"]))):
        fam, n, rmn = r["family"], int(r["n"]), int(r["proven_rmn"])
        text = open(os.path.join(RESULTS, "raw", a.arm, f"{fam}{n}.out")).read()
        pairs = H_RE.findall(text)[-n:]                     # last printed labeling
        h = [int(lab) for _, lab in sorted(pairs, key=lambda x: int(x[0]))]
        assert len(h) == n and max(h) == rmn and is_rml(fam, h), f"{fam}{n}: bad witness"
        prior = best(fam, n)
        out.append({"family": fam, "n": n, "rmn": rmn, "best_published_bound": prior,
                    "improves_published": rmn < prior, "labels_v1_to_vn": " ".join(map(str, h))})
    with open(a.out_csv, "w", newline="") as f:
        wr = csv.DictWriter(f, fieldnames=list(out[0]))
        wr.writeheader()
        wr.writerows(out)
    new = [r for r in out if r["improves_published"]]
    print(f"{len(out)} labelings checked; {len(new)} below every published bound "
          f"({sum(r['family'] == 'C' for r in new)} cycles, {sum(r['family'] == 'P' for r in new)} paths)")


if __name__ == "__main__":
    main()
