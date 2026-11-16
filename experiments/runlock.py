"""One run at a time across all experiment scripts: timings are only comparable if nothing
else is running."""

import fcntl
import os
import sys

from config import RESULTS

LOCK_PATH = os.path.join(RESULTS, ".lock")


def acquire():
    """Hold the lock for the life of the process; exit if another run holds it."""
    os.makedirs(os.path.dirname(LOCK_PATH), exist_ok=True)
    handle = open(LOCK_PATH, "w")
    try:
        fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        sys.exit(f"another run holds {LOCK_PATH} -- runs must not overlap")
    return handle
