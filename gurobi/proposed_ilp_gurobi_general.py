"""Radio Mean Labeling solver: general ILP model via Gurobi, using the
paper's proposed literal pairwise-boolean Radio-mean constraint
(x_{u,l1}+x_{v,l2} <= 1 for l1+l2 < H(u,v)). Assignment/Injectivity/Span
constraints, generic bound UB = n + diam(G) - 1. No symmetry breaking --
this is the general-graph variant; see proposed_ilp_gurobi_cycle.py /
proposed_ilp_gurobi_path.py for the cycle/path-specific symmetry-breaking
variants.

Setup: requires gurobipy (`pip install gurobipy`) and a valid license
findable via GRB_LICENSE_FILE or the default ~/gurobi.lic.

Run:
GRB_LICENSE_FILE=/path/to/gurobi.lic python3 proposed_ilp_gurobi_general.py < input.txt
"""

import time

import gurobipy as gp
from gurobipy import GRB

from common import graph, io, validate

n, adj_matrix = io.read_graph()
UB = io.read_upper_bound()

start_time = time.perf_counter()

dist_matrix = graph.all_pairs_bfs(adj_matrix)
diam = graph.diameter(dist_matrix)

env = gp.Env(params={"OutputFlag": 0})
model = gp.Model("rml_general_literal", env=env)

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

model.setObjective(l_max, GRB.MINIMIZE)


def report_incumbent(m, where):
    if where == GRB.Callback.MIPSOL:
        obj = m.cbGet(GRB.Callback.MIPSOL_OBJ)
        t = time.perf_counter() - start_time
        print(f"rmn(G) <= {int(round(obj))}")
        print(f"Execution time: {t:.6f} s")
        print()


model.optimize(report_incumbent)

t = time.perf_counter() - start_time
if model.SolCount > 0:
    k = int(round(model.ObjVal))
    print(f"rmn(G) = {k}")
    print(f"Execution time: {t:.6f} s")

    labels = [0] * n
    for v in range(n):
        for l in range(1, UB + 1):
            if x[v, l].X > 0.5:
                labels[v] = l
                break
    if len(set(labels)) == n and validate.check_rml(labels, n, diam, dist_matrix):
        print("Valid label")
    else:
        print("Invalid label")
else:
    print("No solution found.")
    print(f"Execution time: {t:.6f} s")
