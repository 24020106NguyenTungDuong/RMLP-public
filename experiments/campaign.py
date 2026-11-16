"""Experiment campaign: runs every method on every instance under one protocol.

  * a flat wall-clock budget per (arm, instance), default 900 s, enforced by runlim, which also
    reports CPU time and peak memory; the ILP and CP solvers also get the budget as their own
    time limit, so they stop cleanly and report their incumbent;
  * python -u (unbuffered); the solvers print every improved labeling;
  * every labeling a solver reports is re-checked here against definition (1) of the paper,
    independently of the solver's own check;
  * ILP and CP solvers at their default settings (solver-default threads, i.e. all cores;
    seed 0; default gaps and node files) unless overridden;
  * --jobs 1 (default) is fully sequential and unpinned; --jobs > 1 pins each job to its own
    physical core and needs --threads 1;
  * runlock.py refuses to start while another run is active.

Results go to results/: results.csv (one row per run, appended, so the campaign resumes where
it stopped), raw/<arm>/<instance>.out|.runlim, and manifest-<timestamp>.json (versions,
machine, git state, arguments). Paths to runlim, CPLEX and CP Optimizer: see config.py.

Arms (method and symmetry breaking) are listed in ARMS below; the paper's runs are in batches/.

Examples:
  python3 campaign.py --dry-run
  python3 campaign.py --arms order_sb --families P --budget 60 --max-n 15 --out-dir /tmp/smoke
"""

import argparse
import csv
import json
import os
import platform
import queue
import re
import subprocess
import sys
import threading
import time

import runlock

from config import CPLEX_HOME, DATASETS, FAMILY_DIR, PY, REPO, RESULTS, RUNLIM

ROOT = REPO
SAT_DIR = os.path.join(REPO, "sat")
GRB_DIR = os.path.join(REPO, "gurobi")
CPX_DIR = os.path.join(REPO, "cplex")          # compile the .java files here first (README)
CP_DIR = os.path.join(REPO, "cp")
OUT_DIR = RESULTS
INSTANCES = {"P": range(3, 51), "C": range(5, 51),
             "W": range(4, 50), "S": range(2, 25), "L": range(2, 26), "G": range(2, 8), "T": range(5, 51)}
PHYSICAL_CORES = [0, 2, 4, 6, 8, 10]      # one logical CPU per physical core (siblings are 2i, 2i+1)
ILP_GRACE_S = 30                          # runlim margin after the ILP's own TimeLimit, for JVM/print exit


def _py(script, *extra):
    return lambda fam, a: [PY, "-u", script, *extra]


def _py_fam(template, *extra):
    return lambda fam, a: [PY, "-u", template.format(fam=FAMILY_DIR[fam]), *extra]


def _gurobi(template):
    return lambda fam, a: [PY, "-u", template.format(fam=FAMILY_DIR[fam]),
                           "--threads", str(a.threads), "--seed", str(a.seed),
                           "--time-limit", str(a.budget)]


def _cplex(cls):
    def cmd(fam, a):
        name = cls.format(Fam=FAMILY_DIR[fam].capitalize())
        return ["java", "-cp", f".:{CPLEX_HOME}/lib/cplex.jar",
                f"-Djava.library.path={CPLEX_HOME}/bin/x86-64_linux",
                f"-Drml.threads={a.threads}", f"-Drml.seed={a.seed}",
                f"-Drml.workmem={a.cplex_workmem}", f"-Drml.nodefile={a.cplex_nodefile}",
                name, str(a.budget)]
    return cmd


