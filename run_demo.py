"""
Send demo traffic to the stable version and to fault versions at the same time.

Each fault is a real commit on its own `fault/*` branch. This script checks
out each chosen fault branch into a git worktree under `.worktrees/` and runs
the traffic driver there, so its traces carry that commit as the git ref.
The rest of the sessions run on the current checkout (the stable version).

Usage:
    python run_demo.py --sessions 40 --faults f1,f3 --fault-share 0.15
"""

from __future__ import annotations

import argparse
import random
import subprocess
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent
WORKTREES = ROOT / ".worktrees"

# The scenario that reaches the bug of each fault. Every session on a fault
# version runs this scenario, so each of its sessions reaches the bug, while
# the fault stays a small share of traffic.
FAULT_SCENARIOS = {
    "f1": "orders_since",
    "f2": "product_question",
    "f3": "large_refund",
    "f4": None,
    "f5": None,
    "f6": "track_and_refund",
}

FAULTS = {
    "f1": "fault/f1-us-date-format",
    "f2": "fault/f2-draft-filter",
    "f3": "fault/f3-refund-limit-config",
    "f4": "fault/f4-no-customer-cache",
    "f5": "fault/f5-bigger-agent-model",
    "f6": "fault/f6-chained-handoffs",
}


def _git(*args: str, cwd: Path = ROOT) -> None:
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True)


def checkout_fault(branch: str) -> Path:
    """Put the latest commit of a fault branch into its own worktree."""
    path = WORKTREES / branch.replace("/", "-")
    _git("fetch", "--quiet", "origin", branch)
    if path.exists():
        _git("checkout", "--quiet", "--detach", f"origin/{branch}", cwd=path)
    else:
        _git("worktree", "add", "--quiet", "--detach", str(path), f"origin/{branch}")
    return path


def run_mix(sessions: int, shares: dict[str, float], concurrency: int = 4) -> int:
    """Send `sessions` sessions. Each one runs on fault `f` with probability `shares[f]`.

    Each session is assigned on its own, so a small run can still reach a fault.
    Returns the highest exit code of the traffic driver processes.
    """
    stable = 1.0 - sum(shares.values())
    if stable < 0:
        raise ValueError("fault shares add up to more than 1")
    picks = random.choices([None, *shares], weights=[stable, *shares.values()], k=sessions)
    counts = Counter(picks)

    procs = []
    for fault, count in counts.items():
        cwd = ROOT if fault is None else checkout_fault(FAULTS[fault])
        focus = None if fault is None else FAULT_SCENARIOS[fault]
        print(f"{count:>4} sessions on {cwd.name}" + (f" (focus: {focus})" if focus else ""))
        cmd = [sys.executable, "traffic_driver.py", "--sessions", str(count)]
        cmd += ["--concurrency", str(concurrency)]
        if focus:
            cmd += ["--focus", focus, "--focus-share", "1"]
        procs.append(subprocess.Popen(cmd, cwd=cwd))
    return max((p.wait() for p in procs), default=0)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sessions", type=int, default=40, help="total sessions for this run")
    parser.add_argument("--faults", default="", help="comma-separated fault IDs, e.g. f1,f3")
    parser.add_argument(
        "--fault-share", type=float, default=0.15, help="share of sessions on all faults together"
    )
    parser.add_argument("--concurrency", type=int, default=4)
    args = parser.parse_args()

    faults = [f for f in args.faults.split(",") if f]
    unknown = [f for f in faults if f not in FAULTS]
    if unknown:
        parser.error(f"unknown faults: {', '.join(unknown)}")
    shares = {f: args.fault_share / len(faults) for f in faults}
    sys.exit(run_mix(args.sessions, shares, args.concurrency))


if __name__ == "__main__":
    main()
