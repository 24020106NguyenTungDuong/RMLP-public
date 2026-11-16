"""Radio Mean Labeling solver: ILP model via Gurobi, using the paper's
proposed literal pairwise-boolean Radio-mean constraint, plus
cycle-specific symmetry breaking (sound only for cycle graphs, whose full
rotational/reflective automorphism group justifies them):

    h(0) <= h(v)     for all v != 0     (rotate WLOG so vertex 0 is minimal)
    h(1) <= h(n-1)                       (break the remaining reflection)

Do not reuse this file's constraint set for path or general graphs.

Setup: requires gurobipy (`pip install gurobipy`) and a valid license
findable via GRB_LICENSE_FILE or the default ~/gurobi.lic.

Run:
GRB_LICENSE_FILE=/path/to/gurobi.lic python3 proposed_ilp_gurobi_cycle.py < input.txt
"""

import argparse
import time

import gurobipy as gp
from gurobipy import GRB

from common import graph, io, validate

parser = argparse.ArgumentParser()
parser.add_argument("--threads", type=int, default=0, help="Gurobi Threads (0 = solver default)")
parser.add_argument("--seed", type=int, default=0)
parser.add_argument("--time-limit", type=float, default=float("inf"), help="seconds")
parser.add_argument("--mip-gap", type=float, default=None, help="relative MIPGap (default: Gurobi's)")
args = parser.parse_args()

n, adj_matrix = io.read_graph()
UB = io.read_upper_bound()

start_time = time.perf_counter()

dist_matrix = graph.all_pairs_bfs(adj_matrix)
diam = graph.diameter(dist_matrix)

# Solver defaults unless overridden (the submitted runs used Gurobi's defaults).
params = {"OutputFlag": 0, "Threads": args.threads, "Seed": args.seed, "TimeLimit": args.time_limit}
if args.mip_gap is not None:
    params["MIPGap"] = args.mip_gap
env = gp.Env(params=params)
model = gp.Model("rml_cycle_literal", env=env)

x = model.addVars(n, range(1, UB + 1), vtype=GRB.BINARY, name="x")
l_max = model.addVar(lb=1, ub=UB, vtype=GRB.INTEGER, name="l_max")

model.addConstrs(
    (gp.quicksum(x[v, l] for l in range(1, UB + 1)) == 1 for v in range(n)),
    name="assignment")
model.addConstrs(
    (gp.quicksum(x[v, l] for v in range(n)) <= 1 for l in range(1, UB + 1)),
    name="injectivity")

h = {v: gp.quicksum(l * x[v, l] for l in range(1, UB + 1)) for v in range(n)}

for u in range(n):
    for v in range(u + 1, n):
        d = int(dist_matrix[u][v])
        h_uv = 2 * (diam - d) + 1
        for l1 in range(1, UB + 1):
            for l2 in range(1, UB + 1):
                if l1 + l2 < h_uv:
                    model.addConstr(x[u, l1] + x[v, l2] <= 1,
                                     name=f"radio_mean_{u}_{v}_{l1}_{l2}")

model.addConstrs((l_max >= h[v] for v in range(n)), name="span")

model.addConstrs((h[0] <= h[v] for v in range(1, n)), name="vertex0_pin")
if n > 2:
    model.addConstr(h[1] <= h[n - 1], name="reflection_break")

model.setObjective(l_max, GRB.MINIMIZE)


def report_incumbent(m, where):
    if where == GRB.Callback.MIPSOL:
        obj = m.cbGet(GRB.Callback.MIPSOL_OBJ)
        t = time.perf_counter() - start_time
        print(f"rmn(G) <= {int(round(obj))}")
        print(f"Execution time: {t:.6f} s")
        print()


model.Params.TimeLimit = max(1.0, args.time_limit - (time.perf_counter() - start_time))
model.optimize(report_incumbent)

t = time.perf_counter() - start_time
if model.SolCount > 0:
    k = int(round(model.ObjVal))
    if model.Status == GRB.OPTIMAL:
        print(f"rmn(G) = {k}")
    else:
        print(f"rmn(G) <= {k} (time limit reached)")
    print(f"Execution time: {t:.6f} s")

    labels = [0] * n
    for v in range(n):
        for l in range(1, UB + 1):
            if x[v, l].X > 0.5:
                labels[v] = l
                break
        print(f"h({v}) = {labels[v]}")
    if len(set(labels)) == n and validate.check_rml(labels, n, diam, dist_matrix):
        print("Valid label")
    else:
        print("Invalid label")
else:
    print("No solution found.")
    print(f"Execution time: {t:.6f} s")
