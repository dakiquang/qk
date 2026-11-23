"""`qk log run`: a tool other than qk-run records a stopped run through the same projection."""

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
ledger = importlib.import_module("qk_ledger")

SAMPLE = Path(__file__).resolve().parent / "fixtures" / "contract" / "log-run-input.json"


class LogRunTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name).resolve()
        self.state_dir = self.root / "tool-state" / "job-1"
        self.state_dir.mkdir(parents=True)
        (self.state_dir / "state.json").write_text("{}")
        settings = mock.patch.dict(os.environ, {"QK_STATE_DIR": str(self.root / "ledger"),
                                                "XDG_STATE_HOME": str(self.root / "state")})
        settings.start()
        self.addCleanup(settings.stop)
        self.state = json.loads(SAMPLE.read_text())

    def cli(self, *argv, stdin=""):
        output, errors = io.StringIO(), io.StringIO()
        with mock.patch("sys.stdin", io.StringIO(stdin)), \
                contextlib.redirect_stdout(output), contextlib.redirect_stderr(errors):
            status = qk.main(list(argv))
        return status, output.getvalue(), errors.getvalue()

    def log(self, state=None, producer="other-tool 1.2.0", state_dir=None, raw=None):
        text = raw if raw is not None else json.dumps(self.state if state is None else state)
        return self.cli("log", "run", "--producer", producer, "--state-dir", str(state_dir or self.state_dir),
                        "--json", stdin=text)

    def store(self):
        path = ledger.store_path()
        return path.read_bytes() if path.exists() else b""

    def test_records_a_run_and_its_findings_like_the_runner(self):
        status, output, errors = self.log()
        self.assertEqual((status, errors), (0, ""))
        reply = json.loads(output)
        self.assertEqual((reply["contract"], reply["findings"]), (1, 1))
        run, finding = ledger.records()
        self.assertEqual((run["id"], run["kind"], run["source"], run["recorded_by"]),
                         (reply["id"], "run", "code", "code"))
        self.assertEqual((run["repo"], run["task_kind"]), ("project", "feature"))
        self.assertEqual(run["refs"], [str(self.state_dir / "state.json")])
        data = run["data"]
        self.assertEqual(data["producer"], "other-tool 1.2.0")
        self.assertEqual((data["run_id"], data["run_key"], data["status"]),
                         (self.state["id"], str(self.state_dir), "done"))
        self.assertEqual((data["impl"], data["review"]), (self.state["impl"], "claude:"))
        self.assertEqual(data["verify_results"], [{"index": 0, "exit": 0}, {"index": 1, "exit": 0}])
        self.assertEqual((data["remaining_count"], data["addressed_count"], data["serious_count"]), (1, 1, 0))
        self.assertEqual(data["changed_files"], ["src/export.py", "tests/test_export.py"])
        self.assertEqual(len(data["usage"]["implementing"]), 2)
        self.assertEqual((finding["kind"], finding["refs"], finding["data"]["file"]),
                         ("finding", [run["id"]], "src/export.py"))

    def test_matches_what_the_runner_records_for_the_same_state(self):
        self.log()
        recorded = ledger.records()[0]["data"]
        with mock.patch.dict(os.environ, {"QK_STATE_DIR": str(self.root / "ledger-2")}):
            direct = ledger.record_run(dict(self.state), self.state_dir)["data"]
        self.assertEqual({key: value for key, value in recorded.items() if key != "producer"}, direct)

    def test_same_input_twice_adds_nothing(self):
        first = json.loads(self.log()[1])
        before = self.store()
        second = json.loads(self.log()[1])
        self.assertEqual((second, self.store()), (first, before))

    def test_rejected_input_writes_nothing(self):
        def changed(**fields):
            return dict(self.state, **fields)
        missing_id = dict(self.state)
        del missing_id["id"]
        cases = {
            "working stage": {"state": changed(stage="implementing")},
            "missing id": {"state": missing_id},
            "relative repo": {"state": changed(repo="project")},
            "no repo": {"state": changed(repo=None)},
            "verify exit not an integer": {"state": changed(verify_results=[{"exit": "0"}])},
            "findings not a list": {"state": changed(findings={})},
            "usage not an object": {"state": changed(usage=[])},
            "not json": {"raw": "{"},
            "not an object": {"raw": "[]"},
            "empty producer": {"producer": ""},
            "multi-line producer": {"producer": "a\nb"},
            "missing state dir": {"state_dir": self.root / "missing"},
            "state dir without state.json": {"state_dir": self.root},
        }
        for name, arguments in cases.items():
            with self.subTest(name):
                status, output, errors = self.log(**arguments)
                self.assertEqual((status, output), (2, ""))
                self.assertTrue(errors.startswith("qk: "), errors)
                self.assertEqual(self.store(), b"")

    def test_state_dir_inside_a_repository_is_rejected(self):
        repository = self.root / "repo"
        (repository / "state").mkdir(parents=True)
        (repository / "state" / "state.json").write_text("{}")
        subprocess.run(["git", "init", "-q", str(repository)], check=True)
        status, _, errors = self.log(state_dir=repository / "state")
        self.assertEqual(status, 2)
        self.assertIn("outside Git repositories", errors)
        self.assertEqual(self.store(), b"")

    def test_blocked_run_keeps_only_the_stage_name(self):
        status, _, _ = self.log(dict(self.state, stage="blocked", blocked_at="verifying", pr_url="", commit=""))
        self.assertEqual(status, 0)
        data = ledger.records()[0]["data"]
        self.assertEqual((data["status"], data["blocked_at"]), ("blocked", "verifying"))
        status, output, _ = self.cli("brief")
        self.assertEqual(status, 0)
        self.assertIn("Next: resume or abort run %s with other-tool 1.2.0, which recorded it" % self.state["id"],
                      output)
        self.assertNotIn("qk run resume", output)

    def test_recorded_run_reads_back_through_show_stats_and_brief(self):
        reply = json.loads(self.log()[1])
        status, output, _ = self.cli("show", "--kind", "run", "--json")
        shown = json.loads(output)
        self.assertEqual((status, [record["id"] for record in shown]), (0, [reply["id"]]))
        self.assertEqual(shown[0]["data"]["impl"], self.state["impl"])
        status, output, errors = self.cli("stats", "--by", "runtime")
        self.assertEqual((status, errors), (0, ""))
        self.assertIn("codex:gpt-example, omp:anthropic/claude-example", output)
        status, output, errors = self.cli("brief")
        self.assertEqual((status, errors), (0, ""))
        self.assertIn(self.state["pr_url"], output)
        self.assertIn("Add CSV export to the report page", output)

    def test_text_output_is_the_record_id(self):
        status, output, _ = self.cli("log", "run", "--producer", "other-tool 1.2.0", "--state-dir",
                                     str(self.state_dir), stdin=json.dumps(self.state))
        self.assertEqual((status, output.strip()), (0, ledger.records()[0]["id"]))

    def test_log_claim_still_works(self):
        reply = json.loads(self.log()[1])
        status, output, errors = self.cli("log", "claim", "--about", reply["id"], "--text", "One conclusion.")
        self.assertEqual((status, errors), (0, ""))
        self.assertIn("source=model recorded_by=model", output)


if __name__ == "__main__":
    unittest.main()
