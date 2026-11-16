"""Radio Mean Labeling solver: only-G encoding, path graphs.

Uses symmetry_breaking_path(): a path's only non-trivial automorphism is the
end-to-end reflection, broken by forcing h(0) < h(n-1).
"""

import time

from pysat.solvers import Solver

from common import graph, io, encoding, validate

n, adj_matrix = io.read_graph()
k = io.read_upper_bound()

start_time = time.perf_counter()

dist_matrix = graph.all_pairs_bfs(adj_matrix)
diam = graph.diameter(dist_matrix)

num_of_clauses = 0
num_of_variables = 0


def get_var_G(i, j):
    return encoding.var_G_only(i, j, n)


def print_result(model, k):
    print(f"rmn(G) <= {k}")
    print(f"Execution time: {time.perf_counter() - start_time:.6f} s")
    #validate.decode_model(model, n, k, get_var_G)
    #validate.check_validation(model, n, k, diam, dist_matrix, get_var_G)
    print("Number of clauses:", num_of_clauses)
    print("Number of variables:", num_of_variables)
    print()


def is_sat(k):
    global num_of_clauses
    global num_of_variables
    s = Solver(name="Cadical195")

    for clause in encoding.monotonicity(n, k, get_var_G):
        s.add_clause(clause)
    for clause in encoding.upper_bound(n, k, get_var_G):
        s.add_clause(clause)
    for clause in encoding.injectivity_only_g(n, k, get_var_G):
        s.add_clause(clause)
    for clause in encoding.rml(n, k, diam, dist_matrix, get_var_G):
        s.add_clause(clause)
    for clause in encoding.symmetry_breaking_path(n, k, get_var_G):
        s.add_clause(clause)

    num_of_clauses = s.nof_clauses()
    num_of_variables = s.nof_vars()

    while True:
        assum = [lit for clause in encoding.lower_bound(n, k, get_var_G) for lit in clause]
        for clause in encoding.forbid_k(n, k + 1, get_var_G):
            s.add_clause(clause)

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
            validate.decode_model(model, n, k, get_var_G)
            validate.check_validation(model, n, k, diam, dist_matrix, get_var_G)
            print("Number of clauses:", num_of_clauses)
            print("Number of variables:", num_of_variables)
            break


is_sat(k)
