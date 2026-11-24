"""Runtime adapters: the shared status-line reader, the session-start hook and Claude Code's status line wrapper."""

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest

ADAPTERS = Path(__file__).resolve().parent.parent / "adapters"


class AdapterTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        self.commands = self.root / "status-commands"
        self.environment = dict(os.environ, QK_STATUS_COMMANDS=str(self.commands), TMPDIR=str(self.root),
                                QK_STATUS_TTL="5", QK_BIN=f"{sys.executable} {self.root / 'fake_qk.py'}")
        (self.root / "fake_qk.py").write_text(
            "import sys\nif sys.argv[1:] == ['brief', '--pending']:\n"
            "    print(open(sys.argv[0] + '.pending').read(), end='')\n")
        self.pending("")

    def pending(self, text):
        (self.root / "fake_qk.py.pending").write_text(text)

    def run_adapter(self, *argv, stdin=""):
        return subprocess.run([*argv], input=stdin, capture_output=True, text=True, env=self.environment, timeout=30)

    def lines(self):
        return self.run_adapter(sys.executable, str(ADAPTERS / "status_lines.py"))

    def test_status_lines_join_every_command_and_skip_failing_or_slow_ones(self):
        self.commands.write_text("# a comment\necho 'qk 3f9c implementing 3/7'\nexit 3\nsleep 5; echo late\n"
                                 "printf 'harness aaea46 · eval review.run\\n\\n'\n")
        started = time.monotonic()
        result = self.lines()
        self.assertLess(time.monotonic() - started, 4)
        self.assertEqual((result.returncode, result.stdout.splitlines()),
                         (0, ["qk 3f9c implementing 3/7", "harness aaea46 · eval review.run"]))

    def test_a_timeout_stops_everything_the_command_started(self):
        marker = self.root / "late"
        self.commands.write_text(f"sh -c 'sleep 2; touch {marker}'; true\n")  # a child that outlives a killed shell
        self.assertEqual(self.lines().stdout, "")
        time.sleep(2.5)
        self.assertFalse(marker.exists(), "the timed-out command kept running")

    def test_the_cache_is_not_shared_across_state_directories(self):
        self.commands.write_text('echo "state=$QK_RUN_STATE_DIR"\n')
        self.environment["QK_RUN_STATE_DIR"] = "/one"
        self.assertEqual(self.lines().stdout, "state=/one\n")
        self.environment["QK_RUN_STATE_DIR"] = "/two"
        self.assertEqual(self.lines().stdout, "state=/two\n")

    def test_status_lines_are_cached_per_command_list(self):
        counter = self.root / "count"
        self.commands.write_text(f"echo x >> {counter}; echo line\n")
        self.assertEqual(self.lines().stdout, "line\n")
        self.assertEqual(self.lines().stdout, "line\n")
        self.assertEqual(counter.read_text(), "x\n")
        self.commands.write_text(f"echo y >> {counter}; echo other\n")
        self.assertEqual(self.lines().stdout, "other\n")

    def test_nothing_to_show_prints_nothing(self):
        self.commands.write_text("true\n")
        result = self.lines()
        self.assertEqual((result.returncode, result.stdout), (0, ""))

    def test_session_start_speaks_only_when_something_waits(self):
        self.commands.write_text("true\n")
        hook = [sys.executable, str(ADAPTERS / "session_start.py")]
        self.assertEqual(self.run_adapter(*hook, stdin='{"hook_event_name": "SessionStart"}').stdout, "")
        self.pending("qk: 2 runs to decide (latest 07:02): qk sync && qk brief\n")
        result = self.run_adapter(*hook, stdin="{}")
        reply = json.loads(result.stdout)
        self.assertEqual(reply["systemMessage"], "qk: 2 runs to decide (latest 07:02): qk sync && qk brief")
        self.assertEqual(reply["hookSpecificOutput"]["hookEventName"], "SessionStart")
        self.assertIn("qk-morning", reply["hookSpecificOutput"]["additionalContext"])
        self.pending("")
        self.commands.write_text("for i in 1 2 3 4 5; do echo line$i; done\n")
        reply = json.loads(self.run_adapter(*hook, stdin="{}").stdout)
        self.assertEqual(reply, {"systemMessage": "line1; line2; line3; +2 more"})  # no tokens without waiting cards

    def test_claude_status_line_keeps_the_wrapped_output_first(self):
        self.commands.write_text("echo 'qk 3f9c verifying 4/7'\n")
        wrapped = self.root / "limits.sh"
        wrapped.write_text('read -r line; echo "limits: $line"\n')
        result = self.run_adapter("/bin/sh", str(ADAPTERS / "claude" / "statusline.sh"), "/bin/sh", str(wrapped),
                                  stdin='{"model": "x"}\n')
        self.assertEqual(result.stdout.splitlines(), ['limits: {"model": "x"}', "qk 3f9c verifying 4/7"])
        alone = self.run_adapter("/bin/sh", str(ADAPTERS / "claude" / "statusline.sh"), stdin="{}")
        self.assertEqual(alone.stdout.splitlines(), ["qk 3f9c verifying 4/7"])


if __name__ == "__main__":
    unittest.main()
