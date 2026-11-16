"""Does the proof checker really reject bad proofs? (Section IV-A of the paper; Reviewer 1, Concerns 4-5)

Takes one certified instance from certify_order.py (results/proofs_order/<inst>.cnf.xz and
.lrat.xz), checks the original proof (positive control), then three broken
variants that lrat-check must reject:
  truncated      the proof cut to its first half, so the empty clause is never derived;
  corrupted      one literal flipped in the first added clause with at least two
                 literals, so that step no longer follows from its hints;
  used_clause    the formula with the first original clause the proof cites
                 replaced by a tautology (numbering kept), so a step relies on a
                 clause the formula no longer has;
and one variant it must still accept:
  unused_clause  the formula with its last clause removed; the proof never cites
                 it, so the smaller formula is still refuted by the same proof
                 (LRAT names exactly the clauses each step uses).
lrat-check exits 0 even on failure, so the verdict is read from its output
("c VERIFIED" and no "NOT VERIFIED"). Writes results/negative_controls_order.csv
and prints one line per check. Temporary files go to a scratch directory that
is deleted afterwards.

  python3 negative_controls.py P18
  python3 negative_controls.py C20
"""

import argparse
import csv
import os
import shutil
import subprocess
import tempfile
import time

import runlock

from config import LRAT_CHECK, RESULTS   # lrat-check: drat-trim commit 2e3b2dc

PROOFS = os.path.join(RESULTS, "proofs_order")
OUT = os.path.join(RESULTS, "negative_controls_order.csv")


def check(cnf, proof):
    t = time.perf_counter()
    log = subprocess.run([LRAT_CHECK, cnf, proof], capture_output=True, text=True).stdout
    verified = "c VERIFIED" in log and "NOT VERIFIED" not in log
    last = [l for l in log.splitlines() if l.strip()][-1] if log.strip() else ""
    return verified, time.perf_counter() - t, last


def truncated(src, dst):
    with open(src) as f:
        lines = f.readlines()
    with open(dst, "w") as f:
        f.writelines(lines[:len(lines) // 2])
    return f"kept {len(lines) // 2} of {len(lines)} lines"


def corrupted(src, dst):
    note = None
    with open(src) as fin, open(dst, "w") as fout:
        for line in fin:
            parts = line.split()
            # addition lines: "<id> <lits...> 0 <hints...> 0"; deletion lines have "d" second
            if note is None and len(parts) > 2 and parts[1] != "d":
                lits = parts[1:parts.index("0", 1)]
                if len(lits) >= 2:
                    parts[1] = str(-int(parts[1]))
                    note = f"clause {parts[0]}: literal {lits[0]} -> {parts[1]}"
                    line = " ".join(parts) + "\n"
            fout.write(line)
    return note


def read_cnf(src):
    with open(src) as f:
        lines = f.readlines()
    header = next(i for i, l in enumerate(lines) if l.startswith("p cnf"))
    _, _, nvars, nclauses = lines[header].split()
    return nvars, int(nclauses), [l for l in lines[header + 1:] if l.strip() and not l.startswith("c")]


def unused_clause(src, dst):
    nvars, nclauses, clauses = read_cnf(src)
    with open(dst, "w") as f:
        f.write(f"p cnf {nvars} {nclauses - 1}\n")
        f.writelines(clauses[:-1])
    return f"removed clause {nclauses}: {clauses[-1].strip()}"


def used_clause(src, proof, dst):
    nvars, nclauses, clauses = read_cnf(src)
    with open(proof) as f:
        for line in f:
            parts = line.split()
            if len(parts) > 2 and parts[1] != "d":
                hints = [int(h) for h in parts[parts.index("0", 1) + 1:-1]]
                cited = next((h for h in hints if 0 < h <= nclauses), None)
                if cited:
                    break
    old = clauses[cited - 1].strip()
    clauses[cited - 1] = "1 -1 0\n"
    with open(dst, "w") as f:
        f.write(f"p cnf {nvars} {nclauses}\n")
        f.writelines(clauses)
    return f"clause {cited} ({old}) replaced by the tautology 1 -1"


def main():
    p = argparse.ArgumentParser()
    p.add_argument("instance", nargs="?", default="P18")
    p.add_argument("--proofs", default=PROOFS, help="directory with <inst>.cnf.xz and <inst>.lrat.xz")
    p.add_argument("--out", default=OUT)
    p.add_argument("--source", default="certify_order.py (order SAT)", help="where the proof came from (recorded in the CSV)")
    a = p.parse_args()
    run_lock = runlock.acquire()  # noqa: F841 -- held until exit
    tmp = tempfile.mkdtemp(prefix="negctl-")
    try:
        cnf, prf = os.path.join(tmp, "f.cnf"), os.path.join(tmp, "p.lrat")
        for name, dst in ((f"{a.instance}.cnf.xz", cnf), (f"{a.instance}.lrat.xz", prf)):
            with open(dst, "wb") as f:
                subprocess.run(["xz", "-dc", os.path.join(a.proofs, name)], stdout=f, check=True)
        cases = [("original", cnf, prf, f"proof from {a.source}, unchanged", True)]
        bad_prf, bad_lit, bad_cnf, short_cnf = (os.path.join(tmp, x) for x in
                                                ("trunc.lrat", "flip.lrat", "taut.cnf", "short.cnf"))
        cases.append(("truncated", cnf, bad_prf, truncated(prf, bad_prf), False))
        cases.append(("corrupted", cnf, bad_lit, corrupted(prf, bad_lit), False))
        cases.append(("used_clause", bad_cnf, prf, used_clause(cnf, prf, bad_cnf), False))
        cases.append(("unused_clause", short_cnf, prf, unused_clause(cnf, short_cnf), True))
        rows = []
        for case, c, pr, what, expect in cases:
            verified, secs, last = check(c, pr)
            rows.append({"instance": a.instance, "case": case, "modification": what,
                         "expected": "VERIFIED" if expect else "rejected",
                         "verdict": "VERIFIED" if verified else "rejected",
                         "as_expected": verified == expect, "check_s": f"{secs:.3f}",
                         "checker_last_line": last,
                         "checked_at": time.strftime("%Y-%m-%d %H:%M:%S")})
            print(rows[-1], flush=True)
    finally:
        shutil.rmtree(tmp)
    new = not os.path.exists(a.out)
    with open(a.out, "a", newline="") as f:
        wr = csv.DictWriter(f, fieldnames=list(rows[0]))
        if new:
            wr.writeheader()
        wr.writerows(rows)


if __name__ == "__main__":
    main()
