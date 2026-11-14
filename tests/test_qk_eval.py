import contextlib
import io
import json
import os
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import qk_eval  # noqa: E402
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


def finding(file, line, severity="important"):
    return {"severity": severity, "file": file, "line": line, "claim": "x", "fix": "y"}


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

    def test_case_files_are_valid(self):
        cases = {case["name"]: case for case in qk_eval.all_cases()}
        self.assertEqual({name: case["skill"] for name, case in cases.items()},
                         {"csv-export": "qk-cook", "pagination-empty-page": "qk-debug", "bundle-malformed": "runner-review"})
        for name, case in cases.items():
            directory = REAL_CASES / name
            self.assertTrue((directory / "check.py").is_file(), name)
            if case["skill"] == qk_eval.REVIEW:
                self.assertFalse(case["write"])
                self.assertTrue((directory / "plan.md").is_file() and (directory / "review.diff").is_file(), name)
            else:
                self.assertTrue(case["write"])
                self.assertTrue((directory / "task.md").is_file() and (directory / "hidden").is_dir(), name)

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
                                                     "test-catches-bug": False, "report": False})

    def test_bundle_review_grading(self):
        case, workdir = self.prepare("bundle-malformed")
        places = ["capacity", "nested-statement", "list-name"]
        empty = self.grade(case, workdir)
        self.assertEqual([empty[name] for name in ["result", *places]], [False, False, False, False])
        covering = [finding(f"{workdir}/bundle/loader.py", 16), finding("bundle/loader.py", 35, "blocker"),
                    finding("./bundle/loader.py", 58)]
        self.assertEqual(set(self.grade(case, workdir, review_result(*covering)).values()), {True})
        missing = self.grade(case, workdir, review_result(covering[0], covering[1], finding("bundle/loader.py", 58, "nit")))
        self.assertEqual([missing[name] for name in places], [True, True, False])
        outside = self.grade(case, workdir, review_result(*covering, finding("bundle/models.py", 20)))
        self.assertFalse(outside["no-outside-important"])
        self.assertTrue(all(outside[name] for name in places))


class Agent:
    """Fake runtime: `reply(cwd, prompt)` returns (text, usage) or raises; each call records what the agent saw."""

    def __init__(self, reply):
        self.reply = reply
        self.calls = []

    def __call__(self, spec, prompt, cwd, write, timeout, extra_dirs, *, events, progress, read_only_mcp=()):
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
        os.environ["XDG_STATE_HOME"] = str(self.state)

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
        self.assertEqual(row.split(None, 1)[1].split(), ["a,", "b=FAIL", "FAIL(1)", "1,234", "0s"])
        self.assertIn(f"no baseline for {SPEC}", out)

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
        self.assertIn("2/2 → 1/2, lost: b;", out)
        self.assertIn("verdict: regression (criterion lost: alpha/b)", out)

    def test_token_limit_is_ten_percent(self):
        self.case("alpha")
        self.baseline({SPEC: {"alpha": self.entry(tokens=1000)}})
        for output, expected in ((110, 1), (100, 0), (90, 0), (None, 0)):
            with self.subTest(output=output):
                usage = None if output is None else {"input": 1000, "cached": 900, "output": output}
                code, out, agent = self.run_eval(lambda cwd, prompt: ("<a><b>", usage), "--case", "alpha")
                self.assertEqual(code, expected, out)
                self.assertEqual(len(agent.calls), 1)
                if expected:
                    self.assertIn("verdict: regression (tokens +11.0% > 10%: alpha)", out)

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
                                                  "criteria": {"a": True, "b": False}, "tokens": 15, "seconds": 0}}})

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
        self.assertEqual([c["passed"] for c in result["criteria"]], [False, False])

    def test_results_directory_layout(self):
        self.case("alpha")
        self.run_eval(lambda cwd, prompt: ("<a><b> final words", None), "--case", "alpha")
        roots = list((self.state / "qk-eval").iterdir())
        self.assertEqual(len(roots), 1)
        run = roots[0] / "alpha" / "run-1"
        self.assertTrue((run / "events.jsonl").is_file())
        self.assertEqual((run / "final.md").read_text(), "<a><b> final words")
        self.assertEqual([c["passed"] for c in json.loads((run / "check.json").read_text())], [True, True])
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
