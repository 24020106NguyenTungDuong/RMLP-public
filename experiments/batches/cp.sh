#!/usr/bin/env bash
# CP model (CP Optimizer) on every instance (Table 6, Section IV-E).
# Paths to runlim, CPLEX, CP Optimizer, CaDiCaL and lrat-check: see ../config.py. Resumable.
set -euo pipefail
cd "$(dirname "$0")/.."
PY=${RMLP_PYTHON:-python3}
$PY -u campaign.py --arms cp_none --families PCWSLGT
