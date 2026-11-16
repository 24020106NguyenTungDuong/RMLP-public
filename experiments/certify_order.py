"""Proof-checked optimality for the order encoding (Section IV-A of the paper).

Only the instances the order encoding itself proves optimal (order_sb rows with status OPT in
results/results.csv: P3-P18, C5-C20) are certified.

For each instance:
  1. run the order solver with family SB (sat/order_sat_{path,cycle}.py), unmodified, under
     emit_order_cnf.py, which writes the CNF of its decisive UNSAT call at span rmn - 1,
     including symmetry breaking and the call's assumptions as unit clauses;
  2. re-check the witness labeling at span rmn against definition (1);
  3. solve the emitted CNF with the standalone CaDiCaL 1.9.5 binary, logging an LRAT proof;
  4. check the proof with lrat-check (drat-trim); its verdict is read from its output, since
     it exits 0 even on failure;
  5. xz-compress CNF and proof into results/proofs_order/ (archived on Zenodo, not in git).
If every span down to n is SAT, rmn = n follows from injectivity.

What this relies on: Lemma 2, Lemma 4, Lemma 5, Theorem 1 and Proposition 2 of the paper, the
encoder (sat/common/encoding.py and the solver files), and the checker.

Appends to results/certify_order.csv and resumes. Paths to CaDiCaL and lrat-check: config.py.
"""

import argparse
import csv
import os
import re
import subprocess
import time

import runlock
from config import CADICAL, DATASETS, LRAT_CHECK, PY, REPO, RESULTS


def check_witness(fam, n, h):
    """Definition (1) on P_n or C_n."""
    diam = n - 1 if fam == "P" else n // 2
    dist = (lambda u, v: abs(u - v)) if fam == "P" else (lambda u, v: min(abs(u - v), n - abs(u - v)))
    return len(set(h)) == n and min(h) >= 1 and all(
        -(-(h[u] + h[v]) // 2) >= diam + 1 - dist(u, v) for u in range(n) for v in range(u + 1, n))


HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(RESULTS, "certify_order.csv")
ARCHIVE = os.path.join(RESULTS, "proofs_order")      # large; on Zenodo, not in git
RESULTS_CSV = os.path.join(RESULTS, "results.csv")
FAMILY_DIR = {"P": "path", "C": "cycle"}
FIELDS = ["family", "n", "rmn", "search_s", "witness_valid", "unsat_k", "cnf_vars", "cnf_clauses",
          "cadical_result", "solve_s", "check_verdict", "check_s", "cnf_xz_bytes", "proof_bytes",
          "proof_xz_bytes"]


def proved_by_order():
    with open(RESULTS_CSV) as f:
        return sorted(((r["family"], int(r["n"])) for r in csv.DictReader(f)
                       if r["arm"] == "order_sb" and r["status"] == "OPT"), key=lambda x: ("PC".index(x[0]), x[1]))


def certify(fam, n, budget, archive):
    name = f"{fam}{n}"
    cnf, prf = os.path.join(archive, f"{name}.cnf"), os.path.join(archive, f"{name}.lrat")
    for stale in (cnf, prf):
        if os.path.exists(stale):
            os.remove(stale)
    solver = os.path.join(REPO, "sat", f"order_sat_{FAMILY_DIR[fam]}.py")
    infile = os.path.join(DATASETS, FAMILY_DIR[fam], f"{n}.txt")
    t = time.perf_counter()
    try:
        with open(infile) as fin:
            out = subprocess.run([PY, "-u", os.path.join(HERE, "emit_order_cnf.py"), solver, cnf],
                                 stdin=fin, capture_output=True, text=True, timeout=budget,
                                 cwd=os.path.join(REPO, "sat")).stdout
    except subprocess.TimeoutExpired:
        return {"family": fam, "n": n, "cadical_result": f"search timeout ({budget} s)", "check_verdict": "n/a"}
    search_s = f"{time.perf_counter() - t:.2f}"
    rmn = int(re.search(r"rmn\(G\) = (\d+)", out).group(1))
    final = out[out.index(f"rmn(G) = {rmn}"):]               # labeling printed after the final verdict
    labels = {int(v): int(l) for v, l in re.findall(r"^h\((\d+)\) = (\d+)$", final, re.M)}
    h = [labels[v] for v in range(n)]
    row = {"family": fam, "n": n, "rmn": rmn, "search_s": search_s,
           "witness_valid": check_witness(fam, n, h) and max(h) == rmn}
    if not os.path.exists(cnf):
        return {**row, "cadical_result": "n/a (rmn = n)", "check_verdict": "n/a"}
    with open(cnf) as f:
        _, _, nv, nc = next(l for l in f if l.startswith("p cnf")).split()
    row.update(unsat_k=rmn - 1, cnf_vars=nv, cnf_clauses=nc)

    t = time.perf_counter()
    try:
        rc = subprocess.run([CADICAL, "-q", "--lrat", "--binary=false", cnf, prf],
                            stdout=subprocess.DEVNULL, timeout=budget).returncode
    except subprocess.TimeoutExpired:
        return {**row, "cadical_result": f"proof timeout ({budget} s)", "check_verdict": "n/a"}
    solve_s = time.perf_counter() - t
    t = time.perf_counter()
    log = subprocess.run([LRAT_CHECK, cnf, prf], capture_output=True, text=True).stdout
    check_s = time.perf_counter() - t
    ok = "c VERIFIED" in log and "NOT VERIFIED" not in log
    proof_bytes = os.path.getsize(prf)
    subprocess.run(["xz", "-f", "-T1", cnf, prf], check=True)
    return {**row, "cadical_result": {20: "UNSAT", 10: "SAT"}.get(rc, f"rc{rc}"),
            "solve_s": f"{solve_s:.3f}", "check_verdict": "VERIFIED" if ok else "NOT_VERIFIED",
            "check_s": f"{check_s:.3f}", "cnf_xz_bytes": os.path.getsize(cnf + ".xz"),
            "proof_bytes": proof_bytes, "proof_xz_bytes": os.path.getsize(prf + ".xz")}


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--budget", type=int, default=3600, help="seconds per step (certification, not timing)")
    p.add_argument("--only", default="", help="comma-separated instances, e.g. P8,C12 (default: all order-proved)")
    p.add_argument("--out", default=OUT)
    p.add_argument("--archive", default=ARCHIVE)
    a = p.parse_args()
    run_lock = runlock.acquire()  # noqa: F841 -- held until exit
    os.makedirs(a.archive, exist_ok=True)
    todo = proved_by_order()
    if a.only:
        todo = [(x[0], int(x[1:])) for x in a.only.split(",")]
    done = set()
    if os.path.exists(a.out):
        with open(a.out) as f:
            done = {(r["family"], int(r["n"])) for r in csv.DictReader(f)}
    new = not os.path.exists(a.out)
    with open(a.out, "a", newline="") as f:
        wr = csv.DictWriter(f, fieldnames=FIELDS, restval="")
        if new:
            wr.writeheader()
        for fam, n in todo:
            if (fam, n) in done:
                continue
            row = certify(fam, n, a.budget, a.archive)
            wr.writerow(row)
            f.flush()
            print(fam, n, row.get("rmn", ""), row.get("witness_valid", ""), row["cadical_result"],
                  row["check_verdict"], row.get("proof_xz_bytes", ""), flush=True)


if __name__ == "__main__":
    main()
