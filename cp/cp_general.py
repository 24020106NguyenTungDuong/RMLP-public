"""Radio Mean Labeling: constraint programming model (CP Optimizer via docplex.cp).

The simple primal CP model (resubmission, Reviewer 1 question 1: comparison with another
exact method), for any connected graph, without symmetry breaking:

  variables   x_u in {1, ..., UB} for every vertex u (the label h(u)); UB from the input
  objective   min z, z = max_u x_u
  constraints AllDifferent(x_1, ..., x_n)
              x_u + x_v >= 2 (D - d(u, v)) + 1   for every pair u < v with d(u, v) < D

where D = diam(G). The second constraint is exactly the radio mean condition
ceil((x_u + x_v) / 2) >= D + 1 - d(u, v); pairs with d(u, v) = D satisfy it for any labels.

Output, as the other solvers: the best labeling ("rmn(G) <= k", the time it was found,
h(i) = label), and "rmn(G) = k" when CP Optimizer proves it optimal.

One solve() call, so CP Optimizer applies TimeLimit to the whole search (2026-11-10: the earlier
search_next loop overran the limit). The result is printed before the solver is shut down, and the
script then exits without waiting for CP Optimizer to free its memory (see the comment in main). solve() returns only the final solution, so the time at
which its value was first found is taken from CP Optimizer's own log, whose "*" lines give the
objective and elapsed time of every new solution, plus the time spent before CP Optimizer's
clock started (the total elapsed time minus its reported solve time).

Usage: python3 cp/cp_general.py [--threads T] [--seed S] [--time-limit SEC] < input.txt
  --threads 0 (default) = CP Optimizer's default (all cores), as for the ILP solvers.
"""

import argparse
import io as _io
import os
import re
import sys
import threading
import time

from docplex.cp.model import CpoModel
from docplex.cp.solver.solver import CpoSolver

from common import graph, io

# CP Optimizer executable: set CPO_EXEC to its path, e.g.
#   <CPLEX_STUDIO_DIR>/cpoptimizer/bin/x86-64_linux/cpoptimizer
# (otherwise docplex looks for "cpoptimizer" on the PATH).
CPO = os.environ.get("CPO_EXEC", "cpoptimizer")
NEW_SOL = re.compile(r"^\s*\*\s+(\d+)\s+\d+\s+([\d.]+)s", re.M)   # " *  obj  branches  time"


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--threads", type=int, default=0)
    p.add_argument("--seed", type=int, default=0)
    p.add_argument("--time-limit", type=float, default=900)
    a = p.parse_args()

    start = time.perf_counter()
    wall0 = time.time()          # real clock: runlim and the other solvers count real seconds
    n, adj = io.read_graph()
    ub = io.read_upper_bound()
    dist = graph.all_pairs_bfs(adj)
    diam = graph.diameter(dist)

    mdl = CpoModel(name="rml_cp")
    x = mdl.integer_var_list(n, 1, ub, "x")
    mdl.add(mdl.all_diff(x))
    for u in range(n):
        for v in range(u + 1, n):
            if dist[u][v] < diam:
                mdl.add(x[u] + x[v] >= 2 * (diam - dist[u][v]) + 1)
    mdl.minimize(mdl.max(x))

    log = _io.StringIO()
    params = {"TimeLimit": max(1.0, a.time_limit - (time.perf_counter() - start)),
              "RandomSeed": a.seed, "LogVerbosity": "Terse", "LogPeriod": 1000000}
    if a.threads > 0:
        params["Workers"] = a.threads
    with CpoSolver(mdl, execfile=CPO, log_output=log, **params) as solver:
        # CP Optimizer's TimeLimit runs on a clock that lags the real clock by 3-5% while its
        # workers load the machine (30.12 s on its clock = 31.05 s real; 900 s became about 930 s),
        # so runlim's 930 s limit killed the run before it printed (2026-11-10). A watchdog on the
        # real clock aborts the search at the requested limit; the abort returns the best solution
        # found. TimeLimit stays as a backstop: it fires later.
        def watchdog():
            while time.time() - wall0 < a.time_limit:
                time.sleep(0.02)
            solver.abort_search()
        threading.Thread(target=watchdog, daemon=True).start()
        res = solver.solve()
        # Everything before CP Optimizer's clock started (model building, launching the solver,
        # sending the model): the elapsed time so far minus CP Optimizer's own solve time.
        before = max(0.0, (time.perf_counter() - start) - res.get_solve_time())

        # Print the result NOW, inside the with block. Leaving the block ends the solver, which
        # kills the CP Optimizer process and waits for it to free its memory: about 3.5% of the
        # run (30 s after 900 s), long enough for runlim to kill this script at 930 s before it
        # printed anything, so the best labeling found was lost (2026-11-10, P34 and larger).
        if res.is_solution():
            h = [res.get_value(x[i]) for i in range(n)]
            k = max(h)
            found = [float(t) for obj, t in NEW_SOL.findall(log.getvalue()) if int(obj) == k]
            now = time.time() - wall0
            # CP Optimizer's times are on its own (slower) clock: scale them to the real clock.
            scale = now / max(1e-9, time.perf_counter() - start)
            t_best = min((before + found[0]) * scale, now) if found else now   # never later than now
            print(f"rmn(G) <= {k}")
            print(f"Execution time: {t_best:.6f} s")
            for i in range(n):
                print(f"h({i}) = {h[i]}")
            print(flush=True)
        if res.get_solve_status() == "Optimal":
            print(f"rmn(G) = {k}")
            print(f"Execution time: {time.time() - wall0:.6f} s")
        else:
            print(f"time limit reached (stop cause {res.get_stop_cause()})")
        sys.stdout.flush()

        # Skip the solver's orderly shutdown: kill the CP Optimizer process without waiting for
        # it, and leave. The result is already printed.
        try:
            solver.agent.process.kill()
        except Exception:
            pass
        os._exit(0)


if __name__ == "__main__":
    main()
