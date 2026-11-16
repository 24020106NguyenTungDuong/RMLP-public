"""Per-call CaDiCaL statistics of the order encoding (Table 7 of the paper; Reviewer 2, W1).

Runs the order-SAT solver script unchanged (the one campaign.py runs for an arm) and records,
for every SAT call of its descent, the result, the wall time and CaDiCaL's statistics:
conflicts (= learned clauses: CDCL learns one clause per conflict), decisions, propagations,
restarts, together with the formula size.

How: before the script runs, pysat.solvers.Solver is replaced by a subclass whose solve()
runs CaDiCaL in slices of --slice conflicts (conf_budget + solve_limited) and checks the real
clock between slices. PySAT cannot interrupt CaDiCaL on time, but a conflict budget returns
control, so a call that reaches --time-limit still reports its statistics (result TIMEOUT).
Learned clauses are kept between slices, so the search is CaDiCaL's own; the slicing only adds
the restart of the solve call every --slice conflicts, which the report states.

Output: one line per call on stdout,
  CALL <i> k=<span> result=<SAT|UNSAT|TIMEOUT> time=<s> conflicts=.. decisions=.. propagations=.. restarts=.. vars=.. clauses=..
plus the script's own output. A row per call is appended to --out (CSV), resumable per instance.

  python3 call_stats.py --arm order_sb --families PC [--max-n 50] [--time-limit 900]
"""

import argparse
import contextlib
import csv
import io
import os
import runpy
import sys
import time

import runlock

from config import DATASETS, REPO, RESULTS

ROOT = REPO
PY = os.path.join(REPO, "sat")
OUT = os.path.join(RESULTS, "call_stats.csv")
SCRIPTS = {("order_sb", "P"): ["order_sat_path.py"],
           ("order_sb", "C"): ["order_sat_cycle.py", "--sb", "full"],
           ("order_none", "P"): ["order_sat_general.py"],
           ("order_none", "C"): ["order_sat_general.py"]}
FIELDS = ["arm", "family", "n", "call", "k", "result", "seconds", "conflicts", "decisions",
          "propagations", "restarts", "vars", "clauses", "slice"]
KEYS = ("conflicts", "decisions", "propagations", "restarts")


class Deadline(Exception):
    pass


def instrument(deadline, slice_conf, calls):
    import pysat.solvers as ps
    base = ps.Solver

    class Timed(base):
        def solve(self, assumptions=[]):
            before = self.accum_stats() or {}
            t0 = time.time()
            res = None
            while res is None:
                if time.time() >= deadline:
                    break
                self.conf_budget(slice_conf)
                res = self.solve_limited(assumptions=assumptions)
            after = self.accum_stats() or {}
            row = {"result": "TIMEOUT" if res is None else ("SAT" if res else "UNSAT"),
                   "seconds": f"{time.time() - t0:.3f}", "vars": self.nof_vars(),
                   "clauses": self.nof_clauses(),
                   **{key: after.get(key, 0) - before.get(key, 0) for key in KEYS}}
            calls.append(row)
            print(f"CALL {len(calls)} " + " ".join(f"{a}={b}" for a, b in row.items()), flush=True)
            if res is None:
                raise Deadline
            return res

    ps.Solver = Timed


def run_one(arm, fam, n, time_limit, slice_conf):
    """Runs the solver on one instance in this process; returns its list of calls (with k)."""
    path = os.path.join(DATASETS, {"P": "path", "C": "cycle"}[fam], f"{n}.txt")
    script, *args = SCRIPTS[(arm, fam)]
    calls = []
    sys.path.insert(0, PY)
    instrument(time.time() + time_limit, slice_conf, calls)
    sys.argv = [script, *args]
    sys.stdin = open(path)
    out = io.StringIO()
    try:
        with contextlib.redirect_stdout(out):
            runpy.run_path(os.path.join(PY, script), run_name="__main__")
    except Deadline:
        pass
    # k of each call: the script prints "rmn(G) <= k" after every SAT call; calls go k_max, k_max-1, ...
    text = out.getvalue()
    sat_ks = [int(line.split()[-1]) for line in text.splitlines() if line.startswith("rmn(G) <=")]
    k = sat_ks[0] if sat_ks else None
    for i, c in enumerate(calls):
        c["k"] = (sat_ks[i] if i < len(sat_ks) else (sat_ks[-1] - 1 if sat_ks else ""))
    return calls


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--arm", default="order_sb", choices=sorted({a for a, _ in SCRIPTS}))
    p.add_argument("--families", default="PC")
    p.add_argument("--min-n", type=int, default=0)
    p.add_argument("--max-n", type=int, default=50)
    p.add_argument("--time-limit", type=float, default=900)
    p.add_argument("--slice", type=int, default=20000, help="conflicts per solve_limited slice")
    p.add_argument("--out", default=OUT)
    p.add_argument("--one", help="internal: run one instance FAM:N in this process")
    a = p.parse_args()

    if a.one:
        fam, n = a.one.split(":")
        for c in run_one(a.arm, fam, int(n), a.time_limit, a.slice):
            print("ROW " + ",".join(str(c.get(f, "")) for f in FIELDS[4:13]), file=sys.__stdout__, flush=True)
        return

    lock = runlock.acquire()  # noqa: F841 -- held until exit
    import subprocess
    done = set()
    if os.path.exists(a.out):
        done = {(r["arm"], r["family"], int(r["n"])) for r in csv.DictReader(open(a.out))}
    new = not os.path.exists(a.out)
    with open(a.out, "a", newline="") as f:
        wr = csv.DictWriter(f, fieldnames=FIELDS)
        if new:
            wr.writeheader()
        for fam in a.families:
            lo = {"P": 3, "C": 5}[fam]
            for n in range(max(lo, a.min_n), a.max_n + 1):
                if (a.arm, fam, n) in done:
                    continue
                # A fresh process per instance (the solver scripts are module-level code).
                proc = subprocess.run([sys.executable, "-u", __file__, "--arm", a.arm, "--one", f"{fam}:{n}",
                                       "--time-limit", str(a.time_limit), "--slice", str(a.slice)],
                                      cwd=PY, capture_output=True, text=True)
                rows = [line[4:].split(",") for line in proc.stdout.splitlines() if line.startswith("ROW ")]
                if proc.returncode != 0 or not rows:
                    print(f"{fam}{n}: failed (exit {proc.returncode})\n{proc.stderr[-2000:]}", flush=True)
                    continue
                for i, vals in enumerate(rows, 1):
                    wr.writerow({"arm": a.arm, "family": fam, "n": n, "call": i, "slice": a.slice,
                                 **dict(zip(FIELDS[4:13], vals))})
                f.flush()
                last = dict(zip(FIELDS[4:13], rows[-1]))
                print(f"{fam}{n}: {len(rows)} calls, last k={last['k']} {last['result']} "
                      f"{last['seconds']} s, {last['conflicts']} conflicts", flush=True)


if __name__ == "__main__":
    main()
