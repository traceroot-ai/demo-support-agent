"""Tests for the fault schedule.

Run with: python -m unittest discover tests
"""

from __future__ import annotations

import sys
import unittest
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from state_bot import (  # noqa: E402
    CYCLE_DAYS,
    EPOCH,
    SCHEDULE,
    active_faults,
    parse_fixed_faults,
)

CYCLE = [EPOCH + timedelta(days=i) for i in range(CYCLE_DAYS)]


class ScheduleTest(unittest.TestCase):
    def test_each_fault_is_on_three_days_a_cycle(self):
        for fault in SCHEDULE:
            self.assertEqual(sum(fault in active_faults(d) for d in CYCLE), 3, fault)

    def test_faults_start_the_cycle_on_different_days(self):
        # On EPOCH, F1 is on its day 0 and F3 (which starts two days later) on its day 5.
        self.assertEqual(set(active_faults(EPOCH)), {"f1", "f3"})
        # Two days later: F2 is on its day 1, F3 on its day 0 and F5 on its day 5.
        self.assertEqual(set(active_faults(date(2026, 10, 14))), {"f2", "f3", "f5"})

    def test_a_fixed_fault_is_never_on(self):
        fixed = frozenset({"f3"})
        for day in CYCLE:
            self.assertNotIn("f3", active_faults(day, fixed))
        # The other faults keep their days.
        self.assertEqual(set(active_faults(EPOCH, fixed)), {"f1"})


class FixedFaultsTest(unittest.TestCase):
    def test_reads_a_comma_separated_list(self):
        self.assertEqual(parse_fixed_faults(" F3, f6 ,"), frozenset({"f3", "f6"}))

    def test_empty_means_no_fixed_faults(self):
        self.assertEqual(parse_fixed_faults(""), frozenset())

    def test_rejects_an_unknown_fault(self):
        with self.assertRaises(ValueError):
            parse_fixed_faults("f9")


if __name__ == "__main__":
    unittest.main()
