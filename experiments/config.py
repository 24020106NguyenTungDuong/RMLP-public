"""Paths shared by the experiment scripts. Everything machine-specific comes from the environment.

  RMLP_PYTHON    Python interpreter for the solvers (default: the one running these scripts)
  RUNLIM         runlim executable (default: "runlim" on the PATH); used 2.0.0rc12
  CPLEX_HOME     <CPLEX_STUDIO_DIR>/cplex, for the CPLEX arms (Java API, CPLEX 22.2.0)
  CPO_EXEC       CP Optimizer executable, for the CP arm (see cp/cp_general.py)
  GRB_LICENSE_FILE  Gurobi licence, for the Gurobi arms (read by Gurobi itself)
  CADICAL        CaDiCaL 1.9.5 binary with LRAT output, for proof logging (default: "cadical")
  LRAT_CHECK     lrat-check from drat-trim (commit 2e3b2dc), for proof checking (default: "lrat-check")
"""

import os
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PY = os.environ.get("RMLP_PYTHON", sys.executable)
RUNLIM = os.environ.get("RUNLIM", "runlim")
CPLEX_HOME = os.environ.get("CPLEX_HOME", "")
CADICAL = os.environ.get("CADICAL", "cadical")
LRAT_CHECK = os.environ.get("LRAT_CHECK", "lrat-check")
DATASETS = os.path.join(REPO, "datasets")
RESULTS = os.path.join(REPO, "results")
FAMILY_DIR = {"P": "path", "C": "cycle",
              # further families, from datasets/gen_families.py; n is the family parameter m
              "W": "wheel", "S": "subdivided_star", "L": "ladder", "G": "grid", "T": "caterpillar"}
