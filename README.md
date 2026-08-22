# Exact Radio Mean Labeling of Paths and Cycles

> Submission ID: *TBD*
> Authors: *TBD*

This repository contains the code, datasets, and independent validators supporting our results
on the **Radio Mean Labeling (RML) Problem** for path and cycle graphs.

## Overview

A radio mean labeling of a graph `G` is an injective function `γ: V(G) → Z+` such that for every
pair of distinct vertices `u, v`:

```
d(u, v) + ceil((γ(u) + γ(v)) / 2) >= 1 + diam(G)
```

The **radio mean number** `rmn(G)` is the minimum possible span (i.e. `max(γ)`) over all valid
radio mean labelings of `G`.

Existing literature on this problem (see e.g. Badr et al., 2020, IEEE Access; Saraswathi & Meera,
2022, IEEE Access; Saraswathi, Meera & Lin, 2025, MDPI *Mathematics*) has proposed ILP models for
computing `rmn(G)` but, as of the most recent published work in this sub-field, exact computation
of `rmn(G)` for `n >= 10` is stated to be an open problem, with practical approaches limited to
brute-force enumeration.

This repository provides:
- SAT-based solvers implementing this paper's proposed encoding, which prove `rmn(G)` exactly for
  paths and cycles up to `n = 50`.
- A literal SAT transcription and ILP (Gurobi, CPLEX) implementations of the pairwise-boolean
  Radio-mean model used as an independent cross-check.
- Standalone validators that re-derive and check every returned labeling against the RML
  condition directly, independent of the solver that produced it.

## Repository Structure

| Path | Contents |
|---|---|
| `datasets/path/` | Path graph instances, `n = 3..50` |
| `datasets/cycle/` | Cycle graph instances, `n = 5..50` |
| `sat/proposed_sat_*.py` | This paper's proposed SAT encoding (x+G and only-G variants), general/path/cycle |
| `sat/simple_sat_*.py` | Literal SAT transcription of the pairwise-boolean ILP model, general/path/cycle |
| `sat/common/` | Shared Python library (graph utilities, encoding, I/O, validation) |
| `gurobi/proposed_ilp_gurobi_*.py` | Literal pairwise-boolean ILP model via Gurobi, general/path/cycle |
| `cplex/ProposedIlpCplex*.java` | Literal pairwise-boolean ILP model via CPLEX (Java), general/path/cycle |
| `validate/validate_path.py`, `validate/validate_cycle.py` | Independent validators: run the Gurobi/CPLEX solvers and re-check every labeling against the RML condition |

Each `general` variant makes no graph-specific assumptions; `path` and `cycle` variants add
symmetry-breaking constraints that are only sound for their respective graph families.

## Installation

### Python / SAT solvers

```bash
python3 -m venv venv
source venv/bin/activate
pip install python-sat
```

The `sat/` scripts use [PySAT](https://pysathq.github.io/) with the CaDiCaL backend (bundled with
`python-sat`). No further setup is required to run `sat/proposed_sat_*.py` or `sat/simple_sat_*.py`.

### Gurobi

```bash
pip install gurobipy
```

Requires a valid Gurobi license. Point `GRB_LICENSE_FILE` at your license file, or place it at the
default `~/gurobi.lic`.

### CPLEX (Java)

Requires an IBM ILOG CPLEX Optimization Studio installation. Compile once before use:

```bash
cd cplex
javac -cp <CPLEX_STUDIO_DIR>/cplex/lib/cplex.jar *.java
```

To run a solver or the validators, set two environment variables pointing at your installation:

```bash
export CPLEX_JAR=<CPLEX_STUDIO_DIR>/cplex/lib/cplex.jar
export CPLEX_LIB_PATH=<CPLEX_STUDIO_DIR>/cplex/bin/x86-64_linux
```

## Usage

All solvers read a graph instance from stdin and write results to stdout. Instance files are
under `datasets/`.

```bash
# Proposed SAT encoding (this paper's method)
python3 sat/proposed_sat_x_and_g_cycle.py < datasets/cycle/50.txt

# Literal SAT transcription of the pairwise-boolean ILP model
python3 sat/simple_sat_path.py < datasets/path/30.txt

# Gurobi (literal pairwise-boolean ILP model)
GRB_LICENSE_FILE=/path/to/gurobi.lic python3 gurobi/proposed_ilp_gurobi_cycle.py < datasets/cycle/50.txt

# CPLEX (Java, literal pairwise-boolean ILP model)
cd cplex
java -cp .:$CPLEX_JAR -Djava.library.path=$CPLEX_LIB_PATH ProposedIlpCplexPath 300 < ../datasets/path/40.txt
```

Each solver prints `rmn(G) = <value>` (or successive `rmn(G) <= <value>` incumbents as they are
found, for the ILP solvers), the vertex labeling (`h(<vertex>) = <label>`), execution time, and a
self-check result (`Valid label` / `Invalid label`).

## Dataset Format

Each instance file has the form:

```
n
<n x n adjacency matrix, one row per line, space-separated 0/1>
UB
```

`UB` is the initial upper bound on the span supplied to the ILP-based solvers
(`UB = n + diam(G) - 1`); the proposed SAT solvers compute this bound internally and ignore the
value in the file.

## Validation

`validate/validate_path.py` and `validate/validate_cycle.py` run the Gurobi and CPLEX solvers
across the full dataset and independently re-verify every returned labeling: injectivity, the
actual radio-mean distance condition (re-derived from the raw solver output, not assumed from the
encoding), and consistency between the reported `rmn(G)` and `max(labels)`. This check is
implemented separately from the encoding logic in `common/validate.py`, so it does not simply
trust that the ILP model was built correctly.

```bash
python3 validate/validate_cycle.py --min 5 --max 50 --timeout 120
python3 validate/validate_path.py --min 3 --max 50 --timeout 300
```

Note: for the path CPLEX solver, `n = 50` is excluded by default (`CPLEX_CAP` in
`validate_path.py`) — at that size the literal encoding's constraint count can exhaust memory on a
typical machine. Gurobi covers `n = 50` for path without issue. Adjust the cap if your machine has
more memory headroom.

## Common Issues

- **`FAIL (missing label(s))` from the CPLEX validators**: the `.java` files have not been
  compiled. Run `javac` in `cplex/` as shown above before invoking the CPLEX solvers or validators.
- **`RuntimeError: Set CPLEX_JAR and CPLEX_LIB_PATH...`**: these environment variables are unset
  or point at the wrong location — see the CPLEX installation section above.
- **Gurobi license errors**: confirm `GRB_LICENSE_FILE` points at a valid, unexpired license file.
