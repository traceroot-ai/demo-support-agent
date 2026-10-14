"""
State bot for the TraceRoot demo project.

A scheduled workflow runs this script every 12 hours. Each run:

1. finds the faults that are on today,
2. sends this run's sessions with `run_demo.run_mix`.

Each fault follows a 7-day cycle, and each fault starts the cycle on a
different day:

    day 0, 1  on    its problem shows up in new traces, findings and alerts
    day 2-4   off   its alert goes back to OK
    day 5     on    its problem comes back
    day 6     off

So on any day some faults are on and some are off. The detectors, signals
and alerts follow the traffic by themselves. The bot does not change the
status of signals: a member sets a few of them once, by hand (see the
README).

FIXED_FAULTS lists the faults that the team fixed in an environment, for
example "f3". The bot does not turn them on again there, so their resolved
signals stay resolved.

Usage:
    python state_bot.py              # send this run's traffic
    python state_bot.py --dry-run    # print the plan for the next 7 days, and send nothing
"""

from __future__ import annotations

import argparse
import os
import sys
from datetime import UTC, date, datetime, timedelta

from run_demo import FAULTS, run_mix

EPOCH = date(2026, 10, 12)
CYCLE_DAYS = 7
ON_DAYS = {0, 1, 5}

# fault ID -> (first day of its cycle after EPOCH, share of sessions while it is on).
# F4 and F5 drive alerts, which need a larger share than detectors do.
SCHEDULE = {
    "f1": (0, 0.05),
    "f2": (1, 0.05),
    "f3": (2, 0.05),
    "f4": (3, 0.10),
    "f5": (4, 0.10),
    "f6": (5, 0.05),
}

DEFAULT_SESSIONS_PER_RUN = 20


def active_faults(day: date, fixed: frozenset[str] = frozenset()) -> dict[str, float]:
    """Return the faults that are on for `day`, with their share of sessions.

    A fault in `fixed` is never on.
    """
    days = (day - EPOCH).days
    return {
        fault: share
        for fault, (offset, share) in SCHEDULE.items()
        if fault not in fixed and (days - offset) % CYCLE_DAYS in ON_DAYS
    }


def parse_fixed_faults(value: str) -> frozenset[str]:
    """Read FIXED_FAULTS, a comma-separated list such as "f3" or "f3,f6"."""
    fixed = frozenset(f.strip().lower() for f in value.split(",") if f.strip())
    unknown = fixed - set(SCHEDULE)
    if unknown:
        raise ValueError(f"unknown faults in FIXED_FAULTS: {', '.join(sorted(unknown))}")
    return fixed


def print_plan(start: date, fixed: frozenset[str]) -> None:
    for i in range(CYCLE_DAYS):
        day = start + timedelta(days=i)
        faults = active_faults(day, fixed)
        share = sum(faults.values())
        print(f"{day}  {', '.join(sorted(faults)) or '-':<14} {share:4.0%} of sessions on faults")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="print what a run would do")
    parser.add_argument("--sessions", type=int, help="sessions for this run")
    parser.add_argument("--concurrency", type=int, default=3)
    args = parser.parse_args()

    unknown = set(SCHEDULE) - set(FAULTS)
    if unknown:
        sys.exit(f"faults in SCHEDULE but not in run_demo.FAULTS: {', '.join(sorted(unknown))}")
    # No default host: a missing setting must not send demo traffic to the wrong TraceRoot.
    host = os.environ.get("TRACEROOT_HOST_URL")
    if not host:
        sys.exit("TRACEROOT_HOST_URL is not set")
    try:
        fixed = parse_fixed_faults(os.environ.get("FIXED_FAULTS", ""))
    except ValueError as e:
        sys.exit(str(e))

    now = datetime.now(UTC)
    faults = active_faults(now.date(), fixed)
    if args.dry_run:
        print_plan(now.date(), fixed)
    print(f"{now:%Y-%m-%d %H:%M} UTC on {host}: faults on: {', '.join(sorted(faults)) or 'none'}")
    if fixed:
        print(f"fixed, never on: {', '.join(sorted(fixed))}")

    sessions = args.sessions
    if sessions is None:
        sessions = int(os.environ.get("SESSIONS_PER_RUN") or DEFAULT_SESSIONS_PER_RUN)
    if args.dry_run:
        print(f"{sessions} sessions (dry run: none sent)")
        return
    missing = [name for name in ("TRACEROOT_API_KEY", "OPENAI_API_KEY") if not os.environ.get(name)]
    if missing:
        sys.exit(f"not set: {', '.join(missing)}")
    print(f"{sessions} sessions")
    if sessions:
        sys.exit(run_mix(sessions, faults, args.concurrency))


if __name__ == "__main__":
    main()
