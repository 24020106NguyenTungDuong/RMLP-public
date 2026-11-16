"""Progress of the experiments: rows in results/results.csv per arm and family, against the
number of instances, with the status counts (OPT = proved optimal, TO = time limit)."""

import csv
import os
from collections import Counter

from campaign import ARMS, INSTANCES
from config import RESULTS


def main():
    path = os.path.join(RESULTS, "results.csv")
    rows = list(csv.DictReader(open(path))) if os.path.exists(path) else []
    for arm, (families, *_rest) in ARMS.items():
        for fam in families:
            mine = [r for r in rows if r["arm"] == arm and r["family"] == fam]
            st = Counter(r["status"] for r in mine)
            print(f"{arm:11s} {fam} {len(mine):3d}/{len(INSTANCES[fam]):<3d} "
                  + " ".join(f"{k}={v}" for k, v in sorted(st.items())))
    bad = [r for r in rows if r["status"] == "ERR" or r["labels_valid"] == "False"]
    if bad:
        print(f"{len(bad)} row(s) need attention (ERR or invalid labeling)")


if __name__ == "__main__":
    main()
