"""`qk agent run` and `qk agent family`: one isolated turn that reports and never touches git."""

import contextlib
import importlib
import io
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import time
import unittest
from unittest import mock

import fake_runtimes


SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))
qk = importlib.import_module("qk")
qk_run = importlib.import_module("qk_run")
ledger = importlib.import_module("qk_ledger")


class AgentCliTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.addCleanup(fake_runtimes.collect_pipes)
        self.root = Path(directory.name).resolve()
        self.work = self.root / "work"
        self.work.mkdir()
        (self.root / "home").mkdir()
        self.prompt_file = self.root / "prompt.txt"
        self.settings = {"PATH": fake_runtimes.path_with(self.root / "bin"),
                         "FAKE_PROMPT": str(self.prompt_file), "QK_STATE_DIR": str(self.root / "ledger"),
                         "HOME": str(self.root / "home"), "CODEX_HOME": str(self.root / "home" / ".codex")}

    def run_cli(self, *argv, prompt="Do the task.", **extra):
        output, errors = io.StringIO(), io.StringIO()
        with mock.patch.dict(os.environ, dict(self.settings, **extra)), \
                mock.patch("sys.stdin", io.StringIO(prompt)), \
                contextlib.redirect_stdout(output), contextlib.redirect_stderr(errors):
            status = qk.main(["agent", "run", *argv])
        return status, output.getvalue(), errors.getvalue()

    def turn(self, *argv, spec="claude:", access="--read-only", **extra):
        status, output, _ = self.run_cli("--spec", spec, "--cwd", str(self.work), access, "--json", *argv, **extra)
        return status, json.loads(output)

    def test_done_turn_reports_result_usage_and_family(self):
        status, data = self.turn()
        self.assertEqual(status, 0)
        self.assertEqual((data["contract"], data["status"], data["reason"]), (1, "done", ""))
        self.assertEqual((data["family"], data["spec"]), ("anthropic", "claude:"))
        self.assertEqual(data["result"]["summary"], "fake turn")
        self.assertIn("cwd=work", data["text"])
        self.assertEqual(data["usage"], {"input": 15, "cached": 4, "output": 7, "cost_usd": 0.25})
        self.assertEqual((data["events"], data["lessons"]), (None, []))
        self.assertIsInstance(data["seconds"], int)

    def test_prompt_rules_follow_the_access_flags(self):
        self.turn()
        prompt = self.prompt_file.read_text()
        self.assertTrue(prompt.startswith("Do the task.\n"))
        self.assertIn(qk_run.RESULT_CONTRACT, prompt)
        self.assertNotIn(qk_run.NO_GIT, prompt)
        self.turn(access="--write")
        prompt = self.prompt_file.read_text()
        self.assertIn(qk_run.NO_GIT, prompt)
        self.assertIn(qk_run.CLEAN, prompt)
        status, data = self.turn("--no-git-rules", "--no-result-contract", access="--write", FAKE_STATUS="none")
        self.assertEqual(self.prompt_file.read_text(), "Do the task.")
        self.assertEqual((status, data["status"], data["result"]), (0, "done", None))

    def test_agent_reported_block_keeps_the_result_and_exits_2(self):
        for reported in ("blocked", "needs_input"):
            with self.subTest(reported=reported):
                status, data = self.turn(FAKE_STATUS=reported)
                self.assertEqual((status, data["status"], data["reason"]), (2, reported, "fake reason"))
                self.assertEqual(data["result"]["status"], reported)

    def test_missing_result_block_is_blocked(self):
        status, data = self.turn(FAKE_STATUS="none")
        self.assertEqual((status, data["status"], data["result"]), (2, "blocked", None))
        self.assertIn("no ```qk-result``` block", data["reason"])
        self.assertIn("cwd=work", data["text"])

    def test_read_only_turn_calling_mcp_is_stopped_unless_the_server_is_allowed(self):
        status, data = self.turn(FAKE_TOOL="mcp__tracker__search")
        self.assertEqual((status, data["status"]), (2, "blocked"))
        self.assertIn("read-only stage called", data["reason"])
        status, data = self.turn("--read-only-mcp", "tracker", FAKE_TOOL="mcp__tracker__search")
        self.assertEqual((status, data["status"]), (0, "done"))
        status, data = self.turn(access="--write", FAKE_TOOL="mcp__tracker__search")
        self.assertEqual((status, data["status"]), (0, "done"))

    def test_runtime_failures_are_blocked_with_a_reason(self):
        status, data = self.turn(FAKE_EXIT="3")
        self.assertEqual((status, data["status"]), (2, "blocked"))
        self.assertIn("exited 3", data["reason"])
        self.assertIsNone(data["limit"])
        status, data = self.turn("--timeout", "1", FAKE_SLEEP="30")
        self.assertEqual((status, data["status"]), (2, "blocked"))
        self.assertIn("timed out after 1s", data["reason"])
        status, data = self.turn(PATH=str(self.root / "empty"))
        self.assertEqual((status, data["status"]), (2, "blocked"))
        self.assertIn("runtime binary not found", data["reason"])

    def test_usage_limit_is_reported_with_its_runtime_and_reset_time(self):
        claude = "You've hit your 5-hour limit \u00b7 resets 11:50pm (Asia/Saigon)"
        status, data = self.turn(FAKE_EXIT="1", FAKE_STDERR=claude)
        self.assertEqual((status, data["status"]), (2, "blocked"))
        self.assertIn(claude, data["reason"])
        self.assertEqual((data["limit"]["runtime"], data["limit"]["message"]), ("claude", claude))
        self.assertRegex(data["limit"]["reset_at"], r"T23:50:00\+07:00$")
        codex = "You\u2019ve hit your usage limit. Upgrade to Pro or try again at 6:52 PM."
        status, data = self.turn(spec="codex:", FAKE_EXIT="1", FAKE_STDERR=codex)
        self.assertEqual((status, data["limit"]["runtime"]), (2, "codex"))
        self.assertRegex(data["limit"]["reset_at"], r"T18:52:00")
        status, data = self.turn(FAKE_STDERR=claude)  # a limit message from a turn that still finished
        self.assertEqual((status, data["limit"]), (0, None))

    def test_rejected_input_runs_nothing(self):
        cases = (("--spec", "claude:", "--cwd", str(self.root / "missing"), "--read-only"),
                 ("--spec", "other:model", "--cwd", str(self.work), "--read-only"),
                 ("--spec", "omp:unknown/thing", "--cwd", str(self.work), "--read-only"),
                 ("--spec", "claude:", "--cwd", str(self.work), "--read-only", "--timeout", "0"))
        for argv in cases:
            with self.subTest(argv=argv):
                status, output, errors = self.run_cli(*argv, "--json")
                self.assertEqual((status, output), (2, ""))
                self.assertTrue(errors.startswith("qk: "), errors)
        status, output, errors = self.run_cli("--spec", "claude:", "--cwd", str(self.work), "--read-only",
                                              prompt=" \n")
        self.assertEqual((status, output), (2, ""))
        self.assertIn("prompt on stdin is empty", errors)
        self.assertFalse(self.prompt_file.exists())

    def test_relative_directories_reach_the_runtime_as_absolute_paths(self):
        arguments = self.root / "arguments.txt"
        (self.root / "extra").mkdir()
        with mock.patch.dict(os.environ, {"FAKE_ARGV": str(arguments)}):
            previous = os.getcwd()
            os.chdir(str(self.root))
            self.addCleanup(os.chdir, previous)
            status, output, _ = self.run_cli("--spec", "codex:", "--cwd", "work", "--read-only",
                                             "--add-dir", "extra", "--json")
        self.assertEqual((status, json.loads(output)["status"]), (0, "done"))
        argv = json.loads(arguments.read_text())
        self.assertEqual(argv[argv.index("-C") + 1], str(self.work))
        self.assertIn(str(self.root / "extra"), argv)

    def test_events_file_receives_raw_events(self):
        events = self.root / "events.jsonl"
        _, data = self.turn("--events", str(events))
        self.assertEqual(data["events"], str(events))
        self.assertEqual([json.loads(line)["type"] for line in events.read_text().splitlines()], ["result"])

    def test_lessons_are_appended_and_reported(self):
        with mock.patch.object(ledger, "lessons_for", return_value=[("abc123", "Check the empty page.")]) as chosen:
            _, data = self.turn("--lessons", "review", "--repo", "project")
        chosen.assert_called_once_with("review", "project")
        self.assertEqual(data["lessons"], ["abc123"])
        self.assertIn("- Check the empty page.\n" + qk_run.RESULT_CONTRACT, self.prompt_file.read_text())
        _, data = self.turn("--lessons", "review")
        self.assertEqual(data["lessons"], [])
        self.assertNotIn("Verified lessons", self.prompt_file.read_text())

    def test_text_output_prints_the_reply_and_explains_a_block(self):
        status, output, errors = self.run_cli("--spec", "claude:", "--cwd", str(self.work), "--read-only",
                                              FAKE_STATUS="blocked")
        self.assertEqual(status, 2)
        self.assertIn("cwd=work", output)
        self.assertIn("qk: blocked: fake reason", errors)

    def test_write_turn_leaves_git_to_the_caller(self):
        def git(*args):
            return subprocess.run(["git", *args], cwd=str(self.work), check=True, capture_output=True,
                                  text=True).stdout.strip()
        git("init", "-q", "-b", "main")
        (self.work / "a.txt").write_text("a\n")
        git("add", "a.txt")
        git("-c", "user.name=t", "-c", "user.email=t@example.invalid", "commit", "-q", "-m", "base")
        before = (git("rev-parse", "HEAD"), git("for-each-ref"), git("stash", "list"))
        status, data = self.turn(access="--write", FAKE_WRITE="made.txt")
        self.assertEqual((status, data["status"]), (0, "done"))
        self.assertEqual((git("rev-parse", "HEAD"), git("for-each-ref"), git("stash", "list")), before)
        self.assertEqual(git("status", "--porcelain"), "?? made.txt")

    def test_codex_turn_uses_a_private_home_that_is_removed(self):
        status, data = self.turn(spec="codex:")
        self.assertEqual((status, data["family"]), (0, "openai"))
        self.assertEqual(data["usage"], {"input": 20, "cached": 5, "output": 3})
        home = Path(data["text"].split("home=")[1].split("\n")[0])
        self.assertEqual(home.name, "codex-home")
        self.assertNotEqual(home, self.root / "home")
        self.assertFalse(home.parent.exists())

    def test_sigterm_stops_the_agent_and_removes_the_scratch_directory(self):
        started = self.root / "started.txt"
        proc = subprocess.Popen(
            [sys.executable, str(SCRIPTS / "qk.py"), "agent", "run", "--spec", "codex:", "--cwd", str(self.work),
             "--read-only", "--json"],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
            env=dict(os.environ, **self.settings, FAKE_PID=str(started), FAKE_SLEEP="60"))
        self.addCleanup(proc.stdout.close)
        self.addCleanup(proc.stderr.close)
        proc.stdin.write("Task.")
        proc.stdin.close()
        deadline = time.monotonic() + 20
        while not started.exists() and time.monotonic() < deadline:
            time.sleep(0.05)
        agent, home = started.read_text().split(" ", 1)
        proc.send_signal(signal.SIGTERM)
        proc.wait(timeout=30)
        data = json.loads(proc.stdout.read())
        self.assertEqual((proc.returncode, data["status"]), (2, "blocked"))
        self.assertIn("stopped by SIGTERM", data["reason"])
        with self.assertRaises(ProcessLookupError):
            os.kill(int(agent), 0)
        self.assertFalse(Path(home).parent.exists())

    def test_two_turns_in_two_directories_run_at_once_without_mixing(self):
        barrier = self.root / "barrier"
        barrier.mkdir()
        turns, homes = [], set()
        for name in ("one", "two"):
            (self.root / name).mkdir()
            events = self.root / (name + ".jsonl")
            proc = subprocess.Popen(
                [sys.executable, str(SCRIPTS / "qk.py"), "agent", "run", "--spec", "codex:", "--cwd",
                 str(self.root / name), "--write", "--events", str(events), "--json"],
                stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                env=dict(os.environ, **self.settings, FAKE_BARRIER=str(barrier), FAKE_WRITE="made.txt"))
            proc.stdin.write("Task for %s." % name)
            proc.stdin.close()
            turns.append((name, events, proc))
        for name, events, proc in turns:
            self.addCleanup(proc.stdout.close)
            self.addCleanup(proc.stderr.close)
            proc.wait(timeout=60)
            output, errors = proc.stdout.read(), proc.stderr.read()
            self.assertEqual(proc.returncode, 0, errors)
            text = json.loads(output)["text"]
            self.assertIn("cwd=%s alone=False" % name, text)
            homes.add(text.split("home=")[1].split("\n")[0])
            self.assertEqual(len(events.read_text().splitlines()), 1)
            self.assertTrue((self.root / name / "made.txt").is_file())
        self.assertEqual(len(homes), 2)


class AgentFamilyTests(unittest.TestCase):
    def cli(self, *argv):
        output, errors = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(output), contextlib.redirect_stderr(errors):
            status = qk.main(["agent", "family", *argv])
        return status, output.getvalue(), errors.getvalue()

    def test_family_matches_the_runner(self):
        self.assertEqual(self.cli("codex:"), (0, "openai\n", ""))
        status, output, _ = self.cli("omp:anthropic/claude-opus-5-5", "--json")
        self.assertEqual((status, json.loads(output)),
                         (0, {"contract": 1, "spec": "omp:anthropic/claude-opus-5-5", "family": "anthropic"}))

    def test_unknown_family_is_rejected(self):
        status, output, errors = self.cli("omp:")
        self.assertEqual((status, output), (2, ""))
        self.assertIn("needs an explicit model", errors)


if __name__ == "__main__":
    unittest.main()
