"""Where does the ILP's proof come from? (Section IV-F of the paper; Reviewer 2, W1; diagnostics, not timings)

Builds the same model as gurobi/proposed_ilp_gurobi_{path,cycle}.py (literal
pairwise radio-mean rows, family symmetry breaking, Gurobi defaults) and
solves it with Gurobi's log on. Per instance it records
  rows / presolved_rows   model rows before and after presolve,
  lp_bound      optimum of the plain LP relaxation (no presolve/cuts),
  root_lp       Gurobi's root relaxation after presolve,
  bound_before_inc  best bound right before the first optimal incumbent,
  t_opt_incumbent   time the optimal labeling was found,
  bound_path    root-node bounds after that incumbent, as printed in the log,
  final_bound / obj, nodes, simplex iterations, runtime,
  cuts          cutting-plane families Gurobi applied, with counts.
The full Gurobi log goes to results/ilp_diagnostics/<instance>.log; the summary to
results/ilp_diagnostics/summary.csv. Run it while no other run is active.
"""

import csv
import os
import re
import sys

import gurobipy as gp
from gurobipy import GRB

from config import RESULTS

OUT = os.path.join(RESULTS, "ilp_diagnostics")
# rmn values proved in the campaign (Gurobi with SB), for locating the optimal incumbent
RMN = {(r["family"], int(r["n"])): int(r["proven_rmn"])
       for r in csv.DictReader(open(os.path.join(RESULTS, "results.csv"))) if r["arm"] == "grb_sb"}


def build(fam, n, env):
    diam = n - 1 if fam == "P" else n // 2
    dist = (lambda u, v: abs(u - v)) if fam == "P" else (lambda u, v: min(abs(u - v), n - abs(u - v)))
    UB = n + diam - 1
    m = gp.Model(f"{fam}{n}", env=env)
    x = m.addVars(n, range(1, UB + 1), vtype=GRB.BINARY, name="x")
    l_max = m.addVar(lb=1, ub=UB, vtype=GRB.INTEGER, name="l_max")
    m.addConstrs((gp.quicksum(x[v, l] for l in range(1, UB + 1)) == 1 for v in range(n)), name="assignment")
    m.addConstrs((gp.quicksum(x[v, l] for v in range(n)) <= 1 for l in range(1, UB + 1)), name="injectivity")
    h = {v: gp.quicksum(l * x[v, l] for l in range(1, UB + 1)) for v in range(n)}
    for u in range(n):
        for v in range(u + 1, n):
            H = 2 * (diam - dist(u, v)) + 1
            for l1 in range(1, UB + 1):
                for l2 in range(1, UB + 1):
                    if l1 + l2 < H:
                        m.addConstr(x[u, l1] + x[v, l2] <= 1)
    m.addConstrs((l_max >= h[v] for v in range(n)), name="span")
    if fam == "P":
        m.addConstr(h[0] <= h[n - 1])
    else:
        m.addConstrs((h[0] <= h[v] for v in range(1, n)))
        m.addConstr(h[1] <= h[n - 1])
    m.setObjective(l_max, GRB.MINIMIZE)
    return m


def main():
    os.makedirs(OUT, exist_ok=True)
    instances = [a for a in sys.argv[1:]] or ["P20", "P30", "P40", "P45", "P50", "C20", "C30", "C40", "C49", "C50"]
    rows = []
    for inst in instances:
        fam, n = inst[0], int(inst[1:])
        rmn = RMN[(fam, n)]
        env = gp.Env(params={"OutputFlag": 0})
        m = build(fam, n, env)
        m.update()
        r = m.relax()
        r.Params.Presolve = 0
        r.optimize()
        lp = r.ObjVal

        log = os.path.join(OUT, f"{inst}.log")
        if os.path.exists(log):
            os.remove(log)
        m.Params.OutputFlag = 1
        m.Params.LogToConsole = 0
        m.Params.LogFile = log
        m.optimize()
        text = open(log).read()
        rows_in = re.search(r"Optimize a model with (\d+) rows", text)
        rows_pre = re.search(r"Presolved: (\d+) rows", text)
        # Node-log lines: "H    0     0    <incumbent>   <bound> ...  <time>s" or "  0 0 <obj> ... <bound> ..."
        node = re.findall(r"^([H* ])\s+(\d+)\s+\d+\s+(.*?)\s+(\d+)s$", text, re.M)
        inc_t, before, path, seen = "", "", [], False
        for mark, _, body, t in node:
            nums = re.findall(r"\d[\d.]*(?:e[+-]\d+)?%?", body)
            if mark in "H*" and nums and abs(float(nums[0]) - rmn) < 1e-6 and not seen:
                seen, inc_t = True, t
                continue
            if not seen and len(nums) >= 2:      # node obj, depth, intinf, [incumbent], best bound
                before = [x for x in nums if not x.endswith("%")][-1]
            elif seen and (nums or "infeasible" in body or "cutoff" in body):
                path.append("infeasible" if "infeasible" in body or "cutoff" in body else nums[0])
        root_lp = re.search(r"Root relaxation: objective ([\d.e+-]+)", text)
        cuts = re.findall(r"^  ([A-Za-z][A-Za-z -]+): (\d+)$", text.split("Cutting planes:")[-1], re.M) \
            if "Cutting planes:" in text else []
        rows.append({"instance": inst, "rmn": rmn,
                     "rows": rows_in.group(1) if rows_in else "",
                     "presolved_rows": rows_pre.group(1) if rows_pre else "",
                     "lp_bound": round(lp, 3), "root_lp": root_lp.group(1) if root_lp else "",
                     "bound_before_inc": before, "t_opt_incumbent": inc_t,
                     "bound_path": " ".join(path),
                     "final_bound": round(m.ObjBound, 3), "obj": round(m.ObjVal),
                     "nodes": int(m.NodeCount), "simplex_iters": int(m.IterCount),
                     "runtime_s": round(m.Runtime, 2),
                     "cuts": "; ".join(f"{k.strip()}={v}" for k, v in cuts)})
        print(rows[-1], flush=True)
        env.dispose()
    with open(os.path.join(OUT, "summary.csv"), "w", newline="") as f:
        wr = csv.DictWriter(f, fieldnames=list(rows[0]))
        wr.writeheader()
        wr.writerows(rows)


if __name__ == "__main__":
    main()
