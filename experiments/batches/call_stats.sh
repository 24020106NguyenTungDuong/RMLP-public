#!/usr/bin/env bash
# Per-call CaDiCaL statistics of the order encoding with SB (Table 7).
# Paths to runlim, CPLEX, CP Optimizer, CaDiCaL and lrat-check: see ../config.py. Resumable.
set -euo pipefail
cd "$(dirname "$0")/.."
PY=${RMLP_PYTHON:-python3}
$PY -u call_stats.py --arm order_sb --families PC --time-limit 900
