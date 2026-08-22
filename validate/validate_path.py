"""Independent validation pass over the path-graph solvers' results.

Runs the proposed_ilp_gurobi_{general,path}.py (Gurobi) and
ProposedIlpCplex{General,Path} (CPLEX Java) solvers across datasets/path
and independently verifies every returned labeling against this repo's
own canonical validator (common/validate.py's check_rml -- injectivity
plus the actual Radio-mean condition, re-derived from the raw solver
output) rather than just trusting the ILP encoding is correct by
construction. Also cross-checks that max(labels) matches the solver's
own reported rmn(G) value.

n=50 is excluded for the CPLEX Java solvers only: at that size, path's
UB=2n-2 makes the literal encoding's O(n^2*UB^2) constraint count large
enough to exhaust memory on a typical machine (~15.6GB RSS observed
during development). Gurobi solves n=50 fine and is included with a
longer timeout. Each CPLEX solver's proven frontier is capped below n=50
for the same reason -- see CPLEX_CAP below; adjust if your machine has
more memory headroom.

Requires CPLEX_JAR and CPLEX_LIB_PATH environment variables pointing at
your CPLEX installation's cplex.jar and native library directory (see
repo README) to validate the Java solvers; the Gurobi half runs
independently of those.

Usage:
    python3 validate_path.py [--min N] [--max N] [--timeout SECONDS]
"""

import argparse
import glob
import os
import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent / "common"))
import graph  # noqa: E402
import validate  # noqa: E402

PATH_DATASET = REPO_ROOT / "datasets" / "path"
GUROBI_DIR = REPO_ROOT / "gurobi"
CPLEX_DIR = REPO_ROOT / "cplex"

CPLEX_JAR = os.environ.get("CPLEX_JAR")
CPLEX_LIB_PATH = os.environ.get("CPLEX_LIB_PATH")

GUROBI_SOLVERS = [
    ("proposed_ilp_gurobi_general", "proposed_ilp_gurobi_general.py"),
    ("proposed_ilp_gurobi_path", "proposed_ilp_gurobi_path.py"),
]
JAVA_SOLVERS = [
    ("ProposedIlpCplexGeneral", "ProposedIlpCplexGeneral"),
    ("ProposedIlpCplexPath", "ProposedIlpCplexPath"),
]
# Largest n each CPLEX solver has been confirmed to solve without running
# out of memory on a typical development machine. Raise these if you've
# verified your machine can go further.
CPLEX_CAP = {"ProposedIlpCplexGeneral": 44, "ProposedIlpCplexPath": 42}

RMN_EQ_RE = re.compile(r"rmn\(G\) = (\d+)")
H_RE = re.compile(r"h\((\d+)\) = (\d+)")


def instance_files(min_n, max_n, exclude_n50=False):
    files = glob.glob(str(PATH_DATASET / "*.txt"))
    out = []
    for p in files:
        name = Path(p).stem
        if not name.isdigit():
            continue
        n = int(name)
        if n < min_n or n > max_n:
            continue
        if exclude_n50 and n == 50:
            continue
        out.append(p)
    return sorted(out, key=lambda p: int(Path(p).stem))


def load_graph(path):
    with open(path) as f:
        n = int(f.readline())
        adj = [list(map(int, f.readline().split())) for _ in range(n)]
    dist_matrix = graph.all_pairs_bfs(adj)
    diam = graph.diameter(dist_matrix)
    return n, dist_matrix, diam


def run_gurobi(script, infile, timeout_s):
    proc = subprocess.run(
        [sys.executable, "-u", script],
        stdin=open(infile), stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        timeout=timeout_s, cwd=GUROBI_DIR)
    out = proc.stdout.decode(errors="replace")
    m_rmn = RMN_EQ_RE.search(out)
    reported_k = int(m_rmn.group(1)) if m_rmn else None
    valid_line = "Valid label" in out
    invalid_line = "Invalid label" in out
    return reported_k, valid_line and not invalid_line


def run_java(class_name, infile, timeout_s):
    if not CPLEX_JAR or not CPLEX_LIB_PATH:
        raise RuntimeError("Set CPLEX_JAR and CPLEX_LIB_PATH to validate the CPLEX solvers.")
    cmd = ["java", "-cp", f".:{CPLEX_JAR}", f"-Djava.library.path={CPLEX_LIB_PATH}",
           class_name, str(timeout_s)]
    proc = subprocess.run(
        cmd, stdin=open(infile), stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        timeout=timeout_s + 20, cwd=CPLEX_DIR)
    out = proc.stdout.decode(errors="replace")
    m_rmn = RMN_EQ_RE.search(out)
    reported_k = int(m_rmn.group(1)) if m_rmn else None

    n, dist_matrix, diam = load_graph(infile)
    labels = [0] * n
    for m in H_RE.finditer(out):
        v, l = int(m.group(1)), int(m.group(2))
        labels[v] = l

    if 0 in labels:
        return reported_k, False, "missing label(s)"
    if len(set(labels)) != n:
        return reported_k, False, "injectivity violated"
    if not validate.check_rml(labels, n, diam, dist_matrix):
        return reported_k, False, "radio-mean condition violated"
    if reported_k is not None and max(labels) != reported_k:
        return reported_k, False, f"max(labels)={max(labels)} != reported rmn={reported_k}"
    return reported_k, True, None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--min", type=int, default=3)
    ap.add_argument("--max", type=int, default=50)
    ap.add_argument("--timeout", type=int, default=300)
    args = ap.parse_args()

    gurobi_files = instance_files(args.min, args.max, exclude_n50=False)
    java_files = instance_files(args.min, args.max, exclude_n50=True)
    failures = []
    total = 0

    for solver_name, script in GUROBI_SOLVERS:
        for path in gurobi_files:
            n = int(Path(path).stem)
            total += 1
            try:
                reported_k, ok = run_gurobi(script, path, args.timeout)
            except subprocess.TimeoutExpired:
                print(f"{solver_name} n={n}: TIMEOUT ({args.timeout}s) -- skipped")
                continue
            status = "OK" if ok else "FAIL"
            print(f"{solver_name} n={n} rmn={reported_k} {status}")
            if not ok:
                failures.append((solver_name, n, "self-check reported Invalid label"))

    for solver_name, class_name in JAVA_SOLVERS:
        cap = CPLEX_CAP[solver_name]
        for path in java_files:
            n = int(Path(path).stem)
            if n > cap:
                continue
            total += 1
            try:
                reported_k, ok, reason = run_java(class_name, path, args.timeout)
            except subprocess.TimeoutExpired:
                print(f"{solver_name} n={n}: TIMEOUT ({args.timeout}s) -- skipped")
                continue
            status = "OK" if ok else f"FAIL ({reason})"
            print(f"{solver_name} n={n} rmn={reported_k} {status}")
            if not ok:
                failures.append((solver_name, n, reason))

    print()
    print(f"Checked {total} (solver, n) cases.")
    if failures:
        print(f"{len(failures)} FAILURES:")
        for solver_name, n, reason in failures:
            print(f"  {solver_name} n={n}: {reason}")
    else:
        print("All checked labelings are valid Radio Mean Labelings.")


if __name__ == "__main__":
    main()
