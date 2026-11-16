"""CPLEX counterpart of ilp_diagnostics.py (Reviewer 2, W1 and W3).

Runs CplexDiagnostics.java (same model and defaults as the campaign's cpx_sb arm,
log on) per instance and writes results/cplex_diagnostics/<instance>.log plus
summary.csv with: rows before/after presolve, root relaxation, root bound
after cuts, nodes, final bound, objective, CPLEX status, runtime, time the
best labeling was found, the incumbent sequence, peak memory. Holds the
run lock, so it cannot overlap a batch.

--mode nocb drops the incumbent callback the timed solver uses (it disables
some presolve reductions and roughly doubles memory on P44); outputs then go
to <instance>-nocb.log and summary-nocb.csv. In both modes the time of each
incumbent comes from the log's line timestamps (t_best_log_s, incumbents).
CPLEX writes its log in bursts, so these are upper bounds: when the incumbent
was reported, not when it was found (P20: found 0.69 s, logged 1.01 s). Rows
are appended as instances finish; a rerun skips instances already in the
summary.

The memory tests (batch 16) add --mode emptycb | lazyparams | progress, the
root-node tuning (batch 17) --mode tune-bound | tune-cliques | tune-probe,
--threads N and --seed S (CPLEX RandomSeed; omitted = CPLEX's default, as in
batches 14-17; the timed solver uses 0). See CplexDiagnostics.java. Outputs go
to <instance>-<mode>[-t<N>][-s<S>].log and summary-<mode>[-t<N>][-s<S>].csv.

  python3 cplex_diagnostics.py [P20 C49 ...] [--budget 900] [--mode MODE] [--threads N] [--seed S]
"""

import argparse
import csv
import os
import re
import subprocess
import time

import runlock

from config import CPLEX_HOME as CPLEX, DATASETS, RESULTS, RUNLIM

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(RESULTS, "cplex_diagnostics")
FAMILY_DIR = {"P": "path", "C": "cycle"}
DEFAULT = ["P20", "P30", "P40", "P44", "P45", "P50", "C20", "C30", "C40", "C49", "C50"]
MODES = ["cb", "nocb", "emptycb", "lazyparams", "progress", "tune-bound", "tune-cliques", "tune-probe"]
FIELDS = ["instance", "mode", "threads", "seed", "rows", "cols", "presolved_rows", "root_lp", "root_last", "root_time",
          "nodes", "best_bound", "obj", "status", "runtime_s", "t_opt_incumbent_s", "t_best_log_s",
          "incumbents", "cuts", "peak_mb", "runlim_status", "finished_at"]
STAMP = re.compile(r"^\[\s*([\d.]+)\] ", re.M)


def incumbents(text):
    """(time, value) for every new incumbent ("*" node-log line), from the line timestamps."""
    found = []
    for t, line in re.findall(r"^\[\s*([\d.]+)\] (\*.*)$", text, re.M):
        vals = re.findall(r"\d+\.\d+", line)
        if vals:
            found.append((float(t), round(float(vals[0]))))
    return found


def parse_log(raw):
    text = STAMP.sub("", raw)
    reduced = re.findall(r"Reduced MIP has (\d+) rows, (\d+) columns", text)
    root = re.search(r"Root relaxation solution time = ([\d.]+) sec", text)
    # Node log: LP lines for node 0 have no "*"/"+" (those are heuristic incumbents);
    # the first gives the root LP objective, later "Cuts:" lines raise it.
    node0 = re.findall(r"^\s+0\s+[02]\s+([\d.]+|infeasible|cutoff)\s", text, re.M)
    cuts = re.findall(r"^(\w[\w -]+) cuts applied:\s+(\d+)", text, re.M)
    inc = incumbents(raw)
    best = min((v for _, v in inc), default=None)
    return {"presolved_rows": reduced[-1][0] if reduced else "",
            "root_lp": node0[0] if node0 else "",
            "root_last": node0[-1] if node0 else "",
            "root_time": root.group(1) if root else "",
            "t_best_log_s": next((f"{t:.2f}" for t, v in inc if v == best), ""),
            "incumbents": " ".join(f"{v}@{t:.0f}s" for t, v in inc),
            "cuts": "; ".join(f"{k.strip()}={v}" for k, v in cuts)}


def main():
    p = argparse.ArgumentParser()
    p.add_argument("instances", nargs="*", default=DEFAULT)
    p.add_argument("--budget", type=int, default=900)
    p.add_argument("--mode", choices=MODES, default="cb")
    p.add_argument("--threads", type=int, default=0, help="CPLEX Threads parameter; 0 = all cores")
    p.add_argument("--seed", type=int, default=None, help="CPLEX RandomSeed; default: CPLEX's own")
    a = p.parse_args()
    run_lock = runlock.acquire()  # noqa: F841 -- held until exit
    os.makedirs(OUT, exist_ok=True)
    subprocess.run(["javac", "-cp", f"{CPLEX}/lib/cplex.jar", "-d", OUT,
                    os.path.join(HERE, "CplexDiagnostics.java")], check=True)
    suffix = (("" if a.mode == "cb" else f"-{a.mode}") + (f"-t{a.threads}" if a.threads else "")
              + (f"-s{a.seed}" if a.seed is not None else ""))
    summary = os.path.join(OUT, f"summary{suffix}.csv")
    done = set()
    if os.path.exists(summary):
        with open(summary) as f:
            done = {r["instance"] for r in csv.DictReader(f)}
    for inst in a.instances:
        if inst in done:
            print(f"{inst}: already in {summary}, skipped", flush=True)
            continue
        fam, n = inst[0], int(inst[1:])
        log = os.path.join(OUT, f"{inst}{suffix}.log")
        rl = os.path.join(OUT, f"{inst}{suffix}.runlim")
        cmd = [RUNLIM, "-r", str(a.budget + 30), "-s", "26000", "-o", rl,
               "java", "-cp", f"{OUT}:{CPLEX}/lib/cplex.jar", f"-Djava.library.path={CPLEX}/bin/x86-64_linux",
               "CplexDiagnostics", fam, log, str(a.budget), a.mode, str(a.threads)]
        if a.seed is not None:
            cmd.append(str(a.seed))
        with open(os.path.join(DATASETS, FAMILY_DIR[fam], f"{n}.txt")) as fin:
            out = subprocess.run(cmd, stdin=fin, capture_output=True, text=True,
                                 start_new_session=True).stdout
        summ = dict(re.findall(r"(\w+)=(\S+)", out))
        rltext = open(rl).read()
        peak = re.search(r"\[runlim\] space:\s+(\d+)", rltext)
        rlstat = re.search(r"\[runlim\] status:\s+(.*)", rltext)
        row = {"instance": inst, "mode": a.mode, "threads": a.threads,
               "seed": "" if a.seed is None else a.seed, **summ,
               **(parse_log(open(log).read()) if os.path.exists(log) else {}),
               "peak_mb": peak.group(1) if peak else "", "runlim_status": rlstat.group(1).strip() if rlstat else "",
               "finished_at": time.strftime("%Y-%m-%d %H:%M:%S")}
        new = not os.path.exists(summary)
        with open(summary, "a", newline="") as f:
            wr = csv.DictWriter(f, fieldnames=FIELDS, extrasaction="ignore")
            if new:
                wr.writeheader()
            wr.writerow(row)
        print(row, flush=True)


if __name__ == "__main__":
    main()
