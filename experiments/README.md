# Experiments

Every number in the paper comes from the scripts in this folder, under one protocol:

- **900 s wall-clock per run**, enforced by [runlim](https://github.com/arminbiere/runlim)
  (2.0.0rc12), which also records CPU time and peak memory; the ILP and CP solvers also receive
  the limit as their own time limit (`--budget`, 30 s grace for them to stop and print);
- **26 GB memory per run** (`--space-mb 26000`);
- **one run at a time** (`runlock.py`), unpinned, on an Intel Core i7-10750H (6 cores, 12
  threads) under WSL2 (Ubuntu 24.04.1, limited to 28 GB);
- **solver defaults**: SAT on one thread; Gurobi, CPLEX and CP Optimizer with their default
  threads (12) and tolerances; random seed 0 wherever a solver accepts one;
- every labeling a solver reports is **re-checked** against the definition by `campaign.py`.

## Setup

Machine-specific paths come from environment variables (see `config.py`):

```bash
export RUNLIM=/path/to/runlim
export CPLEX_HOME=<CPLEX_STUDIO_DIR>/cplex                       # CPLEX arms and diagnostics
export CPO_EXEC=<CPLEX_STUDIO_DIR>/cpoptimizer/bin/x86-64_linux/cpoptimizer   # CP arm
export GRB_LICENSE_FILE=/path/to/gurobi.lic                      # Gurobi arms and diagnostics
export CADICAL=/path/to/cadical                                  # CaDiCaL 1.9.5 binary (proofs)
export LRAT_CHECK=/path/to/lrat-check                            # drat-trim commit 2e3b2dc
export RMLP_PYTHON=$(which python3)                              # interpreter with the packages
```

Compile the CPLEX solvers first (`cplex/`, see the main README).

## Runs

Each script in `batches/` runs one experiment and resumes where it stopped; results are appended
to `../results/`.

| Script | Command | Paper |
|---|---|---|
| `gurobi.sh` | `campaign.py --arms grb_sb,grb_none --families PC` | Tables 3–5, 8–10 |
| `cplex.sh` | `campaign.py --arms cpx_sb,cpx_none --families PC` | Tables 3–5, 8–10 |
| `order_sb.sh` | `campaign.py --arms order_sb --families PC` | Tables 3–5, 9–10 |
| `order_none.sh` | `campaign.py --arms order_none --families PC` | Tables 3, 9–10 |
| `order_rot.sh` | `campaign.py --arms order_rot --families C` | Section IV-B (rotation constraint only) |
| `basic.sh` | `campaign.py --arms basic_sb,basic_none --families PC` | Tables 3–5, 8 |
| `families.sh` | `campaign.py --arms grb_none,cpx_none,order_none,basic_none --families WSLGT` | Table 6, Section IV-D |
| `cp.sh` | `campaign.py --arms cp_none --families PCWSLGT` | Table 6, Section IV-E |
| `certify_order.sh` | `certify_order.py`, then `negative_controls.py P18` and `C20` | Section IV-A, daggers in Tables 4, 5, 11 |
| `call_stats.sh` | `call_stats.py --arm order_sb --families PC` | Table 7 |
| `ilp_diagnostics.sh` | `ilp_diagnostics.py` | Section IV-F (Gurobi presolve, root node) |
| `cplex_diagnostics.sh` | `cplex_diagnostics.py` in several modes | CPLEX memory and presolve (Reviewer 2, W3) |

Families: `P` paths, `C` cycles, `W` wheels, `S` subdivided stars, `L` ladders, `G` grids,
`T` caterpillars. Arms (method, symmetry breaking) are defined in `campaign.py` (`ARMS`):
`order_*` order SAT, `basic_*` Basic SAT, `grb_*` Gurobi, `cpx_*` CPLEX, `cp_none` CP;
`*_sb` with the family's symmetry breaking, `*_none` without, `order_rot` cycles with the
rotation constraint only.

Other scripts:

- `status.py` — progress per arm and family;
- `count_clauses.py` — checks the clause and variable counts of Table 1 against the solvers;
- `extract_labelings.py` — writes `results/optimal_labelings.csv` (the supplementary file; its
  rows with `improves_published = True` are Table 11);
- `emit_order_cnf.py` — used by `certify_order.py` to write the CNF of the decisive call.

`call_stats.py` runs CaDiCaL in slices of 20,000 conflicts so that the time limit can be checked;
it reaches the same best spans and proven optima as the campaign.

## Results (`../results/`)

| File | Contents |
|---|---|
| `results.csv` | One row per run: status (`OPT` proved optimal, `TO` time limit), proven value, best span, time to the best labeling, wall and CPU time, peak memory, labeling check |
| `raw/<arm>/<instance>.out`, `.runlim` | Complete solver output and runlim report of every run |
| `manifest-*.json` | Versions, machine, git state and arguments of each campaign start |
| `certify_order.csv` | LRAT proof check per instance (25 verified; 7 with `rmn = n` need none) |
| `negative_controls_order.csv` | The checker on truncated and corrupted proofs |
| `call_stats.csv` | CaDiCaL statistics of every SAT call (Table 7) |
| `optimal_labelings.csv` | An optimal labeling of every path and cycle, with the best published bound |
| `ilp_diagnostics/`, `cplex_diagnostics/` | Solver logs and summaries of the diagnostics |

The CNF formulas and LRAT proofs (`results/proofs_order/`, 470 MB) are on Zenodo, not in git:
https://doi.org/10.5281/zenodo.24269021.

The raw outputs, runlim reports and manifests were written by the development copy of this
code, so they name the solver files and folders as they were called there: `solve_x_and_g_*`
= `sat/order_sat_*`, `validate_ilp_*` = `sat/simple_sat_*`, `solve_*_gurobi_literal` =
`gurobi/proposed_ilp_gurobi_*`, `Solve*CplexLiteral` = `cplex/ProposedIlpCplex*`,
`solve_general_cp` = `cp/cp_general`. The code is the same apart from names and comments.
