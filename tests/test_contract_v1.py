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


SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))
qk = importlib.import_module("qk")
ledger = importlib.import_module("qk_ledger")

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "contract"


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

    def test_every_contract_command_accepts_json(self):
        for command in self.json("contract", "--json")["commands"]:
            with self.subTest(command=command):
                self.assertEqual(self.cli(*command.split(), "--json")[0], 0)

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