# name -> (families, command builder, working dir, is_ilp, paper role)
ARMS = {
    "order_sb":   ("PC", _py_fam("order_sat_{fam}.py"), SAT_DIR, False, "order SAT, family SB"),
    "order_none": ("PCWSLGT", _py("order_sat_general.py"), SAT_DIR, False,
                   "order SAT, no family SB (keeps the distance-twin clauses, Lemma 5)"),
    "order_rot":  ("C",  _py("order_sat_cycle.py", "--sb", "rotation"), SAT_DIR, False, "order SAT, cycles, rotation SB only"),
    "basic_sb":   ("PC", _py_fam("simple_sat_{fam}.py"), SAT_DIR, False, "Basic SAT, family SB"),
    "basic_none": ("PCWSLGT", _py("simple_sat_general.py"), SAT_DIR, False, "Basic SAT, no SB"),
    "grb_sb":     ("PC", _gurobi("proposed_ilp_gurobi_{fam}.py"), GRB_DIR, True, "ILP via Gurobi, family SB"),
    "grb_none":   ("PCWSLGT", _gurobi("proposed_ilp_gurobi_general.py"), GRB_DIR, True, "ILP via Gurobi, no SB"),
    "cpx_sb":     ("PC", _cplex("ProposedIlpCplex{Fam}"), CPX_DIR, True, "ILP via CPLEX, family SB"),
    "cpx_none":   ("PCWSLGT", _cplex("ProposedIlpCplexGeneral"), CPX_DIR, True, "ILP via CPLEX, no SB"),
    "cp_none":    ("PCWSLGT", _gurobi("cp_general.py"), CP_DIR, True, "CP model (CP Optimizer), no SB"),
}

FIELDS = ["arm", "family", "n", "status", "proven_rmn", "best_span", "time_to_best_s",
          "wall_s", "cpu_s", "peak_mb", "labels_checked", "labels_valid", "runlim_status",
          "exit_code", "final_call_stats", "cpu", "finished_at"]
LE_RE = re.compile(r"rmn\(G\) <= (\d+)")
EQ_RE = re.compile(r"rmn\(G\) = (\d+)")
TIME_RE = re.compile(r"Execution time: ([\d.]+) s")
H_RE = re.compile(r"^h\((\d+)\) = (\d+)$")
STATS_RE = re.compile(r"^Final call stats: (.*)$")


def _from_file(fam, m):
    """Order, diameter and distance function of a further-family instance, by BFS on its file."""
    rows = open(os.path.join(DATASETS, FAMILY_DIR[fam], f"{m}.txt")).read().split("\n")
    order = int(rows[0])
    adj = [list(map(int, r.split())) for r in rows[1:order + 1]]
    d = []
    for s in range(order):
        ds, frontier = [-1] * order, [s]
        ds[s] = 0
        while frontier:
            nxt = []
            for u in frontier:
                for v in range(order):
                    if adj[u][v] and ds[v] < 0:
                        ds[v] = ds[u] + 1
                        nxt.append(v)
            frontier = nxt
        d.append(ds)
    return order, max(map(max, d)), (lambda u, v: d[u][v])


def order_of(fam, n):
    return n if fam in "PC" else _from_file(fam, n)[0]


def graph_of(fam, n):
    if fam == "P":
        return n - 1, (lambda u, v: abs(u - v))
    if fam == "C":
        return n // 2, (lambda u, v: min(abs(u - v), n - abs(u - v)))
    return _from_file(fam, n)[1:]


