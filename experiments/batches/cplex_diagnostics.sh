#!/usr/bin/env bash
# CPLEX presolve, memory and root-node diagnostics (Reviewer 2, W3).
# Paths to runlim, CPLEX, CP Optimizer, CaDiCaL and lrat-check: see ../config.py. Resumable.
set -euo pipefail
cd "$(dirname "$0")/.."
PY=${RMLP_PYTHON:-python3}
$PY -u cplex_diagnostics.py
$PY -u cplex_diagnostics.py --mode nocb P40 P41 P42 P43 P44 P45 P46 P47 P48 P49 P50
$PY -u cplex_diagnostics.py P40 --mode emptycb
$PY -u cplex_diagnostics.py P40 --mode lazyparams
$PY -u cplex_diagnostics.py P40 --mode cb --threads 1 --budget 300
$PY -u cplex_diagnostics.py P40 --mode nocb --threads 1 --budget 300
$PY -u cplex_diagnostics.py P40 --mode progress
for MODE in tune-bound tune-cliques tune-probe; do
    $PY -u cplex_diagnostics.py P45 P50 --mode "$MODE"
done
$PY -u cplex_diagnostics.py P43 P46 P47 P48 P49 --mode tune-cliques
$PY -u cplex_diagnostics.py P45 --mode nocb --seed 0
$PY -u cplex_diagnostics.py P45 --mode tune-cliques --seed 0
