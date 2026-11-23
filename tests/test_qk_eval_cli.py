"""`qk eval prepare` and `qk eval grade`: the evaluator's case setup and grading, without an agent turn."""

import contextlib
import importlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock


SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))
qk = importlib.import_module("qk")
evaluator = importlib.import_module("qk_eval")

# Passes when the agent created done.txt and its final reply says "finished".
CHECK = '''import json, sys
from pathlib import Path
workdir, final = Path(sys.argv[1]), Path(sys.argv[2])
print(json.dumps([
    {"name": "file", "passed": (workdir / "done.txt").is_file(), "detail": ""},
    {"name": "reply", "passed": "finished" in final.read_text(), "detail": ""},
]))
'''


class EvalStepTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name).resolve()
        self.cases = self.root / "cases"
        task = self.cases / "tiny"
        (task / "repo").mkdir(parents=True)
        (task / "repo" / "a.txt").write_text("a\n")
        (task / "task.md").write_text("Create done.txt.\n")
        (task / "case.json").write_text('{"skill": "qk-cook", "write": true}')
        (task / "check.py").write_text(CHECK)
        review = self.cases / "tiny-review"
        (review / "repo").mkdir(parents=True)
        (review / "repo" / "a.txt").write_text("a\n")
        (review / "plan.md").write_text("# Plan\n")
        (review / "review.diff").write_text(
            "diff --git a/a.txt b/a.txt\n--- a/a.txt\n+++ b/a.txt\n@@ -1 +1 @@\n-a\n+b\n")
        (review / "case.json").write_text('{"skill": "runner-review", "write": false}')
        (review / "check.py").write_text(CHECK)
        patch = mock.patch.object(evaluator, "CASES", self.cases)
        patch.start()
        self.addCleanup(patch.stop)

    def cli(self, *argv):
        output, errors = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(output), contextlib.redirect_stderr(errors):
            status = qk.main(["eval", *argv])
        return status, output.getvalue(), errors.getvalue()

    def json(self, *argv):
        status, output, errors = self.cli(*argv, "--json")
        self.assertEqual((status, errors), (0, ""), argv)
        return json.loads(output)

    def test_prepare_builds_the_case_repository_with_its_task(self):
        reply = self.json("prepare", "tiny", str(self.root / "run"))
        workdir = self.root / "run" / "repo"
        self.assertEqual(reply, {"contract": 1, "case": "tiny", "skill": "qk-cook", "write": True,
                                 "workdir": str(workdir), "task": str(workdir / "task.md"), "plan": None, "diff": None})
        log = subprocess.run(["git", "log", "--format=%s"], cwd=str(workdir), capture_output=True, text=True)
        self.assertEqual(log.stdout.strip(), "base")
        status = subprocess.run(["git", "status", "--porcelain"], cwd=str(workdir), capture_output=True, text=True)
        self.assertEqual(status.stdout, "")

    def test_prepare_review_case_applies_the_change_and_copies_plan_and_diff_out_of_the_case(self):
        reply = self.json("prepare", "tiny-review", str(self.root / "run"))
        workdir = Path(reply["workdir"])
        self.assertEqual((reply["write"], reply["task"]), (False, None))
        self.assertEqual((Path(reply["plan"]).parent, Path(reply["diff"]).parent), (workdir.parent, workdir.parent))
        self.assertEqual(Path(reply["plan"]).read_text(), "# Plan\n")
        self.assertEqual((workdir / "a.txt").read_text(), "b\n")  # applied, not committed

    def test_prepare_rejects_unknown_cases_and_an_existing_repository(self):
        for name in ("missing", "../cases/tiny", ".hidden"):
            with self.subTest(name=name):
                status, output, errors = self.cli("prepare", name, str(self.root / "run"), "--json")
                self.assertEqual((status, output), (2, ""))
                self.assertIn("unknown case", errors)
        self.json("prepare", "tiny", str(self.root / "run"))
        status, _, errors = self.cli("prepare", "tiny", str(self.root / "run"), "--json")
        self.assertEqual(status, 2)
        self.assertIn("already exists", errors)

    def test_grade_reports_criteria_and_passed(self):
        workdir = Path(self.json("prepare", "tiny", str(self.root / "run"))["workdir"])
        reply = self.json("grade", "tiny", str(workdir))
        self.assertEqual((reply["contract"], reply["case"], reply["passed"]), (1, "tiny", False))
        self.assertEqual([(item["name"], item["passed"]) for item in reply["criteria"]],
                         [("file", False), ("reply", False)])
        (workdir / "done.txt").write_text("x")
        final = self.root / "final.md"
        final.write_text("All finished.")
        reply = self.json("grade", "tiny", str(workdir), "--final", str(final))
        self.assertTrue(reply["passed"])

    def test_grade_runs_a_private_copy_of_the_graders(self):
        workdir = Path(self.json("prepare", "tiny", str(self.root / "run"))["workdir"])
        seen = []
        real = evaluator.grade

        def spy(case, *args):
            seen.append(case["dir"])
            return real(case, *args)
        with mock.patch.object(evaluator, "grade", side_effect=spy):
            self.json("grade", "tiny", str(workdir))
        self.assertNotEqual(seen[0], self.cases / "tiny")
        self.assertFalse(seen[0].exists())

    def test_grade_with_events_adds_the_clean_criterion(self):
        workdir = Path(self.json("prepare", "tiny", str(self.root / "run"))["workdir"])
        events = self.root / "events.jsonl"
        events.write_text('{"read": "%s"}\n' % (self.cases / "tiny" / "check.py"))
        with mock.patch.object(evaluator, "CASES", self.cases):
            reply = self.json("grade", "tiny", str(workdir), "--events", str(events))
        self.assertEqual(reply["criteria"][-1]["name"], "clean")
        self.assertFalse(reply["criteria"][-1]["passed"])
        events.write_text('{"read": "a.txt"}\n')
        reply = self.json("grade", "tiny", str(workdir), "--events", str(events))
        self.assertTrue(reply["criteria"][-1]["passed"])

    def test_grade_rejects_missing_paths(self):
        status, _, errors = self.cli("grade", "tiny", str(self.root / "missing"), "--json")
        self.assertEqual(status, 2)
        self.assertIn("WORKDIR is not a directory", errors)
        workdir = self.json("prepare", "tiny", str(self.root / "run"))["workdir"]
        status, _, errors = self.cli("grade", "tiny", workdir, "--final", str(self.root / "none.md"), "--json")
        self.assertEqual(status, 2)
        self.assertIn("--final is not a file", errors)

    def test_text_output(self):
        status, output, _ = self.cli("prepare", "tiny", str(self.root / "run"))
        self.assertEqual((status, output.strip()), (0, str(self.root / "run" / "repo")))
        status, output, _ = self.cli("grade", "tiny", output.strip())
        self.assertEqual(status, 0)
        self.assertEqual(output.splitlines(), ["FAIL file", "FAIL reply"])

    def test_old_eval_flags_still_reach_the_evaluator(self):
        with mock.patch.object(evaluator, "main", return_value=7) as old:
            self.assertEqual(qk.main(["eval", "--case", "tiny", "--runtime", "codex:"]), 7)
        old.assert_called_once_with(["--case", "tiny", "--runtime", "codex:"])


if __name__ == "__main__":
    unittest.main()
