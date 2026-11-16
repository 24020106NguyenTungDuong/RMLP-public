# Exact Approaches for Radio Mean Labeling: ILP and SAT

Code, instances and complete results for the paper *Exact approaches for Radio mean labeling: ILP
and SAT* by Huong Vu Thanh, Duong Nguyen Tung, Thuan Truong Ninh and Khanh To Van (IEEE Access,
under review). The CNF formulas and LRAT proofs are archived on Zenodo:
[10.5281/zenodo.24269021](https://doi.org/10.5281/zenodo.24269021).

## Overview

A radio mean labeling of a connected graph `G` is an injective function `h: V(G) → Z+` such that
for every pair of distinct vertices `u, v`:

```
d(u, v) + ceil((h(u) + h(v)) / 2) >= 1 + diam(G)
```

The **radio mean number** `rmn(G)` is the minimum span `max(h)` over all radio mean labelings of
`G`. This repository contains the paper's exact methods for computing it:

- the **ILP model**, solved with Gurobi and CPLEX;
- the **Basic SAT encoding**, a direct transcription of the ILP model into CNF;
- the **order SAT encoding** (order variables `G(v,l)` linked to exact-label variables `x(v,l)`),
  with the incremental descending search of Algorithm 1;
- the **constraint programming model** used for comparison (CP Optimizer);

together with the symmetry-breaking constraints for paths and cycles, the distance-twin clauses
for any graph, the LRAT proof pipeline, the baselines from the literature, the experiment
harness, and every result reported in the paper.

## Repository structure

| Path | Contents |
|---|---|
| `datasets/path/`, `datasets/cycle/` | `P_n`, `n = 3..50`, and `C_n`, `n = 5..50` |
| `datasets/{wheel,subdivided_star,ladder,grid,caterpillar}/` | The further families of Section IV-D; `datasets/gen_families.py` generates them (file name = family parameter `m`, see its docstring) |
| `sat/order_sat_{path,cycle,general}.py` | Order SAT encoding; `path`/`cycle` add the family symmetry breaking (`order_sat_cycle.py --sb full\|rotation`), `general` uses only the distance-twin clauses |
| `sat/simple_sat_{path,cycle,general}.py` | Basic SAT encoding |
| `gurobi/proposed_ilp_gurobi_{path,cycle,general}.py` | ILP model via Gurobi |
| `cplex/ProposedIlpCplex{Path,Cycle,General}.java` | ILP model via CPLEX (Java API) |
| `cp/cp_general.py` | CP model via CP Optimizer (docplex) |
| `*/common/` | Shared Python library (graph utilities, encoding, I/O, validation) |
| `validate/` | Validators that run the ILP solvers and re-check every labeling |
| `experiments/` | Experiment harness, proof checking, solver statistics and diagnostics; see `experiments/README.md` |
| `baselines/` | The published bounds of Tables 4–5, evaluated for every `n` |
| `results/` | Every result of the paper: `results.csv`, the raw solver outputs, the proof checks, the statistics and the optimal labelings |
| `archive/` | Variants not used in the paper (only-`G` order encoding); not runnable in place |

Each `general` variant makes no graph-specific assumptions; the `path` and `cycle` variants add
symmetry-breaking constraints that are sound only for their families.

## Installation

```bash
python3 -m venv venv
source venv/bin/activate
pip install python-sat gurobipy docplex
```

- **SAT:** [PySAT](https://pysathq.github.io/) with its bundled CaDiCaL 1.9.5; nothing else is needed.
- **Gurobi:** requires a licence; point `GRB_LICENSE_FILE` at it.
- **CPLEX:** requires IBM ILOG CPLEX Optimization Studio. Compile once:
  ```bash
  cd cplex
  javac -cp <CPLEX_STUDIO_DIR>/cplex/lib/cplex.jar *.java
  ```
- **CP Optimizer:** part of the same Studio; set
  `CPO_EXEC=<CPLEX_STUDIO_DIR>/cpoptimizer/bin/x86-64_linux/cpoptimizer`.

The paper used Python 3.12.3, PySAT 1.8.dev30, Gurobi 13.0.2, CPLEX and CP Optimizer 22.2.0,
docplex 2.32 and OpenJDK 21 (Table 2 of the paper).

## Usage

Every solver reads an instance from stdin and prints each improved labeling (`rmn(G) <= k`, the
time, and `h(i) = label` per vertex), then `rmn(G) = k` when it proves optimality.

```bash
# Order SAT encoding with symmetry breaking
python3 sat/order_sat_cycle.py < datasets/cycle/20.txt

# Basic SAT encoding
python3 sat/simple_sat_path.py < datasets/path/14.txt

# ILP via Gurobi
python3 gurobi/proposed_ilp_gurobi_path.py --time-limit 900 < datasets/path/40.txt

# ILP via CPLEX
cd cplex
java -cp .:<CPLEX_STUDIO_DIR>/cplex/lib/cplex.jar \
     -Djava.library.path=<CPLEX_STUDIO_DIR>/cplex/bin/x86-64_linux \
     ProposedIlpCplexPath 900 < ../datasets/path/40.txt

# CP model
python3 cp/cp_general.py --time-limit 900 < datasets/wheel/20.txt
```

To reproduce the paper's experiments, see `experiments/README.md`.

## Dataset format

```
n
<n x n adjacency matrix, one row per line, space-separated 0/1>
UB
```

`UB = n + diam(G) - 1` is the initial upper bound on the span (Lemma 1 of the paper).

## Validation

Every labeling a solver reports is re-checked against the definition, independently of the
solver: by the solvers themselves (`common/validate.py`), by the experiment harness
(`experiments/campaign.py`, column `labels_valid` of `results/results.csv`), and by the
validators:

```bash
python3 validate/validate_cycle.py --min 5 --max 50 --timeout 120
python3 validate/validate_path.py --min 3 --max 50 --timeout 300
```

`validate_path.py` runs CPLEX only up to `n = 42` by default (`CPLEX_CAP`), to keep validation
runs short; CPLEX needs up to 22.6 GB on `P_50`.
