"""Check the clause and variable counts of Table 1 of the paper against the solvers (Reviewer 1, Concern 8).

For each solver (Basic SAT and order SAT, with and without SB), the unmodified
solver file is run with PySAT's Solver replaced by a recorder. At its first
solve() call, before any search, the recorder reports the number of clauses
added and the largest variable index. These are compared with the closed forms
of Table 1, evaluated from n, D = diam(G), k_max = n + D - 1 and
the pair thresholds H(u,v) = 2(D - d(u,v)) + 1.

  python3 count_clauses.py            # P3-P20 and C5-C20, every solver
  python3 count_clauses.py --table    # also print the formulas at n = 20, 30, 40, 50

Exit code 1 if any count differs.
"""

import argparse
import io
import os
import runpy
import sys
from contextlib import redirect_stdout
from math import comb

import pysat.solvers as ps

from config import DATASETS, REPO

PYDIR = os.path.join(REPO, "sat")
FAMILY_DIR = {"P": "path", "C": "cycle"}


class Counted(Exception):
    pass


def recorded_counts(solver_file, graph_file):
    real = ps.Solver
    seen = {}

    class Recorder(real):
        def __init__(self, *a, **k):
            super().__init__(*a, **k)
            self.nc, self.mv = 0, 0

        def add_clause(self, clause, no_return=True):
            self.nc += 1
            self.mv = max([self.mv] + [abs(int(l)) for l in clause])
            return super().add_clause(clause, no_return)

        def solve(self, assumptions=[]):
            seen.update(clauses=self.nc, maxvar=self.mv, assumptions=len(assumptions))
            raise Counted

    ps.Solver = Recorder
    old_stdin, old_argv = sys.stdin, sys.argv
    try:
        sys.stdin = open(graph_file)
        sys.argv = [solver_file]
        sys.path.insert(0, PYDIR)
        with redirect_stdout(io.StringIO()):
            runpy.run_path(solver_file, run_name="__main__")
    except Counted:
        pass
    finally:
        sys.stdin.close()
        sys.stdin, sys.argv = old_stdin, old_argv
        ps.Solver = real
    return seen


def pairs(fam, n):
    """Thresholds H(u,v) for all unordered pairs."""
    D = n - 1 if fam == "P" else n // 2
    dist = (lambda u, v: v - u) if fam == "P" else (lambda u, v: min(v - u, n - v + u))
    return D, [2 * (D - dist(u, v)) + 1 for u in range(n) for v in range(u + 1, n)]


def formulas(fam, n):
    """Clause counts per family, as in Table tab:sizes (built once at k_max)."""
    D, H = pairs(fam, n)
    K = n + D - 1
    order = {
        "linking": 3 * n * K,
        "monotonicity": n * K,
        "upper bound": n,
        "injectivity": comb(n, 2) * K,
        "radio mean": sum(h - 2 for h in H if h >= 5),          # pairs with d <= D - 2
    }
    order_sb = dict(order, **({"SB": K - 1} if fam == "P" else
                              {"SB": K - 1, "propagation": sum(2 * max(0, min(K, h - 2)) for h in H)}))
    basic = {
        "exactly one": n + n * comb(K, 2),
        "injectivity": comb(n, 2) * K,
        "radio mean": sum((h - 1) * (h - 2) // 2 for h in H),
    }
    basic_sb = dict(basic, SB=comb(K, 2) if fam == "P" else n * comb(K, 2))   # cycle: (n-1) pin + 1 reflection
    return {
        "order_sb": (order_sb, n * (2 * K + 1)),
        "order_none": (order, n * (2 * K + 1)),
        "basic_sb": (basic_sb, n * K),
        "basic_none": (basic, n * K),
    }


def twin_clauses(fam, n):
    """encoding.symmetry_breaking_twins: per class of m twins, m - 1 chained orders of k_max - 1 clauses."""
    sys.path.insert(0, PYDIR)
    from common import graph
    D = n - 1 if fam == "P" else n // 2
    dist = [[abs(u - v) if fam == "P" else min(abs(u - v), n - abs(u - v)) for v in range(n)] for u in range(n)]
    return sum(len(c) - 1 for c in graph.find_distance_twins(dist)) * (n + D - 1 - 1)


SOLVERS = {
    "order_sb": lambda fam: f"order_sat_{FAMILY_DIR[fam]}.py",
    "order_none": lambda fam: "order_sat_general.py",
    "basic_sb": lambda fam: f"simple_sat_{FAMILY_DIR[fam]}.py",
    "basic_none": lambda fam: "simple_sat_general.py",
}


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--max-n", type=int, default=20)
    p.add_argument("--table", action="store_true")
    a = p.parse_args()
    bad = 0
    for fam, start in (("P", 3), ("C", 5)):
        for n in range(start, a.max_n + 1):
            graph = os.path.join(DATASETS, FAMILY_DIR[fam], f"{n}.txt")
            f = formulas(fam, n)
            for arm, solver in SOLVERS.items():
                got = recorded_counts(os.path.join(PYDIR, solver(fam)), graph)
                want_c, want_v = sum(f[arm][0].values()), f[arm][1]
                if arm == "order_sb":     # the first call's tightening units not G(v, k_max+1), added
                    want_c += n           # before its first solve(); they repeat the upper-bound family
                if arm == "order_none":   # distance-twin order clauses (only P3 among these graphs)
                    want_c += twin_clauses(fam, n)
                ok = got["clauses"] == want_c and got["maxvar"] == want_v
                bad += not ok
                if not ok:
                    print(f"MISMATCH {arm} {fam}{n}: clauses {got['clauses']} vs {want_c}, "
                          f"vars {got['maxvar']} vs {want_v}")
    print(f"{'all counts match' if not bad else f'{bad} mismatches'} (P3-P{a.max_n}, C5-C{a.max_n}, 4 solvers)")
    if a.table:
        for fam in "PC":
            for n in (20, 30, 40, 50):
                for arm, (fam_counts, nv) in formulas(fam, n).items():
                    print(f"{fam}{n} {arm:10s} vars {nv:>7,} clauses {sum(fam_counts.values()):>12,}  "
                          + "; ".join(f"{k} {v:,}" for k, v in fam_counts.items()))
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
