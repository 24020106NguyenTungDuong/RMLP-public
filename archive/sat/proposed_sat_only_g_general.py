"""Radio Mean Labeling solver: only-G encoding, general graphs (no symmetry
breaking -- valid for any connected graph, not just cycles/paths)."""

import time

from pysat.solvers import Solver

from common import graph, io, encoding, validate

n, adj_matrix = io.read_graph()
k = io.read_upper_bound()

start_time = time.perf_counter()

dist_matrix = graph.all_pairs_bfs(adj_matrix)
diam = graph.diameter(dist_matrix)
twin_classes = graph.find_distance_twins(dist_matrix)


def get_var_G(i, j):
    return encoding.var_G_only(i, j, n)


def print_result(model, k):
    print(f"rmn(G) <= {k}")
    print(f"Execution time: {time.perf_counter() - start_time:.6f} s")
    validate.check_validation(model, n, k, diam, dist_matrix, get_var_G)
    print()


def is_sat(k):
    s = Solver(name="Cadical195")

    for clause in encoding.monotonicity(n, k, get_var_G):
        s.add_clause(clause)
    for clause in encoding.upper_bound(n, k, get_var_G):
        s.add_clause(clause)
    for clause in encoding.injectivity_only_g(n, k, get_var_G):
        s.add_clause(clause)
    for clause in encoding.rml(n, k, diam, dist_matrix, get_var_G):
        s.add_clause(clause)
    for clause in encoding.symmetry_breaking_twins(k, get_var_G, twin_classes):
        s.add_clause(clause)

    last_model = None
    while True:
        assum = [lit for clause in encoding.lower_bound(n, k, get_var_G) for lit in clause]
        if k >= n and s.solve(assumptions=assum):
            model = s.get_model()
            last_model = model
            for clause in encoding.forbid_k(n, k, get_var_G):
                s.add_clause(clause)
            print_result(model, k)
            k -= 1
        else:
            k += 1
            print(f"rmn(G) = {k}")
            print(f"Execution time: {time.perf_counter() - start_time:.6f} s")
            if last_model is not None:
                validate.decode_model(last_model, n, k, get_var_G)
                validate.check_validation(last_model, n, k, diam, dist_matrix, get_var_G)
            else:
                print("No solution found.")
            return


is_sat(k)
