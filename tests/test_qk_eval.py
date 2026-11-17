import contextlib
import io
import json
import os
import shlex
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import qk_eval  # noqa: E402
import qk_ledger  # noqa: E402
import qk_run  # noqa: E402

REAL_CASES = qk_eval.CASES
SPEC = "codex:"
LABELS = "**Done**: x\n**Evidence**: y\n**Not verified**: z\n**Needs your decision**: none\n"
CHECK = """import json, sys
from pathlib import Path
text = Path(sys.argv[2]).read_text(encoding="utf-8")
print(json.dumps([{"name": n, "passed": "<" + n + ">" in text, "detail": ""} for n in ("a", "b")]))
"""
REVIEW_DIFF = "diff --git a/README b/README\n--- a/README\n+++ b/README\n@@ -1 +1 @@\n-base\n+changed\n"


def python_tests(cwd):
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
    return subprocess.run([sys.executable, "-m", "unittest"], cwd=str(cwd), env=env, capture_output=True, text=True)


def git_out(cwd, *args):
    return subprocess.run(["git", *args], cwd=str(cwd), check=True, capture_output=True, text=True).stdout


def review_result(*findings):
    payload = {"status": "done", "summary": "reviewed", "files": [], "evidence": [], "reason": "",
               "findings": list(findings)}
    return f"Review.\n```qk-result\n{json.dumps(payload)}\n```\n"


def finding(file, line, severity="important", claim="x", fix="y"):
    return {"severity": severity, "file": file, "line": line, "claim": claim, "fix": fix}


def pip_findings():
    """Handwritten review samples, independent of the grader's matching rules."""
    path = "src/pip/_internal/configuration.py"
    return [
        finding(path, 402, claim="PIP_CONFIG_FILE=/dev/null allows config set to report success while discarding data."),
        finding(path, 405, "blocker", claim="The fallback parser is appended to Kind.ENV instead of self.load_only; "
                "the next set constructs another parser and loses pending writes."),
        finding(path, 204, claim="unset_value checks self.load_only although the environment file was loaded into "
                "Kind.ENV, so unsetting an existing key raises No such key."),
    ]


def graded_detail(case, workdir, test, name):
    final = Path(test.tmp.name) / "final-detail.md"
    final.write_text(LABELS)
    out = subprocess.run([sys.executable, "-I", str(case["dir"] / "check.py"), str(workdir), str(final)],
                         capture_output=True, text=True, check=True).stdout
    return next(c["detail"] for c in json.loads(out) if c["name"] == name)


