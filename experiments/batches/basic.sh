#!/usr/bin/env bash
# Basic SAT with and without SB on P3-P50 and C5-C50 (Tables 3-5, 8).
# Paths to runlim, CPLEX, CP Optimizer, CaDiCaL and lrat-check: see ../config.py. Resumable.
set -euo pipefail
cd "$(dirname "$0")/.."
PY=${RMLP_PYTHON:-python3}
$PY -u campaign.py --arms basic_sb,basic_none --families PC
