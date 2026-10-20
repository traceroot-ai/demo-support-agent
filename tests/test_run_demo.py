"""Tests for run_demo.run_mix.

Run with: python -m unittest discover tests
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import run_demo  # noqa: E402


class RunMixTest(unittest.TestCase):
    def test_each_version_names_its_own_commit(self):
        # In GitHub Actions, GITHUB_SHA is the commit of the workflow run. The
        # traces of a fault version must carry the fault commit instead.
        fault_path = run_demo.WORKTREES / "fault-f1-us-date-format"
        heads = {run_demo.ROOT: "stable-sha", fault_path: "fault-sha"}
        with (
            mock.patch.object(run_demo, "checkout_fault", return_value=fault_path),
            mock.patch.object(run_demo, "_head", side_effect=heads.__getitem__),
            mock.patch.object(run_demo.random, "choices", return_value=[None, "f1"]),
            mock.patch.object(run_demo.subprocess, "Popen") as popen,
            mock.patch.dict(run_demo.os.environ, {"GITHUB_SHA": "workflow-sha"}),
        ):
            popen.return_value.wait.return_value = 0
            self.assertEqual(run_demo.run_mix(2, {"f1": 0.5}), 0)

        refs = {c.kwargs["cwd"]: c.kwargs["env"]["TRACEROOT_GIT_REF"] for c in popen.call_args_list}
        self.assertEqual(refs, heads)


if __name__ == "__main__":
    unittest.main()