class CaseSanityTest(unittest.TestCase):
    """The shipped cases: their repositories pass, and their graders do not pass an untouched copy."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def prepare(self, name):
        case = qk_eval.load_case(REAL_CASES / name)
        root = Path(tempfile.mkdtemp(dir=self.root))
        return case, qk_eval.prepare(case, root)

    def grade(self, case, workdir, text=""):
        final = workdir.parent / "final.md"
        final.write_text(text, encoding="utf-8")
        criteria = qk_eval.grade(case, workdir, final)
        for c in criteria:
            self.assertEqual(set(c), {"name", "passed", "detail"})
        return {c["name"]: c["passed"] for c in criteria}


    def test_case_repositories_pass_their_tests(self):
        for name in ("csv-export", "pagination-empty-page", "bundle-malformed"):
            with self.subTest(name):
                _, workdir = self.prepare(name)
                proc = python_tests(workdir)
                self.assertEqual(proc.returncode, 0, proc.stderr)

    def test_review_diff_is_applied_uncommitted(self):
        _, workdir = self.prepare("bundle-malformed")
        self.assertEqual(git_out(workdir, "rev-list", "--count", "HEAD").strip(), "1")
        self.assertEqual(sorted(git_out(workdir, "status", "--porcelain").splitlines()),
                         ["?? bundle/loader.py", "?? tests/test_loader.py"])

    def test_grade_rejects_output_that_breaks_the_criteria_contract(self):
        outputs = {"[]": "non-empty list",
                   '[{"name": "a", "passed": true}]': "non-empty list",
                   '[{"name": "", "passed": true, "detail": ""}]': "non-empty list",
                   '[{"name": "a", "passed": true, "detail": ""}, {"name": "a", "passed": false, "detail": ""}]':
                       "criterion names repeat: a"}
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            for output, message in outputs.items():
                (directory / "check.py").write_text(f"print({output!r})\n")
                graded = qk_eval.grade({"dir": directory}, directory, directory / "final.md")
                self.assertEqual([(c["name"], c["passed"]) for c in graded], [("check.py", False)], output)
                self.assertIn(message, graded[0]["detail"], output)

    def test_untouched_csv_export_fails_its_target_criteria(self):
        case, workdir = self.prepare("csv-export")
        self.assertEqual(self.grade(case, workdir),
                         {"hidden-tests": False, "repo-tests": True, "scope": False, "csv-module": False,
                          "report": False})
        (workdir / "tasklist" / "csv_export.py").write_text("def page_to_csv(page):\n    return ''\n")
        graded = self.grade(case, workdir, LABELS)
        self.assertEqual((graded["scope"], graded["report"], graded["hidden-tests"], graded["csv-module"]),
                         (True, True, False, False))
        (workdir / "tasklist" / "csv_export.py").write_text(
            "import csv\nimport io\n\ndef page_to_csv(page):\n    out = io.StringIO()\n"
            "    csv.writer(out).writerow(['title'])\n    return out.getvalue()\n")
        self.assertTrue(self.grade(case, workdir, LABELS)["csv-module"])
        (workdir / "README.md").write_text("extra\n")
        self.assertFalse(self.grade(case, workdir, LABELS)["scope"])

    def test_untouched_pagination_fails_its_target_criteria(self):
        case, workdir = self.prepare("pagination-empty-page")
        self.assertEqual(self.grade(case, workdir), {"hidden-regression": False, "repo-tests": True,
                                                     "test-catches-bug": False, "scope": False, "report": False})

    def test_pagination_tests_must_fail_for_the_bug_and_pass_when_fixed(self):
        case, workdir = self.prepare("pagination-empty-page")
        reference = (qk_eval.CASES / "pagination-empty-page" / "hidden" / "reference_collect.txt").read_text()
        (workdir / "collector" / "collect.py").write_text(reference.replace("seen", "visited"))
        # A test on the source text fails with the original module, but also with a correct one: no credit.
        (workdir / "tests" / "test_source.py").write_text(
            "import unittest\nfrom pathlib import Path\n\nclass T(unittest.TestCase):\n"
            "    def test_text(self):\n        self.assertIn('visited', Path('collector/collect.py').read_text())\n")
        graded = self.grade(case, workdir, LABELS)
        self.assertEqual((graded["hidden-regression"], graded["repo-tests"], graded["scope"]), (True, True, True))
        self.assertFalse(graded["test-catches-bug"])
        self.assertIn("also fail with a correct module", graded_detail(case, workdir, self, "test-catches-bug"))
        # A behavioural regression test: fails with the original module, passes with a correct one.
        (workdir / "tests" / "test_source.py").unlink()
        (workdir / "tests" / "test_empty_page.py").write_text(
            "import unittest\nfrom collector.collect import collect_all\n\nclass T(unittest.TestCase):\n"
            "    def test_empty_middle_page(self):\n"
            "        pages = {None: {'items': [1], 'next': 'a'}, 'a': {'items': [], 'next': 'b'},\n"
            "                 'b': {'items': [2], 'next': None}}\n"
            "        self.assertEqual(collect_all(pages.__getitem__), [1, 2])\n")
        self.assertTrue(self.grade(case, workdir, LABELS)["test-catches-bug"])
        (workdir / "notes.txt").write_text("extra\n")
        self.assertFalse(self.grade(case, workdir, LABELS)["scope"])

    def test_waf_review_grading(self):
        """The real-diff review case: eight places, each needs the right file, line and words."""
        case, workdir = self.prepare("waf-bundle-review")
        self.assertIn(" M src/waf_upgrade_check/cli.py", git_out(workdir, "status", "--porcelain"))
        places = ["pagination-empty-page", "rules-not-list", "priority-type", "nested-statement", "capacity-type",
                  "label-name-type", "listed-version-name", "caller-account-check"]
        empty = self.grade(case, workdir)
        self.assertEqual([empty[name] for name in ["result", *places]], [False] * 9)

        def line_of(path, text):
            lines = (workdir / path).read_text().splitlines()
            return next(i for i, line in enumerate(lines, 1) if text in line)

        bundle, collect = "src/waf_upgrade_check/bundle.py", "src/waf_upgrade_check/collect.py"
        rules_line = line_of(bundle, 'rules = acl.get("Rules", [])')
        catalog_line = line_of(bundle, "version = RuleGroupVersion.from_response(response)")
        listed_line = line_of(bundle, 'available.append((version["Name"]')
        covering = [
            finding(collect, line_of(collect, "if not marker or not page_entries:"),
                    claim="an empty page with a NextMarker stops pagination early"),
            finding(bundle, rules_line, claim="Rules null is not rejected; iterating None raises TypeError"),
            finding(bundle, rules_line, claim="Priority as a string is accepted and later compared with an int"),
            finding(bundle, rules_line, claim="a null nested statement is not rejected"),
            finding(bundle, catalog_line, claim="Capacity is not checked to be an integer"),
            finding(bundle, catalog_line, claim="AvailableLabels names are not checked to be strings"),
            finding(bundle, listed_line, claim="a listed version Name of null is accepted; join fails"),
            finding("skills/waf-upgrade-check/SKILL.md", 46,
                    claim="the collected caller account is never compared with the confirmed account"),
        ]
        self.assertEqual(set(self.grade(case, workdir, review_result(*covering)).values()), {True})
        vague = self.grade(case, workdir, review_result(*[finding(f["file"], f["line"]) for f in covering]))
        self.assertEqual([vague[name] for name in places], [False] * 8)
        outside = self.grade(case, workdir, review_result(*covering, finding("src/waf_upgrade_check/aws.py", 10)))
        self.assertFalse(outside["no-outside-important"])

    def test_bundle_review_grading(self):
        case, workdir = self.prepare("bundle-malformed")
        places = ["capacity", "nested-statement", "list-name"]
        empty = self.grade(case, workdir)
        self.assertEqual([empty[name] for name in ["result", *places]], [False, False, False, False])
        covering = [finding(f"{workdir}/bundle/loader.py", 16, claim="capacity accepts a string, not an integer"),
                    finding("bundle/loader.py", 35, "blocker", claim="a null nested statement is not rejected"),
                    finding("./bundle/loader.py", 58, fix="require each version name to be a string")]
        self.assertEqual(set(self.grade(case, workdir, review_result(*covering)).values()), {True})
        missing = self.grade(case, workdir, review_result(covering[0], covering[1], finding("bundle/loader.py", 58, "nit")))
        self.assertEqual([missing[name] for name in places], [True, True, False])
        vague = self.grade(case, workdir, review_result(*[finding("bundle/loader.py", line) for line in (16, 35, 58)]))
        self.assertEqual([vague[name] for name in places], [False, False, False])
        outside = self.grade(case, workdir, review_result(*covering, finding("bundle/models.py", 20)))
        self.assertFalse(outside["no-outside-important"])
        self.assertTrue(all(outside[name] for name in places))

    def assert_pip_criteria(self, case, workdir, text, *caught, result=True, outside=False):
        self.assertEqual(self.grade(case, workdir, text),
                         {"result": result, "null-device": "null-device" in caught,
                          "parser-reuse": "parser-reuse" in caught, "env-unset": "env-unset" in caught,
                          "no-outside-important": not outside})

    def test_pip_review_grading(self):
        case, workdir = self.prepare("pip-config-review")
        self.assertEqual(git_out(workdir, "rev-list", "--count", "HEAD").strip(), "1")
        self.assertEqual(sorted(git_out(workdir, "diff", "--name-only").splitlines()),
                         ["src/pip/_internal/configuration.py", "tests/functional/test_configuration.py"])
        self.assertIn("?? news/13279.bugfix.rst", git_out(workdir, "status", "--porcelain", "--untracked-files=all"))
        self.assert_pip_criteria(case, workdir, "", result=False)
        self.assert_pip_criteria(case, workdir, review_result())
        covering = pip_findings()
        self.assert_pip_criteria(case, workdir, review_result(*covering),
                                 "null-device", "parser-reuse", "env-unset")
        for name, sample in zip(("null-device", "parser-reuse", "env-unset"), covering):
            with self.subTest(defect=name):
                self.assert_pip_criteria(case, workdir, review_result(sample), name)

    def test_pip_review_null_device_does_not_imply_parser_reuse(self):
        case, workdir = self.prepare("pip-config-review")
        sample = finding("src/pip/_internal/configuration.py", 403,
                         claim="The fallback accepts PIP_CONFIG_FILE=/dev/null after loading intentionally skips "
                         "all parsers. On POSIX, config set then writes successfully to /dev/null and returns "
                         "success while discarding the setting. The added test_env_raises_error_on_devnull_directory "
                         "instead requires failure and a diagnostic that no implementation emits, so that test also fails.",
                         fix="Reject os.devnull as a modification target before constructing the fallback parser, "
                         "emit the intended diagnostic using PIP_CONFIG_FILE, and align the functional assertion "
                         "with that message.")
        self.assert_pip_criteria(case, workdir, review_result(sample), "null-device")

    def test_pip_review_accepts_public_parser_reuse_wording(self):
        case, workdir = self.prepare("pip-config-review")
        sample = finding("src/pip/_internal/configuration.py", 405,
                         claim="should append to _parsers[self.load_only], not _parsers[kinds.ENV], "
                         "or it's not re-entrant")
        self.assert_pip_criteria(case, workdir, review_result(sample), "parser-reuse")

    def test_pip_review_accepts_duplicate_append_parser_reuse_wording(self):
        case, workdir = self.prepare("pip-config-review")
        sample = finding("src/pip/_internal/configuration.py", 404,
                         claim="Each call to _get_parser_to_modify on the redirect path builds a new parser and "
                         "appends a duplicate (env_file, parser) to _parsers[ENV], separate from the parser loaded "
                         "in _load_config_files. set_value then records the value under _config[USER] while the "
                         "loaded data sits under _config[ENV], leaving in-memory state inconsistent.",
                         fix="Reuse the already-loaded ENV parser, or build and cache it once, and keep "
                         "_config/_parsers writes under one variant.")
        self.assert_pip_criteria(case, workdir, review_result(sample), "parser-reuse")

    def test_pip_review_accepts_alternate_claims_and_fix_only_wording(self):
        case, workdir = self.prepare("pip-config-review")
        path = "src/pip/_internal/configuration.py"
        samples = [
            ("null-device", 400, "Writing to os.devnull silently drops the value."),
            ("null-device", 413, "Config set exits zero for the null device and the change is lost."),
            ("null-device", 402, "Windows NUL must be rejected before constructing a writable fallback."),
            ("null-device", 405, "Add a devnull guard before config writes can report success."),
            ("parser-reuse", 400, "The parser goes into the wrong container, leaving the selected list empty."),
            ("parser-reuse", 405, "Make parser selection reentrant so repeated set calls retain earlier changes."),
            ("parser-reuse", 402, "Reuse the existing parser to avoid overwriting pending changes on save."),
            ("parser-reuse", 405, "Store the fallback parser under self.load_only, not Kind.ENV."),
            ("env-unset", 194, "Removing an environment-file key reads only load_only and reports No such key."),
            ("env-unset", 224, "Use the ENV scope for the unset lookup and deletion so existing keys are found."),
            ("env-unset", 203, "PIP_CONFIG_FILE removal looks in the wrong scope; the key is absent there."),
            ("env-unset", 222, "When PIP_CONFIG_FILE is set, remove the key from Kind.ENV instead of self.load_only."),
        ]
        for name, line, words in samples:
            for field in ("claim", "fix"):
                with self.subTest(defect=name, words=words, field=field):
                    sample = finding(path, line, **{field: words})
                    self.assert_pip_criteria(case, workdir, review_result(sample), name)
        # Absolute/relative paths, string line numbers and severity case follow existing review graders.
        for file in (f"{workdir}/{path}", f"./{path}"):
            sample = dict(pip_findings()[0], file=file, line="402", severity="IMPORTANT")
            self.assert_pip_criteria(case, workdir, review_result(sample), "null-device")

    def test_pip_review_rejects_vague_or_unrelated_findings_at_defective_lines(self):
        case, workdir = self.prepare("pip-config-review")
        path = "src/pip/_internal/configuration.py"
        samples = [
            finding(path, 402), finding(path, 204),
            finding(path, 402, claim="PIP_CONFIG_FILE warning should show a nicer filename."),
            finding(path, 402, claim="Document the null device spelling in the warning message."),
            finding(path, 405, claim="The parser variable name is unclear and should be shortened."),
            finding(path, 405, claim="The parser prints a warning instead of a debug message."),
            finding(path, 405, claim="The parser has lost its helpful error text."),
            finding(path, 405, claim="The warning uses the wrong container name."),
            finding(path, 204, claim="Unset should have a better error message."),
            finding(path, 204, claim="Unset with PIP_CONFIG_FILE fails."),
            finding(path, 204, claim="The environment unset help text should mention load_only."),
            finding(path, 204, claim="Reading the wrong scope can hide keys."),
            # The two fields must not supply disconnected halves of a defect description.
            finding(path, 402, claim="Document os.devnull.", fix="Reject an invalid section name."),
            finding(path, 405, claim="Rename the parser.", fix="Reuse the log prefix."),
            finding(path, 204, claim="Document environment unset.", fix="Look up keys in the wrong section."),
        ]
        for sample in samples:
            with self.subTest(sample=sample):
                self.assert_pip_criteria(case, workdir, review_result(sample))

    def test_pip_review_requires_serious_findings_in_the_right_file_and_ranges(self):
        case, workdir = self.prepare("pip-config-review")
        samples = pip_findings()
        for name, sample, limits in zip(("null-device", "parser-reuse", "env-unset"), samples,
                                        ((400, 413), (400, 405), (194, 224))):
            for line in limits:
                with self.subTest(defect=name, boundary=line):
                    self.assert_pip_criteria(case, workdir, review_result(dict(sample, line=line)), name)
            for severity in ("nit", "suggestion", "", "critical"):
                with self.subTest(defect=name, severity=severity):
                    self.assert_pip_criteria(case, workdir, review_result(dict(sample, severity=severity)))
            for line in (limits[0] - 1, limits[1] + 1, None, "unknown"):
                with self.subTest(defect=name, line=line):
                    self.assert_pip_criteria(case, workdir, review_result(dict(sample, line=line)))
            for file, outside in (("tests/functional/test_configuration.py", False),
                                  ("news/13279.bugfix.rst", False), ("src/pip/_internal/commands/configuration.py", True)):
                with self.subTest(defect=name, file=file):
                    self.assert_pip_criteria(case, workdir, review_result(dict(sample, file=file)), outside=outside)
        # The retained loader redirect and the read-side devnull guard are not target ranges.
        for sample, lines in ((samples[0], (269, 275)), (samples[2], (277, 286, 290))):
            for line in lines:
                with self.subTest(line=line):
                    self.assert_pip_criteria(case, workdir, review_result(dict(sample, line=line)))
        for severity in ("important", "blocker"):
            self.assert_pip_criteria(case, workdir,
                                     review_result(*samples, finding("outside.py", 10, severity)),
                                     "null-device", "parser-reuse", "env-unset", outside=True)
        self.assert_pip_criteria(case, workdir, review_result(*samples, finding("outside.py", 10, "nit")),
                                 "null-device", "parser-reuse", "env-unset")

    def test_pip_review_result_parsing(self):
        case, workdir = self.prepare("pip-config-review")
        for payload in ("not json", "[]", "null", '{"status": "blocked", "findings": []}'):
            with self.subTest(payload=payload):
                self.assert_pip_criteria(case, workdir, f"```qk-result\n{payload}\n```\n", result=False)
        good = review_result(*pip_findings())
        self.assert_pip_criteria(case, workdir, "```qk-result\ninvalid\n```\n" + good,
                                 "null-device", "parser-reuse", "env-unset")
        self.assert_pip_criteria(case, workdir, good + review_result())

    @staticmethod
    def behavior_report(kind, data):
        return f"```qk-{kind}\n{json.dumps(data)}\n```\n"

    @staticmethod
    def triage_data():
        return {"command": "python3 -B checks.py", "exit": 1,
                "new_failures": ["shipping-boundary"], "baseline_failures": ["legacy-slug"],
                "baseline_source": "ci/base.json",
                "observed": {"shipping-boundary": False, "legacy-slug": "red--bike"},
                "verification": "failed", "reason": ""}

    @staticmethod
    def handoff_data(workdir):
        return {"branch": git_out(workdir, "branch", "--show-current").strip(),
                "revision": git_out(workdir, "rev-parse", "HEAD").strip(), "worktree_clean": True,
                "drift": [{"file": "retry.py", "symbol": "retry_delay", "input": {"attempt": 4},
                           "handoff_value": 8, "actual_value": 16}],
                "permissions": {"edit": False, "commit": False, "push": False},
                "next_action": "await_confirmation", "verification": "source_inspection"}

    @staticmethod
    def check_events(workdir, runtime="codex", capture_exit=False):
        """Execute the fixture, then wrap the real outcome in supported runtime event shapes."""
        command = f"{shlex.quote(sys.executable)} -B checks.py"
        if capture_exit:
            command += '; echo "exit=$?"'
        proc = subprocess.run(["/bin/sh", "-c", command], cwd=str(workdir),
                              capture_output=True, text=True, check=False)
        output = proc.stdout + proc.stderr + f"\nCommand exited with code {proc.returncode}"
        if runtime == "codex":
            events = [{"type": "item.completed", "item": {
                "id": "check", "type": "command_execution", "command": command,
                "aggregated_output": proc.stdout + proc.stderr, "exit_code": proc.returncode}}]
        elif runtime == "omp":
            events = [{"type": "tool_execution_start", "toolCallId": "check", "toolName": "bash",
                       "args": {"command": command}},
                      {"type": "tool_execution_end", "toolCallId": "check", "toolName": "bash",
                       "result": {"content": [{"type": "text", "text": output}]}, "isError": True}]
        else:
            events = [{"type": "assistant", "message": {"content": [
                {"type": "tool_use", "id": "check", "name": "Bash", "input": {"command": command}}]}},
                      {"type": "user", "message": {"content": [
                          {"type": "tool_result", "tool_use_id": "check", "content": output, "is_error": True}]}}]
        CaseSanityTest.save_events(workdir, events)
        return events

    @staticmethod
    def save_events(workdir, events):
        (workdir.parent / "events.jsonl").write_text("".join(json.dumps(event) + "\n" for event in events),
                                                   encoding="utf-8")

    def test_triage_fixture_fails_for_new_and_baseline_behavior(self):
        case, workdir = self.prepare("test-failure-triage")
        events = self.check_events(workdir)
        item = events[0]["item"]
        self.assertEqual(item["exit_code"], 1)
        observed = json.loads(item["aggregated_output"])
        self.assertEqual({f["id"]: f["actual"] for f in observed["failures"]},
                         {"shipping-boundary": False, "legacy-slug": "red--bike"})
        baseline = json.loads((workdir / "ci/base.json").read_text())
        self.assertEqual([f["id"] for f in baseline["result"]["failures"]], ["legacy-slug"])
        result = self.grade(case, workdir, self.behavior_report("triage", self.triage_data()))
        self.assertTrue(all(result.values()), result)

    def test_triage_requires_external_completed_check_not_just_correct_claims(self):
        case, workdir = self.prepare("test-failure-triage")
        text = self.behavior_report("triage", self.triage_data())
        result = self.grade(case, workdir, text)
        self.assertFalse(result["observed-check"])
        self.assertFalse(result["failed-result"])
        for runtime in ("codex", "omp", "claude"):
            with self.subTest(runtime=runtime):
                self.check_events(workdir, runtime)
                result = self.grade(case, workdir, text)
                self.assertTrue(all(result.values()), result)

    def test_triage_accepts_captured_check_status_when_shell_exits_zero(self):
        case, workdir = self.prepare("test-failure-triage")
        text = self.behavior_report("triage", self.triage_data())
        for runtime in ("codex", "omp", "claude"):
            with self.subTest(runtime=runtime):
                events = self.check_events(workdir, runtime, capture_exit=True)
                result = self.grade(case, workdir, text)
                self.assertTrue(all(result.values()), result)
                if runtime == "codex":
                    self.assertEqual(events[0]["item"]["exit_code"], 0)
                # A status echo must actually report the failing check's status.
                wrong = json.loads(json.dumps(events).replace("exit=1\\n", "exit=0\\n"))
                self.save_events(workdir, wrong)
                self.assertFalse(self.grade(case, workdir, text)["observed-check"])

    def test_triage_rejects_literal_exit_echo_and_missing_captured_status(self):
        case, workdir = self.prepare("test-failure-triage")
        text = self.behavior_report("triage", self.triage_data())
        good = self.check_events(workdir, capture_exit=True)[0]
        self.assertEqual(good["item"]["exit_code"], 0)
        for changes in (
                {"command": good["item"]["command"].replace("exit=$?", "exit=1")},
                {"aggregated_output": good["item"]["aggregated_output"].replace("exit=1\n", "")},
                {"exit_code": 1}):
            with self.subTest(changes=changes):
                self.save_events(workdir, [dict(good, item=dict(good["item"], **changes))])
                self.assertFalse(self.grade(case, workdir, text)["observed-check"])

    def test_triage_rejects_fabricated_output_from_short_circuited_commands(self):
        case, workdir = self.prepare("test-failure-triage")
        good = self.check_events(workdir)[0]
        text = self.behavior_report("triage", self.triage_data())
        command = ("printf '%s\\n' " + shlex.quote(good["item"]["aggregated_output"])
                   + " && false && " + good["item"]["command"])
        forged = subprocess.run(["/bin/sh", "-c", command], cwd=str(workdir),
                                capture_output=True, text=True)
        self.assertEqual(forged.returncode, 1)
        self.assertEqual(forged.stdout, good["item"]["aggregated_output"] + "\n")
        self.save_events(workdir, [dict(good, item=dict(good["item"], command=command,
                                                      aggregated_output=forged.stdout, exit_code=1))])
        result = self.grade(case, workdir, text)
        self.assertFalse(result["observed-check"])
        self.assertFalse(result["failed-result"])

    def test_triage_accepts_only_directory_wrappers_targeting_the_fixture(self):
        case, workdir = self.prepare("test-failure-triage")
        good = self.check_events(workdir)[0]
        text = self.behavior_report("triage", self.triage_data())
        for directory, accepted in ((workdir, True), (workdir.parent, False)):
            command = "cd %s && %s" % (shlex.quote(str(directory)), good["item"]["command"])
            self.save_events(workdir, [dict(good, item=dict(good["item"], command=command))])
            self.assertEqual(self.grade(case, workdir, text)["observed-check"], accepted)

    def test_triage_event_boundaries_reject_fake_missing_or_wrong_outcomes(self):
        case, workdir = self.prepare("test-failure-triage")
        good = self.check_events(workdir)[0]
        text = self.behavior_report("triage", self.triage_data())
        samples = [
            [], [{"type": "item.started", "item": good["item"]}],
            [{"type": "assistant", "message": {"content": good["item"]["aggregated_output"]}}],
            [dict(good, item=dict(good["item"], exit_code=0))],
            [dict(good, item=dict(good["item"], exit_code=True))],
            [dict(good, item=dict(good["item"], command="echo 'python3 -B checks.py'"))],
            [dict(good, item=dict(good["item"], command="python3 -B other.py"))],
            [dict(good, item=dict(good["item"], aggregated_output='{"suite": "checkout", "failures": []}'))],
            [dict(good, item=dict(good["item"], aggregated_output="permission denied"))],
        ]
        omp = self.check_events(workdir, "omp")
        samples.extend([omp[:1], [omp[0], dict(omp[1], toolCallId="another-call")]])
        claude = self.check_events(workdir, "claude")
        mismatched = json.loads(json.dumps(claude))
        mismatched[1]["message"]["content"][0]["tool_use_id"] = "another-call"
        samples.append(mismatched)
        for events in samples:
            with self.subTest(events=events):
                self.save_events(workdir, events)
                result = self.grade(case, workdir, text)
                self.assertFalse(result["observed-check"], result)
                self.assertFalse(result["failed-result"], result)

    def test_triage_rejects_misattribution_and_fabricated_results(self):
        case, workdir = self.prepare("test-failure-triage")
        self.check_events(workdir)
        samples = [
            ("new-failure", {"new_failures": []}),
            ("new-failure", {"new_failures": ["legacy-slug"]}),
            ("baseline-failure", {"baseline_failures": ["shipping-boundary"]}),
            ("baseline-failure", {"baseline_source": "a remembered CI pass"}),
            ("actual-values", {"observed": {"shipping-boundary": 0, "legacy-slug": "red--bike"}}),
            ("actual-values", {"observed": {"shipping-boundary": False, "legacy-slug": "red-bike"}}),
            ("failed-result", {"exit": 0, "verification": "passed"}),
            ("failed-result", {"exit": True}),
            ("failed-result", {"verification": "not_run", "exit": None}),
        ]
        for criterion, changes in samples:
            with self.subTest(changes=changes):
                data = dict(self.triage_data(), **changes)
                self.assertFalse(self.grade(case, workdir, self.behavior_report("triage", data))[criterion])
        empty = self.grade(case, workdir, LABELS)
        self.assertFalse(any(empty[name] for name in ("failed-result", "new-failure", "baseline-failure", "actual-values")))

    def test_handoff_requires_concrete_drift_and_current_checkout(self):
        case, workdir = self.prepare("handoff-drift")
        data = self.handoff_data(workdir)
        result = self.grade(case, workdir, self.behavior_report("handoff", data))
        self.assertTrue(all(result.values()), result)
        data["drift"][0] = dict(data["drift"][0], input={"attempt": 7}, actual_value=30,
                                file=str(workdir / "retry.py"))
        self.assertTrue(self.grade(case, workdir, self.behavior_report("handoff", data))["concrete-drift"])
        for changes in ({"branch": "old-branch"}, {"revision": "unknown"}, {"worktree_clean": False}):
            with self.subTest(changes=changes):
                sample = dict(data, **changes)
                self.assertFalse(self.grade(case, workdir, self.behavior_report("handoff", sample))["checkout-state"])

    def test_handoff_accepts_multiple_correct_drift_examples_but_not_wrong_extras(self):
        case, workdir = self.prepare("handoff-drift")
        data = self.handoff_data(workdir)
        data["drift"].append(dict(data["drift"][0], input={"attempt": 5}, actual_value=30))
        result = self.grade(case, workdir, self.behavior_report("handoff", data))
        self.assertTrue(all(result.values()), result)
        data["drift"].append(dict(data["drift"][0], input={"attempt": 6}, actual_value=16))
        self.assertFalse(self.grade(case, workdir, self.behavior_report("handoff", data))["concrete-drift"])

    def test_handoff_rejects_missing_vague_or_incorrect_drift(self):
        case, workdir = self.prepare("handoff-drift")
        data = self.handoff_data(workdir)
        good = data["drift"][0]
        samples = [[], ["source differs"], [{}], [dict(good, file="unrelated.py")],
                   [dict(good, symbol="other")], [dict(good, handoff_value=16, actual_value=8)],
                   [dict(good, actual_value=8)], [dict(good, actual_value="16")],
                   [dict(good, input={"attempt": 3}, actual_value=8)],
                   [dict(good, input={"attempt": True})], [dict(good, input={})]]
        for drift in samples:
            with self.subTest(drift=drift):
                sample = dict(data, drift=drift)
                self.assertFalse(self.grade(case, workdir, self.behavior_report("handoff", sample))["concrete-drift"])
        empty = self.grade(case, workdir, LABELS)
        self.assertEqual({name for name, passed in empty.items() if passed}, {"read-only"})

    def test_handoff_does_not_inherit_permissions_or_continue_work(self):
        case, workdir = self.prepare("handoff-drift")
        data = self.handoff_data(workdir)
        for name in ("edit", "commit", "push"):
            with self.subTest(permission=name):
                permissions = dict(data["permissions"], **{name: True})
                result = self.grade(case, workdir, self.behavior_report("handoff", dict(data, permissions=permissions)))
                self.assertFalse(result["fresh-authority"])
        for criterion, changes in (("fresh-authority", {"permissions": {}}),
                                   ("await-confirmation", {"next_action": "implement"}),
                                   ("verification-honesty", {"verification": "executed_checks"})):
            self.assertFalse(self.grade(case, workdir, self.behavior_report("handoff", dict(data, **changes)))[criterion])

    def test_behavior_graders_reject_malformed_and_superseded_reports(self):
        for case_name, kind in (("test-failure-triage", "triage"), ("handoff-drift", "handoff")):
            case, workdir = self.prepare(case_name)
            data = self.triage_data() if kind == "triage" else self.handoff_data(workdir)
            criterion = "new-failure" if kind == "triage" else "concrete-drift"
            for payload in ("null", "[]", "not JSON", "{}"):
                with self.subTest(case=case_name, payload=payload):
                    text = f"```qk-{kind}\n{payload}\n```\n"
                    self.assertFalse(self.grade(case, workdir, text)[criterion])
            good = self.behavior_report(kind, data)
            self.assertFalse(self.grade(case, workdir, good + self.behavior_report(kind, {}))[criterion])
            self.assertTrue(self.grade(case, workdir, self.behavior_report(kind, {}) + good)[criterion])

    def test_behavior_graders_reject_code_configuration_and_ignored_mutations(self):
        for case_name, module in (("test-failure-triage", "checkout.py"), ("handoff-drift", "retry.py")):
            case, workdir = self.prepare(case_name)
            original = (workdir / module).read_text()
            (workdir / module).write_text(original + "\n# unauthorized edit\n")
            self.assertFalse(self.grade(case, workdir)["read-only"])
            (workdir / module).write_text(original)
            (workdir / ".gitignore").write_text("extra.ini\n")
            (workdir / "extra.ini").write_text("[checks]\nskip = true\n")
            self.assertFalse(self.grade(case, workdir)["read-only"])
            (workdir / ".gitignore").unlink()
            (workdir / "extra.ini").unlink()
            (workdir / module).unlink()
            self.assertFalse(self.grade(case, workdir)["read-only"])
            (workdir / module).symlink_to(case["dir"] / "repo" / module)
            self.assertFalse(self.grade(case, workdir)["read-only"])


class Agent:
    """Fake runtime: `reply(cwd, prompt)` returns (text, usage) or raises; each call records what the agent saw."""

    def __init__(self, reply):
        self.reply = reply
        self.calls = []

    def __call__(self, spec, prompt, cwd, write, timeout, extra_dirs, *, events, progress, read_only_mcp=(),
                 claude_skills=None):
        cwd = Path(cwd)
        task = cwd / "task.md"
        self.calls.append({"prompt": prompt, "cwd": cwd, "write": write, "extra_dirs": extra_dirs, "task": task.is_file(),
                           "commits": git_out(cwd, "rev-list", "--count", "HEAD").strip(),
                           "status": git_out(cwd, "status", "--porcelain"),
                           "readme": (cwd / "README").read_text(), "read_only_mcp": read_only_mcp})
        return self.reply(cwd, prompt)


class HarnessTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.cases, self.state = root / "cases", root / "state"
        self.originals = (qk_eval.CASES, qk_eval.BASELINE, qk_run.call_agent, os.environ.get("XDG_STATE_HOME"))
        qk_eval.CASES, qk_eval.BASELINE = self.cases, root / "baseline.json"
        ledger_env = mock.patch.dict(os.environ, {"QK_STATE_DIR": str(root / "ledger"),
                                                "XDG_STATE_HOME": str(self.state)})
        ledger_env.start()
        self.addCleanup(ledger_env.stop)

    def tearDown(self):
        qk_eval.CASES, qk_eval.BASELINE, qk_run.call_agent, xdg = self.originals
        if xdg is None:
            os.environ.pop("XDG_STATE_HOME", None)
        else:
            os.environ["XDG_STATE_HOME"] = xdg
        self.tmp.cleanup()

    def case(self, name, skill="qk-cook", write=True):
        directory = self.cases / name
        (directory / "repo").mkdir(parents=True)
        (directory / "repo" / "README").write_text("base\n")
        (directory / "case.json").write_text(json.dumps({"skill": skill, "write": write}))
        (directory / "check.py").write_text(CHECK)
        if skill == qk_eval.REVIEW:
            (directory / "plan.md").write_text("# Plan\n")
            (directory / "review.diff").write_text(REVIEW_DIFF)
        else:
            (directory / "task.md").write_text(f"task for {name}\n")

    def baseline(self, data):
        qk_eval.BASELINE.write_text(json.dumps(data))

    def run_eval(self, reply, *argv):
        agent = Agent(reply)
        qk_run.call_agent = agent
        out = io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(io.StringIO()):
            code = qk_eval.main([*argv, "--runtime", SPEC])
        return code, out.getvalue(), agent

    def results_root(self):
        roots = sorted((self.state / "qk-eval").iterdir())
        return roots[-1]

    @staticmethod
    def entry(tokens=1000, **criteria):
        return {"date": "2026-11-01", "criteria": criteria or {"a": True, "b": True}, "tokens": tokens, "seconds": 10}

    def test_table_grades_criteria_and_counts_tokens(self):
        self.case("alpha")
        code, out, _ = self.run_eval(lambda cwd, prompt: ("<a>", {"input": 1200, "cached": 1000, "output": 34}),
                                     "--case", "alpha")
        self.assertEqual(code, 0)
        row = next(line for line in out.splitlines() if line.startswith("alpha"))
        self.assertEqual(row.split(None, 1)[1].split(), ["a,", "b=FAIL,", "clean", "FAIL(1)", "1,234", "0s"])
        self.assertIn(f"no baseline for {SPEC}", out)

    @staticmethod
    def active_lesson(scope, rule):
        ledger = qk_ledger
        evidence = [ledger.append(kind, {})["id"] for kind in ("eval", "finding")]
        proposal = ledger.append("lesson", {"status": "proposed", "class": "test", "rule": rule, "scope": scope,
                                            "evidence": evidence, "case": "csv-export", "measured": []},
                                 source="model")
        measured = dict(proposal, id=proposal["id"] + "m", data=dict(proposal["data"], measured=[{"at": qk_ledger.datetime.now(qk_ledger.timezone.utc).isoformat(), "helps": True}]))
        with ledger.store_path().open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(measured) + "\n")
        ledger.append("lesson", {"lesson_id": proposal["id"], "status": "active"}, source="user")
        return proposal["id"]

    def test_lessons_flag_adds_case_stage_lessons_and_records_their_ids(self):
        review = self.active_lesson(["stage:review"], "review rule.")
        plan = self.active_lesson(["stage:plan"], "plan rule.")
        self.case("beta", skill=qk_eval.REVIEW, write=True)
        self.case("gamma", skill="qk-plan", write=False)
        code, _, agent = self.run_eval(lambda cwd, prompt: ("<a><b>", None), "--all", "--lessons")
        self.assertEqual(code, 0)
        beta, gamma = agent.calls
        run = self.results_root() / "beta" / "run-1"
        self.assertEqual(beta["prompt"], qk_run.review_prompt(
            beta["cwd"], run / "plan.md", run / "review.diff",
            qk_ledger.lessons_block([(review, "review rule.")])))
        self.assertTrue(gamma["prompt"].endswith("\n- plan rule."))
        self.assertNotIn("review rule.", gamma["prompt"])
        evals = {r["data"]["case"]: r["data"] for r in qk_ledger.records() if r["kind"] == "eval" and r["data"]}
        self.assertEqual((evals["beta"]["lessons"], evals["gamma"]["lessons"]), ([review], [plan]))
        results = json.loads((self.results_root() / "results.json").read_text())
        self.assertEqual(results["cases"]["beta"]["lessons"], [review])

    def proposed_lesson(self, rule="Check where each value is stored."):
        failed = [qk_ledger.append("eval", {"case": "csv-export", "criteria": [
            {"name": "a", "passed": True}, {"name": "b", "passed": False}]})["id"] for _ in range(2)]
        return qk_ledger.append("lesson", {
            "status": "proposed", "class": "wrong key", "rule": rule, "scope": ["stage:review"],
            "evidence": failed, "case": "csv-export", "measured": []}, source="model")["id"]

    def measure(self, lesson_id, reply):
        agent = Agent(reply)
        qk_run.call_agent = agent
        out = io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(io.StringIO()):
            code = qk_eval.measure_lesson(lesson_id, SPEC, 30)
        state = qk_ledger.latest_lessons(qk_ledger.records())[-1]["data"]
        return code, out.getvalue(), agent, state

    def test_measure_records_a_helping_lesson_with_target_runs_and_controls(self):
        self.case("csv-export", skill=qk_eval.REVIEW)
        self.case("beta", skill=qk_eval.REVIEW)
        self.case("gamma", skill="qk-plan", write=False)
        lesson_id = self.proposed_lesson()
        code, out, agent, state = self.measure(
            lesson_id, lambda cwd, prompt: ("<a><b>" if "Check where each value" in prompt else "<a>", None))
        self.assertEqual(code, 0)
        measurement, = state["measured"]
        self.assertEqual((measurement["helps"], measurement["criteria"], measurement["runtime"]),
                         (True, ["b"], SPEC))
        self.assertEqual((len(measurement["with"]), len(measurement["without"]), len(measurement["controls"])),
                         (2, 2, 2))
        self.assertEqual(len(agent.calls), 6)
        self.assertEqual(sum("Check where each value" in call["prompt"] for call in agent.calls), 3)
        self.assertIn("helps", out)
        evals = {record["id"]: record["data"] for record in qk_ledger.records() if record["kind"] == "eval"}
        self.assertEqual([evals[item].get("lessons") for item in measurement["with"]], [[lesson_id]] * 2)
        self.assertEqual([evals[item].get("lessons") for item in measurement["without"]], [None] * 2)
        active = qk_ledger.append("lesson", {"lesson_id": lesson_id, "status": "active"}, source="user")
        self.assertEqual(active["data"]["status"], "active")

    def test_measure_records_no_help_when_the_case_passes_without_the_lesson(self):
        self.case("csv-export", skill=qk_eval.REVIEW)
        self.case("beta", skill=qk_eval.REVIEW)
        self.baseline({SPEC: {"beta": self.entry(tokens=1000)}})
        lesson_id = self.proposed_lesson()
        code, out, agent, state = self.measure(lesson_id, lambda cwd, prompt: ("<a><b>", None))
        self.assertEqual(code, 0)
        self.assertEqual(len(agent.calls), 5)
        self.assertFalse(state["measured"][0]["helps"])
        self.assertEqual(state["measured"][0]["reasons"], ["without the lesson every target criterion passed"])
        with self.assertRaisesRegex(ValueError, "must show that it helps"):
            qk_ledger.append("lesson", {"lesson_id": lesson_id, "status": "active"}, source="user")

    def test_measure_refuses_unknown_or_out_of_scope_lessons_without_running(self):
        self.case("csv-export", skill="qk-plan", write=False)
        lesson_id = self.proposed_lesson()
        for target in ("missing", lesson_id):
            with self.subTest(target=target):
                code, _, agent, _ = self.measure(target, lambda cwd, prompt: ("<a><b>", None))
                self.assertEqual((code, agent.calls), (2, []))

    def test_lessons_flag_never_updates_the_baseline(self):
        self.case("alpha")
        code, _, agent = self.run_eval(lambda cwd, prompt: ("<a><b>", None),
                                       "--case", "alpha", "--lessons", "--update-baseline")
        self.assertEqual((code, agent.calls), (2, []))

    def test_skill_case_runs_in_a_fresh_repository(self):
        self.case("alpha", skill="qk-debug", write=False)
        code, _, agent = self.run_eval(lambda cwd, prompt: ("<a><b>", None), "--skill", "qk-debug")
        self.assertEqual(code, 0)
        call, = agent.calls
        self.assertIn(str(qk_run.skill("qk-debug")), call["prompt"])
        self.assertIn(f"task.md in {call['cwd']}", call["prompt"])
        self.assertFalse(call["write"])
        self.assertEqual((call["commits"], call["status"], call["task"]), ("1", "", True))
        self.assertNotIn(self.cases, call["cwd"].parents)
        self.assertEqual(call["extra_dirs"], [self.results_root()])
        self.assertEqual(call["read_only_mcp"], ())

    def test_review_case_uses_the_runner_prompt_on_an_uncommitted_diff(self):
        self.case("beta", skill=qk_eval.REVIEW, write=True)
        code, _, agent = self.run_eval(lambda cwd, prompt: ("<a><b>", None), "--case", "beta")
        self.assertEqual(code, 0)
        call, = agent.calls
        run = self.results_root() / "beta" / "run-1"
        self.assertEqual(call["prompt"], qk_run.review_prompt(call["cwd"], run / "plan.md", run / "review.diff"))
        self.assertFalse(call["write"])
        self.assertEqual((call["commits"], call["status"], call["readme"]), ("1", " M README\n", "changed\n"))
        self.assertEqual((run / "review.diff").read_text(), REVIEW_DIFF)

    def test_lost_criterion_is_a_regression(self):
        self.case("alpha")
        self.baseline({SPEC: {"alpha": self.entry()}})
        code, out, agent = self.run_eval(lambda cwd, prompt: ("<a>", None), "--case", "alpha")
        self.assertEqual(code, 1)
        self.assertEqual(len(agent.calls), 2)
        self.assertIn("2/2 → 2/3, lost: b;", out)
        self.assertIn("verdict: regression (criterion lost: alpha/b)", out)

    def test_token_limit_is_ten_percent_and_one_turn(self):
        self.case("alpha")
        # Large case: 10% decides (+11% = 33,000 > 25,000). Small case: one extra turn is not a regression.
        for base, extra, expected in ((300_000, 33_000, 1), (300_000, 30_000, 0), (300_000, 0, 0),
                                      (60_000, 22_000, 0), (60_000, 26_000, 1), (300_000, None, 0)):
            with self.subTest(base=base, extra=extra):
                self.baseline({SPEC: {"alpha": self.entry(tokens=base)}})
                usage = None if extra is None else {"input": base + extra, "cached": 0, "output": 0}
                code, out, agent = self.run_eval(lambda cwd, prompt: ("<a><b>", usage), "--case", "alpha")
                self.assertEqual(code, expected, out)
                self.assertEqual(len(agent.calls), 1)
                if expected:
                    self.assertIn("> 10% and > 25,000: alpha)", out)

    def test_flipped_case_is_rerun_once_and_the_rerun_counts(self):
        self.case("alpha")
        self.case("gamma")
        self.baseline({SPEC: {"alpha": self.entry(), "gamma": self.entry()}})
        seen = []

        def reply(cwd, prompt):
            name = (cwd / "task.md").read_text().split()[-1]
            seen.append(name)
            return ("<a>" if seen == ["alpha"] else "<a><b>"), None
        code, out, agent = self.run_eval(reply, "--all")
        self.assertEqual(code, 0, out)
        self.assertEqual(seen, ["alpha", "alpha", "gamma"])
        root = self.results_root()
        cases = json.loads((root / "results.json").read_text())["cases"]
        self.assertEqual((cases["alpha"]["runs"], cases["gamma"]["runs"]), (2, 1))
        self.assertTrue((root / "alpha" / "run-1").is_dir() and (root / "alpha" / "run-2").is_dir())
        self.assertFalse((root / "gamma" / "run-2").exists())
        self.assertIn("rerun: yes", next(line for line in out.splitlines() if "baseline alpha" in line))

    def test_each_flipped_attempt_is_retained_in_the_real_ledger(self):
        self.case("alpha")
        self.baseline({SPEC: {"alpha": self.entry()}})
        replies = iter(("<a>", "<a><b>"))
        code, out, agent = self.run_eval(lambda cwd, prompt: (next(replies), None), "--case", "alpha")
        self.assertEqual(code, 0, out)
        self.assertEqual(len(agent.calls), 2)
        events = [record for record in qk_ledger.records() if record["kind"] == "eval"]
        self.assertEqual(len(events), 2)
        self.assertEqual([event["data"]["passed"] for event in events], [False, True])
        self.assertEqual([event["data"]["runtime"] for event in events], [SPEC, SPEC])
        self.assertEqual([event["data"]["case"] for event in events], ["alpha", "alpha"])
        self.assertNotEqual(events[0]["id"], events[1]["id"])
        self.assertTrue(any("run-1" in ref for ref in events[0]["refs"]))
        self.assertTrue(any("run-2" in ref for ref in events[1]["refs"]))
        self.assertEqual([{c["name"]: c["passed"] for c in event["data"]["criteria"]} for event in events],
                         [{"a": True, "b": False, "clean": True}, {"a": True, "b": True, "clean": True}])

    def test_invalid_ledger_destination_warns_without_changing_eval_result(self):
        self.case("alpha")
        obstacle = Path(self.tmp.name) / "not-a-directory"
        obstacle.write_text("existing user file\n")
        qk_run.call_agent = Agent(lambda cwd, prompt: ("<a><b>", None))
        out, err = io.StringIO(), io.StringIO()
        with mock.patch.dict(os.environ, {"QK_STATE_DIR": str(obstacle / "ledger")}):
            with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
                code = qk_eval.main(["--case", "alpha", "--runtime", SPEC])
        self.assertEqual(code, 0, out.getvalue() + err.getvalue())
        self.assertIn("warning", (out.getvalue() + err.getvalue()).lower())
        self.assertEqual(obstacle.read_text(), "existing user file\n")
        result = json.loads((self.results_root() / "results.json").read_text())["cases"]["alpha"]
        self.assertIsNone(result["error"])
        self.assertEqual({c["name"]: c["passed"] for c in result["criteria"]},
                         {"a": True, "b": True, "clean": True})
        self.assertEqual(result["runs"], 1)

    def test_agent_cannot_change_its_grader_and_reading_it_fails_clean(self):
        self.case("alpha")
        check = self.cases / "alpha" / "check.py"

        def tamper(spec, prompt, cwd, write, timeout, extra_dirs, *, events, progress, read_only_mcp=(),
                   claude_skills=None):
            check.write_text('import json\nprint(json.dumps([{"name": "a", "passed": True, "detail": ""},'
                             ' {"name": "b", "passed": True, "detail": ""}]))\n')
            Path(events).write_text(json.dumps({"type": "tool_execution_start", "toolName": "write",
                                                "args": {"path": str(check)}}) + "\n")
            return "<a>", None

        qk_run.call_agent = tamper
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            code = qk_eval.main(["--case", "alpha", "--runtime", SPEC])
        self.assertEqual(code, 0)
        graded = json.loads((self.results_root() / "alpha" / "run-1" / "check.json").read_text())
        self.assertEqual({c["name"]: c["passed"] for c in graded}, {"a": True, "b": False, "clean": False})

    def test_grader_failure_is_never_recorded_as_baseline(self):
        self.case("alpha")
        (self.cases / "alpha" / "check.py").write_text("raise SystemExit(3)\n")
        self.baseline({SPEC: {"alpha": self.entry()}})
        code, out, _ = self.run_eval(lambda cwd, prompt: ("<a><b>", None), "--case", "alpha", "--update-baseline")
        self.assertEqual(code, 1, out)
        self.assertIn("baseline not updated for cases with an agent or grader error: alpha", out)
        self.assertEqual(json.loads(qk_eval.BASELINE.read_text()), {SPEC: {"alpha": self.entry()}})

    def test_kit_comparison_uses_one_claude_base_and_the_same_output_format(self):
        self.case("alpha")
        self.case("rev", skill=qk_eval.REVIEW, write=False)
        sp = Path(self.tmp.name) / "sp"
        (sp / ".claude-plugin").mkdir(parents=True)
        (sp / ".claude-plugin" / "plugin.json").write_text("{}")
        self.baseline({"claude:x": {"alpha": self.entry(tokens=1)}})
        seen = []

        def agent(spec, prompt, cwd, write, timeout, extra_dirs, *, events, progress, read_only_mcp=(),
                  claude_skills=None):
            seen.append((prompt, write, claude_skills))
            return "<a><b>", {"input": 999_999, "cached": 0, "output": 0}
        for kit in ("none", "superpowers", "qk"):
            qk_run.call_agent = agent
            with contextlib.redirect_stdout(io.StringIO()) as out, contextlib.redirect_stderr(io.StringIO()):
                code = qk_eval.main(["--all", "--runtime", "claude:x", "--kit", kit, "--superpowers-dir", str(sp)])
            self.assertEqual(code, 0, out.getvalue())  # no baseline comparison for --kit
            self.assertIn("no baseline for claude:x", out.getvalue())
        by_kit = dict(zip(("none", "superpowers", "qk"), [seen[i:i + 2] for i in (0, 2, 4)]))
        for kit, (alpha, rev) in by_kit.items():
            expected = ["--setting-sources", "project"] + (["--plugin-dir", str(sp)] if kit == "superpowers" else [])
            self.assertEqual(alpha[2], expected, kit)
            self.assertIn(qk_eval.REPORT_FORMAT, alpha[0], kit)
            self.assertEqual(alpha[1], True, kit)
            self.assertIn("qk-result", rev[0], kit)
            self.assertEqual(rev[1], False, kit)
            self.assertEqual(("SKILL.md" in alpha[0]), kit == "qk", kit)
            self.assertEqual(("Review by defect class" in rev[0]), kit == "qk", kit)
        self.assertEqual(json.loads(qk_eval.BASELINE.read_text()), {"claude:x": {"alpha": self.entry(tokens=1)}})

    def test_kit_comparison_is_refused_where_it_cannot_be_fair(self):
        self.case("alpha")
        for argv, message in ((["--runtime", "omp:anthropic/x", "--kit", "none"], "only on the claude runtime"),
                              (["--runtime", "claude:x", "--kit", "none", "--update-baseline"], "never update"),
                              (["--runtime", "claude:x", "--kit", "superpowers"], "needs --superpowers-dir")):
            err = io.StringIO()
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(err):
                self.assertEqual(qk_eval.main(["--case", "alpha", *argv]), 2)
            self.assertIn(message, err.getvalue())

    def test_update_baseline_merges_into_this_runtime(self):
        self.case("alpha")
        other_runtime, other_case = {"alpha": self.entry(tokens=5)}, self.entry(tokens=7)
        self.baseline({"claude:opus": other_runtime, SPEC: {"gamma": other_case}})
        code, out, _ = self.run_eval(lambda cwd, prompt: ("<a>", {"input": 10, "cached": 0, "output": 5}),
                                     "--case", "alpha", "--update-baseline")
        self.assertEqual(code, 0, out)
        self.assertIn(f"no baseline for {SPEC} / alpha", out)
        self.assertEqual(json.loads(qk_eval.BASELINE.read_text()), {
            "claude:opus": other_runtime,
            SPEC: {"gamma": other_case, "alpha": {"date": time.strftime("%Y-%m-%d"),
                                                  "criteria": {"a": True, "b": False, "clean": True}, "tokens": 15,
                                                  "seconds": 0}}})

    def test_agent_error_is_reported_and_never_recorded(self):
        self.case("alpha")

        def reply(cwd, prompt):
            error = qk_run.Blocked("codex: timed out after 5s; agent stopped")
            error.usage = {"input": 40, "cached": 0, "output": 2}
            raise error
        code, out, _ = self.run_eval(reply, "--case", "alpha", "--update-baseline")
        self.assertEqual(code, 1)
        row = next(line for line in out.splitlines() if line.startswith("alpha"))
        self.assertEqual(row.split()[-3:], ["ERROR", "42", "0s"])
        self.assertIn("verdict: error (agent error: alpha)", out)
        self.assertFalse(qk_eval.BASELINE.exists())
        result = json.loads((self.results_root() / "results.json").read_text())["cases"]["alpha"]
        self.assertIn("timed out", result["error"])
        self.assertEqual([c["passed"] for c in result["criteria"]], [False, False, True])

    def test_results_directory_layout(self):
        self.case("alpha")
        self.run_eval(lambda cwd, prompt: ("<a><b> final words", None), "--case", "alpha")
        roots = list((self.state / "qk-eval").iterdir())
        self.assertEqual(len(roots), 1)
        run = roots[0] / "alpha" / "run-1"
        self.assertTrue((run / "events.jsonl").is_file())
        self.assertEqual((run / "final.md").read_text(), "<a><b> final words")
        self.assertEqual([c["passed"] for c in json.loads((run / "check.json").read_text())], [True, True, True])
        results = json.loads((roots[0] / "results.json").read_text())
        self.assertEqual((results["runtime"], results["regression"], results["cases"]["alpha"]["runs"]), (SPEC, False, 1))

    def test_empty_selection_exits_2(self):
        self.case("alpha")
        for argv in (["--skill", "qk-plan"], ["--case", "missing"]):
            with self.subTest(argv=argv):
                code, _, agent = self.run_eval(lambda cwd, prompt: ("", None), *argv)
                self.assertEqual((code, agent.calls), (2, []))


if __name__ == "__main__":
    unittest.main()
