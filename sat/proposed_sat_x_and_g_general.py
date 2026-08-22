"""Radio Mean Labeling solver: x+G encoding, general graphs (no symmetry
breaking -- valid for any connected graph, not just cycles)."""

import time

from pysat.solvers import Solver

from common import graph, io, encoding, validate

n, adj_matrix = io.read_graph()
k = io.read_upper_bound()
k_max = k

start_time = time.perf_counter()

dist_matrix = graph.all_pairs_bfs(adj_matrix)
diam = graph.diameter(dist_matrix)
twin_classes = graph.find_distance_twins(dist_matrix)


def get_var_G(i, j):
    return encoding.var_G_with_x(i, j, n, k_max)


def get_var_x(i, j):
    return encoding.var_x(i, j, n)


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
    for clause in encoding.x_to_G(n, k, get_var_G, get_var_x):
        s.add_clause(clause)
    for clause in encoding.rml(n, k, diam, dist_matrix, get_var_G):
        s.add_clause(clause)
    for clause in encoding.symmetry_breaking_twins(k, get_var_G, twin_classes):
        s.add_clause(clause)

    while True:
        # No vertex-0 pin here: that trick is only sound together with
        # symmetry_breaking_cycle() (it assumes WLOG vertex 0 holds the
        # minimal label, valid only because of a cycle's automorphisms).
        assum = [lit for clause in encoding.lower_bound(n, k, get_var_G) for lit in clause]
        if k >= n and s.solve(assumptions=assum):
            model = s.get_model()
            for clause in encoding.forbid_k(n, k, get_var_G):
                s.add_clause(clause)
            print_result(model, k)
            k -= 1
        else:
            k += 1
            print(f"rmn(G) = {k}")
            print(f"Execution time: {time.perf_counter() - start_time:.6f} s")
            return


is_sat(k)
