#!/usr/bin/env bash
# Order SAT on cycles with the rotation constraint only (Section IV-B, Reviewer 2 W2).
# Paths to runlim, CPLEX, CP Optimizer, CaDiCaL and lrat-check: see ../config.py. Resumable.
set -euo pipefail
cd "$(dirname "$0")/.."
PY=${RMLP_PYTHON:-python3}
$PY -u campaign.py --arms order_rot --families C
