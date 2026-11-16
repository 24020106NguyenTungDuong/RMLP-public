"""Baseline [26] of the paper: the value that Saraswathi and Meera, "Radio Mean Labeling of Paths and
Its Total Graph", TURCOMAT 12(1S):343-350, 2021, state as the exact radio mean number of P_n:
  rmn(P_n) = n                 for n <= 3,
             2n - 4            for n = 4, 5, 6,
             2n - k - 4        for n in [4 + S_k, 6 + S_k + k], S_k = 3 + 4 + ... + (3 + k - 1).

Compares it with (a) the [26] column of the first submission's Table 4 (n <= 30), (b) the path
labeling of Algorithm 1 of [14] (saraswathi2025_algorithm1.csv), and (c) the optimum proved by
Gurobi in our runs (../results/results.csv, arm grb_sb). Writes saraswathi2021_paths_formula.csv.
"""

import csv
import os

HERE = os.path.dirname(os.path.abspath(__file__))
RESULTS = os.path.join(HERE, "..", "results", "results.csv")

# [26] column of the first submission's Table 4, n = 3..30.
PAPER_26 = dict(zip(range(3, 31), [3, 4, 6, 8, 9, 11, 13, 15, 16, 18, 20, 22, 24, 25, 27,
                                   29, 31, 33, 35, 36, 38, 40, 42, 44, 46, 48, 49, 51]))


def rmn_claimed(n):
    if n <= 3:
        return n
    if n <= 6:
        return 2 * n - 4
    k = 1
    while not 4 + k * (k + 5) // 2 <= n <= 6 + k * (k + 5) // 2 + k:
        k += 1
    return 2 * n - k - 4


def main():
    alg14 = {int(r["n"]): int(r["alg1_span"])
             for r in csv.DictReader(open(os.path.join(HERE, "saraswathi2025_algorithm1.csv")))
             if r["family"] == "P"}
    opt = {int(r["n"]): int(r["proven_rmn"]) for r in csv.DictReader(open(RESULTS))
           if r["arm"] == "grb_sb" and r["family"] == "P"}
    below = 0
    with open(os.path.join(HERE, "saraswathi2021_paths_formula.csv"), "w", newline="") as f:
        wr = csv.writer(f)
        wr.writerow(["n", "stated_value", "first_submission_column", "alg1_path_span", "optimum",
                     "optimum_below_stated"])
        for n in range(3, 51):
            claim = rmn_claimed(n)
            assert opt[n] <= claim, f"n={n}: optimum above a stated labeling span"
            below += opt[n] < claim
            wr.writerow([n, claim, PAPER_26.get(n, ""), alg14[n], opt[n], opt[n] < claim])
    print("n with the optimum below the stated value:", below)


if __name__ == "__main__":
    main()
