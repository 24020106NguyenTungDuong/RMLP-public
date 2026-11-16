#!/usr/bin/env bash
# LRAT proofs of the order encoding's optima, and negative controls (Section IV-A).
# Paths to runlim, CPLEX, CP Optimizer, CaDiCaL and lrat-check: see ../config.py. Resumable.
set -euo pipefail
cd "$(dirname "$0")/.."
PY=${RMLP_PYTHON:-python3}
$PY -u certify_order.py
for inst in P18 C20; do
    $PY -u negative_controls.py "$inst"
done
