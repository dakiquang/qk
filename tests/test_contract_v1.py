"""The CLI surface external tools may rely on: commands, JSON fields and exit codes.

Each fixture is a sample of contract output. Output may gain fields and commands; losing or renaming one that a
fixture shows breaks callers, so it fails here. Changing a fixture is a contract decision, not a test fix.
"""

import contextlib
import importlib
import io
import json
import os
from pathlib import Path
import re
import sys
import tempfile
import unittest
from unittest import mock

import fake_runtimes


SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))
qk = importlib.import_module("qk")
ledger = importlib.import_module("qk_ledger")

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "contract"
# One call per contract command, using the flags the contract documents; `--json` is appended.
SAMPLE_ARGV = {
    "contract": [],
    "show": ["--kind", "run", "--id", "abc", "--repo", "project", "--since", "7d"],
    "lesson list": [],
    "agent run": ["--spec", "codex:", "--cwd", ".", "--read-only", "--add-dir", "a", "--timeout", "60",
                  "--read-only-mcp", "tracker", "--no-result-contract", "--no-git-rules", "--lessons", "review",
                  "--repo", "project", "--events", "events.jsonl"],
    "agent family": ["codex:"],
    "log run": ["--producer", "other-tool 1.2.0", "--state-dir", "state"],
}


def fixture(name):
    return json.loads((FIXTURES / name).read_text())


class ContractTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        environment = mock.patch.dict(os.environ, {"QK_STATE_DIR": str(self.root / "ledger"),
                                                  "XDG_STATE_HOME": str(self.root / "state")})
        environment.start()
        self.addCleanup(environment.stop)

    def cli(self, *argv):
        output, errors = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(output), contextlib.redirect_stderr(errors):
            status = qk.main(list(argv))
        return status, output.getvalue(), errors.getvalue()

    def json(self, *argv):
        status, output, errors = self.cli(*argv)
        self.assertEqual((status, errors), (0, ""), argv)
        return json.loads(output)

    def assert_keeps_fields(self, actual, sample):
        self.assertEqual(sorted(set(sample) - set(actual)), [], "fields the contract promises are missing")
        for name, value in sample.items():
            self.assertIs(type(actual[name]), type(value), name)

    def test_contract_reports_version_and_commands(self):
        sample = fixture("contract.json")
        actual = self.json("contract", "--json")
        self.assert_keeps_fields(actual, sample)
        self.assertEqual(actual["contract"], sample["contract"])
        self.assertEqual(sorted(set(sample["commands"]) - set(actual["commands"])), [])
        self.assertRegex(actual["qk"], r"^\d+\.\d+\.\d+$")

    def test_contract_needs_no_ledger(self):
        with mock.patch.dict(os.environ, {"QK_STATE_DIR": str(self.root / "file")}):
            (self.root / "file").write_text("not a directory")
            self.assertEqual(self.json("contract", "--json")["contract"], 1)

    def test_contract_text_names_the_same_version(self):
        status, output, errors = self.cli("contract")
        self.assertEqual((status, errors), (0, ""))
        self.assertTrue(output.startswith("contract 1 qk %s " % qk.VERSION), output)

    def test_every_contract_command_parses_with_its_documented_flags(self):
        commands = self.json("contract", "--json")["commands"]
        self.assertEqual(sorted(set(commands) - set(SAMPLE_ARGV)), [], "add a sample call for each new command")
        for command in commands:
            with self.subTest(command=command):
                args = qk._parser().parse_args(command.split() + SAMPLE_ARGV[command] + ["--json"])
                self.assertTrue(args.json)

    def agent_run(self, **extra):
        self.addCleanup(fake_runtimes.collect_pipes)
        settings = {"PATH": fake_runtimes.path_with(self.root / "bin"), "HOME": str(self.root)}
        with mock.patch.dict(os.environ, dict(settings, **extra)), mock.patch("sys.stdin", io.StringIO("Task.")):
            status, output, _ = self.cli("agent", "run", "--spec", "claude:", "--cwd", str(self.root),
                                         "--read-only", "--json")
        return status, json.loads(output)

    def test_agent_run_keeps_fields_statuses_and_exit_codes(self):
        sample = fixture("agent-run.json")
        status, actual = self.agent_run()
        self.assert_keeps_fields(actual, sample)
        self.assert_keeps_fields(actual["result"], sample["result"])
        self.assert_keeps_fields(actual["usage"], sample["usage"])
        self.assertEqual((status, actual["status"], actual["contract"]), (0, "done", 1))
        for reported in ("blocked", "needs_input"):
            self.assertEqual(self.agent_run(FAKE_STATUS=reported)[0], 2, reported)
        self.assertEqual(self.agent_run(FAKE_STATUS=reported)[1]["status"], reported)

    def log_run(self, text):
        (self.root / "tool").mkdir(exist_ok=True)
        with mock.patch("sys.stdin", io.StringIO(text)):
            return self.cli("log", "run", "--producer", "other-tool 1.2.0", "--state-dir",
                            str(self.root / "tool"), "--json")

    def test_log_run_accepts_the_sample_state_and_keeps_fields(self):
        status, output, errors = self.log_run((FIXTURES / "log-run-input.json").read_text())
        self.assertEqual((status, errors), (0, ""))
        actual = json.loads(output)
        self.assert_keeps_fields(actual, fixture("log-run.json"))
        self.assertEqual((actual["contract"], actual["findings"]), (1, 1))
        run = self.json("show", "--kind", "run", "--json")[0]
        self.assertEqual((run["id"], run["data"]["producer"]), (actual["id"], "other-tool 1.2.0"))
        self.assertEqual(self.log_run("{}")[0], 2)

    def test_agent_family_keeps_fields(self):
        sample = fixture("agent-family.json")
        self.assertEqual(self.json("agent", "family", sample["spec"], "--json"), sample)

    def test_show_json_keeps_record_fields(self):
        sample = fixture("show-record.json")
        ledger.append(sample["kind"], sample["data"], repo=sample["repo"])
        records = self.json("show", "--json", "--kind", sample["kind"], "--repo", sample["repo"])
        self.assertEqual(len(records), 1)
        self.assert_keeps_fields(records[0], sample)
        self.assertEqual((records[0]["v"], records[0]["data"]), (sample["v"], sample["data"]))

    def test_lesson_list_json_is_a_list(self):
        self.assertEqual(self.json("lesson", "list", "--json"), [])


if __name__ == "__main__":
    unittest.main()
