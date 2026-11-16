#!/usr/bin/env bash
# All methods without SB on wheels, subdivided stars, ladders, grids and caterpillars (Table 6).
# Paths to runlim, CPLEX, CP Optimizer, CaDiCaL and lrat-check: see ../config.py. Resumable.
set -euo pipefail
cd "$(dirname "$0")/.."
PY=${RMLP_PYTHON:-python3}
$PY -u campaign.py --arms grb_none,cpx_none,order_none,basic_none --families WSLGT
