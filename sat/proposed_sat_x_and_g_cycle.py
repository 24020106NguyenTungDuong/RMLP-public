"""Radio Mean Labeling solver: x+G encoding, cycle graphs.

This is the most refined Python variant (ported from rdml_x_and_g_cycle_fix_1.py):
  - k is computed directly as n + diam - 1 (closed-form starting bound for
    cycles) instead of being read from stdin.
  - previous_label() strengthens the radio-mean constraint into direct
    implications for better unit propagation.
  - symmetry_breaking_cycle() is used (valid for cycles only) together with a
    vertex-0 exact-label pinning assumption.
  - lower_bound() is replaced by the much weaker trivial_lower_bound()
    (label >= 1) since previous_label()/symmetry breaking do the heavy lifting
    here instead of the top-window packing trick used elsewhere.
"""

import time

from pysat.solvers import Solver

from common import graph, io, encoding, validate

n, adj_matrix = io.read_graph()

start_time = time.perf_counter()

dist_matrix = graph.all_pairs_bfs(adj_matrix)
diam = graph.diameter(dist_matrix)
k = n + diam - 1
k_max = k


def get_var_G(i, j):
    return encoding.var_G_with_x(i, j, n, k_max)


def get_var_x(i, j):
    return encoding.var_x(i, j, n)


def decode_model(model, k):
    for i in range(n):
        for j in range(1, k + 1):
            if get_var_G(i, j) in model and -get_var_G(i, j + 1) in model:
                print(f"h({i}) = {j}")


def print_result(model, k):
    print(f"rmn(G) <= {k}")
    print(f"Execution time: {time.perf_counter() - start_time:.6f} s")
    print()


def is_sat(k):
    s = Solver(name="Cadical195")

    for clause in encoding.monotonicity(n, k, get_var_G):
        s.add_clause(clause)
    for clause in encoding.upper_bound(n, k, get_var_G):
        s.add_clause(clause)
    for clause in encoding.injectivity_x(n, k, get_var_x):
        s.add_clause(clause)
    for clause in encoding.rml(n, k, diam, dist_matrix, get_var_G):
        s.add_clause(clause)
    for clause in encoding.x_to_G(n, k, get_var_G, get_var_x):
        s.add_clause(clause)
    for clause in encoding.previous_label(n, k, diam, dist_matrix, get_var_G, get_var_x):
        s.add_clause(clause)
    for clause in encoding.symmetry_breaking_cycle(n, k, get_var_G, anchor=1):
        s.add_clause(clause)

    num_of_clauses = s.nof_clauses()
    num_of_variables = s.nof_vars()

    while True:
        assum = [lit for clause in encoding.trivial_lower_bound(n, get_var_G) for lit in clause]
        for clause in encoding.forbid_k(n, k + 1, get_var_G):
            s.add_clause(clause)
        # Guard against k - n + 1 <= 0: below that, get_var_x/get_var_G would
        # compute an out-of-range variable id (colliding with an unrelated
        # real variable) instead of a valid vertex-0 pin. Only reachable when
        # rmn(G) == n exactly, matching the guard already used in
        # cpp/solve_x_and_g_cycle_{portfolio,hybrid}.cpp.
        if k - n + 1 >= 1:
            assum.append(get_var_x(0, k - n + 1))
        if k - n + 2 >= 1:
            assum.append(-get_var_G(0, k - n + 2))

        solved = False
        if k >= n and s.solve(assumptions=assum):
            model = s.get_model()
            print_result(model, k)
            k -= 1
            solved = True
        if not solved:
            k += 1
            print(f"rmn(G) = {k}")
            print(f"Execution time: {time.perf_counter() - start_time:.6f} s")
            decode_model(model, k)
            validate.check_validation(model, n, k, diam, dist_matrix, get_var_G)
            print("Number of clauses:", num_of_clauses)
            print("Number of variables:", num_of_variables)
            break


is_sat(k)
