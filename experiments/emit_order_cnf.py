"""Write the exact CNF of the order encoding's decisive UNSAT call.

Runs an order-encoding solver (sat/order_sat_{path,cycle}.py) unmodified,
with PySAT's Solver class replaced by a subclass that records every clause the
solver adds. At the first solve() call that returns UNSAT, the recorder writes
  every clause added so far (permanent clauses, symmetry breaking and the
  upper-bound clauses not G(v, k'+1) for every span k' tried so far)
  + one unit clause per assumption of that call (the window or the cycle pin)
to the output file in DIMACS. That is exactly the formula the solver refuted at
span rmn - 1, so an LRAT proof of it shows that span is infeasible (Theorem 1 and
Proposition 2 of the paper). If every call is SAT down to span n, no file is
written: rmn = n follows from injectivity.

The solver's own stdout is passed through unchanged, so the witness labeling
at span rmn can be read from it.

  python3 emit_order_cnf.py <solver.py> <out.cnf> [solver args...] < graph.txt
"""

import os
import runpy
import sys

import pysat.solvers as ps

solver_path, out_cnf, *solver_args = sys.argv[1:]
Real = ps.Solver
emitted = False


class Recorder(Real):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.recorded = []

    def add_clause(self, clause, no_return=True):
        self.recorded.append([int(l) for l in clause])
        return super().add_clause(clause, no_return)

    def append_formula(self, formula, no_return=True):   # not used by the solvers; refuse silently wrong output
        raise NotImplementedError("emit_order_cnf: append_formula is not recorded")

    def solve(self, assumptions=[]):
        global emitted
        result = super().solve(assumptions=assumptions)
        if result is False and not emitted:
            clauses = self.recorded + [[int(a)] for a in assumptions]
            nvars = max([self.nof_vars()] + [abs(l) for c in clauses for l in c])
            with open(out_cnf, "w") as f:
                f.write(f"c order encoding, decisive UNSAT call; solver {os.path.basename(solver_path)}"
                        f" {' '.join(solver_args)}\n")
                f.write(f"c {len(self.recorded)} recorded clauses + {len(assumptions)} assumption units\n")
                f.write(f"p cnf {nvars} {len(clauses)}\n")
                for c in clauses:
                    f.write(" ".join(map(str, c)) + " 0\n")
            emitted = True
        return result


ps.Solver = Recorder
sys.path.insert(0, os.path.dirname(os.path.abspath(solver_path)))
sys.argv = [solver_path] + solver_args
runpy.run_path(solver_path, run_name="__main__")
