"""Literal, faithful transcription of the paper's general ILP model (Appendix
A) into SAT, for cross-validating the existing (differently-encoded) solvers
-- not a performance-oriented solver. Uses ONLY x_{v,l} boolean variables (no
G thermometer), matching the ILP exactly:

    min l_max
    s.t. sum_l x_{v,l} = 1                      for all v         (Assignment)
         sum_v x_{v,l} <= 1                      for all l         (Injectivity)
         x_{u,l1} + x_{v,l2} <= 1                for l1+l2 < H(u,v) (Radio-mean)
         l_max >= sum_l l * x_{v,l}              for all v         (Span)

The ILP's minimize-l_max objective becomes the same decision-problem +
incremental-descent pattern every other solver in this repo already uses:
solve "is l_max <= k feasible?" starting at k = UB (the input upper bound),
decrementing on success. Starting the search at UB and never testing a
larger k is exactly "l_max <= UB" as an added constraint, using the same
stdin format (n, adjacency, UB) as every other solve_*.py.

The Radio-mean constraint here is the ILP's own O(n^2 * UB^2) pairwise
enumeration (x_{u,l1} + x_{v,l2} <= 1 for every l1, l2 with l1+l2 < H(u,v)),
deliberately NOT the O(n^2 * UB) threshold trick common/encoding.py's rml()
uses -- the point of this file is to encode literally what the ILP states,
so a match against the existing solvers' rmn(G) values is a real
cross-validation of both encodings, not just two copies of the same one.
Only injectivity (already an exact structural match: sum_v x_{v,l} <= 1 is
precisely encoding.injectivity_x()) is reused. Expect this to only be
tractable for small n given the O(n^2 * UB^2) blowup.
"""

import time

from pysat.solvers import Solver

from common import graph, io, encoding, validate

n, adj_matrix = io.read_graph()
UB = io.read_upper_bound()
k_max = UB

start_time = time.perf_counter()

dist_matrix = graph.all_pairs_bfs(adj_matrix)
diam = graph.diameter(dist_matrix)


def get_var_x(i, l):
    return encoding.var_x(i, l, n)


def assignment(n, ub, get_var_x):
    """sum_l x_{v,l} = 1 for all v -- literal at-least-one + pairwise
    at-most-one, matching the ILP's equality constraint exactly."""
    result = []
    for v in range(n):
        result.append([get_var_x(v, l) for l in range(1, ub + 1)])
        for l1 in range(1, ub + 1):
            for l2 in range(l1 + 1, ub + 1):
                result.append([-get_var_x(v, l1), -get_var_x(v, l2)])
    return result


def radio_mean_literal(n, ub, diam, dist_matrix, get_var_x):
    """x_{u,l1} + x_{v,l2} <= 1 for all u != v, l1 + l2 < H(u,v). Literal
    O(n^2 * ub^2) enumeration, not the compressed threshold encoding."""
    result = []
    for u in range(n):
        for v in range(u + 1, n):
            d = int(dist_matrix[u][v])
            h_uv = 2 * (diam - d) + 1
            for l1 in range(1, ub + 1):
                for l2 in range(1, ub + 1):
                    if l1 + l2 < h_uv:
                        result.append([-get_var_x(u, l1), -get_var_x(v, l2)])
    return result


def forbid_label(n, l, get_var_x):
    """Permanently exclude exact label l for every vertex -- the x-only
    analog of encoding.forbid_k(), used the same way: called once per
    decrement with the just-tested k, building a growing exclusion prefix."""
    return [[-get_var_x(i, l)] for i in range(n)]


def decode_x(model, n, ub, get_var_x):
    model_set = set(model)
    h = [0] * n
    for i in range(n):
        for l in range(1, ub + 1):
            if get_var_x(i, l) in model_set:
                h[i] = l
                break
    return h


def print_result(h, k, proven):
    tag = "rmn(G) =" if proven else "rmn(G) <="
    print(f"{tag} {k}")
    print(f"Execution time: {time.perf_counter() - start_time:.6f} s")
    if h is None:
        print("No solution found.")
        print()
        return
    seen = [0] * (k + 1)
    ok = True
    for val in h:
        if val < 1 or val > k or seen[val]:
            ok = False
            break
        seen[val] = 1
    valid = ok and validate.check_rml(h, n, diam, dist_matrix)
    print("Valid label" if valid else "Invalid label")
    print()


def is_sat(k_max):
    s = Solver(name="Cadical195")

    for clause in assignment(n, k_max, get_var_x):
        s.add_clause(clause)
    for clause in encoding.injectivity_x(n, k_max, get_var_x):
        s.add_clause(clause)
    for clause in radio_mean_literal(n, k_max, diam, dist_matrix, get_var_x):
        s.add_clause(clause)

    k = k_max
    last_h = None
    while True:
        if k >= n and s.solve():
            model = s.get_model()
            h = decode_x(model, n, k_max, get_var_x)
            last_h = h
            print_result(h, k, proven=False)
            for clause in forbid_label(n, k, get_var_x):
                s.add_clause(clause)
            k -= 1
        else:
            k += 1
            print_result(last_h, k, proven=True)
            return


is_sat(k_max)