def check_labeling(fam, n, h):
    """Definition (1), checked here, independently of the solver's own check.
    n is the instance parameter; for the further families the order is read from the file."""
    diam, dist = graph_of(fam, n)
    n = order_of(fam, n)
    if len(h) != n or len(set(h)) != n or min(h) < 1:
        return False
    return all(-(-(h[u] + h[v]) // 2) >= diam + 1 - dist(u, v)
               for u in range(n) for v in range(u + 1, n))


def parse_solver_output(text, fam, n):
    param, n = n, order_of(fam, n)      # labelings have one label per vertex of the order
    best, best_t, proven, stats = None, None, None, ""
    labelings, cur = [], {}
    lines = text.splitlines()
    for i, line in enumerate(lines):
        m_le, m_eq = LE_RE.search(line), EQ_RE.search(line)
        if m_le or m_eq:
            k = int((m_le or m_eq).group(1))
            t = next((float(m.group(1)) for j in range(i + 1, min(i + 3, len(lines)))
                      if (m := TIME_RE.search(lines[j]))), None)
            if m_eq:
                proven = k
            if best is None or k < best:
                best, best_t = k, t
        m_h = H_RE.match(line.strip())
        if m_h:
            v, lab = int(m_h.group(1)), int(m_h.group(2))
            if v in cur:
                cur = {}
            cur[v] = lab
            if len(cur) == n:
                labelings.append([cur[i] for i in range(n)])
                cur = {}
        m_s = STATS_RE.match(line.strip())
        if m_s:
            stats = m_s.group(1)
    # Check the labeling that backs the best span: the last complete one with that span.
    backing = [h for h in labelings if max(h) == best] if best is not None else []
    checked = bool(backing)
    valid = check_labeling(fam, param, backing[-1]) if checked else None
    return best, best_t, proven, stats, checked, valid


def parse_runlim(text):
    get = lambda key: (re.search(rf"\[runlim\] {key}:\s+(.*)", text) or [None, None])[1]
    num = lambda s: float(s.split()[0]) if s else None
    return get("status"), num(get("real")), num(get("time")), num(get("space"))


def run_one(arm, fam, n, a, cpu):
    families, build, cwd, is_ilp, _ = ARMS[arm]
    raw = os.path.join(OUT_DIR, "raw", arm)
    os.makedirs(raw, exist_ok=True)
    out_path = os.path.join(raw, f"{fam}{n}.out")
    rl_path = os.path.join(raw, f"{fam}{n}.runlim")
    wall_cap = a.budget + (ILP_GRACE_S if is_ilp else 0)
    pin = ["taskset", "-c", str(cpu)] if cpu is not None else []
    cmd = [*pin, RUNLIM, "-r", str(wall_cap), "-s", str(a.space_mb), "-o", rl_path, *build(fam, a)]
    infile = os.path.join(DATASETS, FAMILY_DIR[fam], f"{n}.txt")
    env = dict(os.environ)          # GRB_LICENSE_FILE and CPO_EXEC pass through
    with open(infile) as fin, open(out_path, "w") as fout:
        # Own session per job: runlim signals its whole process group on exit,
        # which would otherwise kill the other jobs' solvers.
        proc = subprocess.Popen(cmd, stdin=fin, stdout=fout, stderr=subprocess.STDOUT,
                                cwd=cwd, env=env, start_new_session=True)
        rc = proc.wait()
    text = open(out_path, errors="replace").read()
    rl_status, wall, cpu_s, peak = parse_runlim(open(rl_path, errors="replace").read())
    best, best_t, proven, stats, checked, valid = parse_solver_output(text, fam, n)
    oom = rl_status == "out of memory" or re.search(r"out of memory|OutOfMemory|CPLEX Error\s+1001",
                                                    text, re.IGNORECASE)
    if proven is not None and rl_status == "ok":
        status = "OPT"
    elif oom:
        status = "OOM"
    elif rl_status == "out of time" or "time limit reached" in text:
        status = "TO"
    else:
        status = "ERR"
    return {"arm": arm, "family": fam, "n": n, "status": status,
            "proven_rmn": proven if status == "OPT" else "", "best_span": best or "",
            "time_to_best_s": best_t if best_t is not None else "", "wall_s": wall,
            "cpu_s": cpu_s, "peak_mb": peak, "labels_checked": checked,
            "labels_valid": "" if valid is None else valid, "runlim_status": rl_status,
            "exit_code": rc, "final_call_stats": stats, "cpu": "all" if cpu is None else cpu,
            "finished_at": time.strftime("%Y-%m-%d %H:%M:%S")}


def manifest(a, jobs):
    def sh(cmd):
        try:
            return subprocess.run(cmd, capture_output=True, text=True, timeout=30).stdout.strip()
        except Exception as e:          # record, don't abort the campaign
            return f"unavailable: {e}"
    return {
        "started": time.strftime("%Y-%m-%d %H:%M:%S"), "args": vars(a), "jobs": jobs,
        "git_head": sh(["git", "-C", ROOT, "rev-parse", "HEAD"]),
        "git_dirty_files": sh(["git", "-C", ROOT, "status", "--porcelain", "sat", "gurobi", "cplex", "cp"]),
        "cpu": sh(["bash", "-c", "lscpu | grep 'Model name'"]),
        "mem_total": sh(["bash", "-c", "grep MemTotal /proc/meminfo"]),
        "kernel": platform.release(), "os": sh(["bash", "-c", "grep PRETTY_NAME /etc/os-release"]),
        "python": sh([PY, "--version"]),
        "pysat": sh([PY, "-c", "import pysat; print(pysat.__version__)"]),
        "gurobi": sh([PY, "-c", "import gurobipy; print(gurobipy.gurobi.version())"]),
        "java": sh(["bash", "-c", "java -version 2>&1 | head -1"]),
        "cplex_home": CPLEX_HOME,
        "runlim": sh([RUNLIM, "--version"]),
    }


def main():
    global OUT_DIR
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--arms", default=",".join(ARMS), help="comma-separated, default all: " + ",".join(ARMS))
    p.add_argument("--families", default="PC")
    p.add_argument("--min-n", type=int, default=0)
    p.add_argument("--max-n", type=int, default=50)
    p.add_argument("--budget", type=int, default=900, help="wall-clock seconds per run")
    p.add_argument("--space-mb", type=int, default=26000, help="runlim memory cap in MB (26 GB in the paper)")
    p.add_argument("--threads", type=int, default=0, help="ILP/CP solver threads (0 = solver default)")
    p.add_argument("--seed", type=int, default=0, help="ILP solver seed (0 = both solvers' default)")
    p.add_argument("--cplex-workmem", type=int, default=2048, help="CPLEX WorkMem MB (2048 = default)")
    p.add_argument("--cplex-nodefile", type=int, default=1, help="CPLEX NodeFileInd (1 = default)")
    p.add_argument("--jobs", type=int, default=1, help="1 = sequential, unpinned; >1 = pinned parallel")
    p.add_argument("--out-dir", default=OUT_DIR, help="use a scratch dir for smoke tests")
    p.add_argument("--dry-run", action="store_true")
    a = p.parse_args()
    OUT_DIR = a.out_dir

    arms = [x for x in a.arms.split(",") if x]
    unknown = set(arms) - set(ARMS)
    if unknown:
        sys.exit(f"unknown arms: {sorted(unknown)}")
    if a.jobs > 1 and a.threads != 1:
        sys.exit("--jobs > 1 needs --threads 1 (one physical core per job)")
    jobs = min(a.jobs, len(PHYSICAL_CORES))

    os.makedirs(OUT_DIR, exist_ok=True)
    res_path = os.path.join(OUT_DIR, "results.csv")
    done = set()
    if os.path.exists(res_path):
        done = {(r["arm"], r["family"], int(r["n"])) for r in csv.DictReader(open(res_path))}

    todo = [(arm, fam, n) for arm in arms for fam in ARMS[arm][0] if fam in a.families
            for n in INSTANCES[fam] if a.min_n <= n <= a.max_n and (arm, fam, n) not in done]
    print(f"{len(todo)} runs to do ({len(done)} already in {res_path}); "
          f"worst case {len(todo) * a.budget / 3600 / jobs:.1f} h with {jobs} job(s)")
    if a.dry_run:
        for arm, fam, n in todo[:20]:
            print(arm, fam, n, " ".join(ARMS[arm][1](fam, a)))
        return

    run_lock = runlock.acquire()  # noqa: F841 -- held until exit

    stamp = time.strftime("%Y%m%d-%H%M%S")
    with open(os.path.join(OUT_DIR, f"manifest-{stamp}.json"), "w") as f:
        json.dump(manifest(a, jobs), f, indent=2)

    work, lock = queue.Queue(), threading.Lock()
    for item in todo:
        work.put(item)
    new_file = not os.path.exists(res_path)
    fres = open(res_path, "a", newline="")
    wr = csv.DictWriter(fres, fieldnames=FIELDS)
    if new_file:
        wr.writeheader()

    def worker(cpu):
        while True:
            try:
                arm, fam, n = work.get_nowait()
            except queue.Empty:
                return
            row = run_one(arm, fam, n, a, cpu)
            with lock:
                wr.writerow(row)
                fres.flush()
                print(f"[cpu{cpu}] {arm} {fam}{n}: {row['status']} best={row['best_span']} "
                      f"wall={row['wall_s']}s peak={row['peak_mb']}MB valid={row['labels_valid']}",
                      flush=True)

    cpus = [None] if jobs == 1 else PHYSICAL_CORES[:jobs]
    threads = [threading.Thread(target=worker, args=(c,)) for c in cpus]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    fres.close()


if __name__ == "__main__":
    main()
