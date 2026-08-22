"""Literal, faithful transcription of the paper's general ILP model
(Appendix A) into SAT, PLUS path-specific symmetry breaking. Same base
encoding as validate_ilp_general.py (see that file for the full
constraint derivation and the rationale for using the ILP's own literal
O(n^2*UB^2) Radio-mean enumeration rather than the compressed rml()
threshold trick) -- this file adds one constraint, sound only for path
graphs, matching common/encoding.py's symmetry_breaking_path():

    h(0) <= h(n-1)     (break the end-to-end reflection)

encoded the same literal way as this file's other constraints: forbid
every (l0, l_last) pair with l0 > l_last.

Do not reuse this file's constraint set for cycle or general graphs.
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
    result = []
    for v in range(n):
        result.append([get_var_x(v, l) for l in range(1, ub + 1)])
        for l1 in range(1, ub + 1):
            for l2 in range(l1 + 1, ub + 1):
                result.append([-get_var_x(v, l1), -get_var_x(v, l2)])
    return result


def radio_mean_literal(n, ub, diam, dist_matrix, get_var_x):
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


def reflection_break(n, ub, get_var_x):
    """h(0) <= h(n-1): literal pairwise enumeration forbidding (l0, l_last)
    with l0 > l_last, matching this file's other literal constraints."""
    result = []
    for l0 in range(1, ub + 1):
        for l_last in range(1, ub + 1):
            if l0 > l_last:
                result.append([-get_var_x(0, l0), -get_var_x(n - 1, l_last)])
    return result


def forbid_label(n, l, get_var_x):
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
    if n > 1:
        for clause in reflection_break(n, k_max, get_var_x):
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
