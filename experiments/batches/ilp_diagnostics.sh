#!/usr/bin/env bash
# Gurobi presolve, root bound and incumbent timing (Section IV-F).
# Paths to runlim, CPLEX, CP Optimizer, CaDiCaL and lrat-check: see ../config.py. Resumable.
set -euo pipefail
cd "$(dirname "$0")/.."
PY=${RMLP_PYTHON:-python3}
$PY -u ilp_diagnostics.py
