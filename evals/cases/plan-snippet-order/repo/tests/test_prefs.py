import json
import os
import subprocess
import sys
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "prefs.py"
sys.path.insert(0, str(ROOT))

import prefs  # noqa: E402


class Hook(unittest.TestCase):
    def test_remembers_from_now_on(self):
        self.assertEqual(prefs.run_hook(json.dumps({"prompt": "From now on use pnpm"})), "remember")
        self.assertEqual(prefs.run_hook(json.dumps({"prompt": "use pnpm once"})), "")

    def test_latency_budget(self):
        if os.environ.get("CI"):
            self.skipTest("latency budget is checked on a local machine only")
        # Interpreter startup differs a lot between Python builds, so the budget is
        # the hook's cost on top of a bare start of the same interpreter.
        def p95(command, stdin):
            samples = []
            for _ in range(20):
                start = time.perf_counter()
                subprocess.run(command, input=stdin, capture_output=True, text=True, timeout=30)
                samples.append(time.perf_counter() - start)
            samples.sort()
            return samples[int(len(samples) * 0.95) - 1]

        payload = json.dumps({"prompt": "From now on use pnpm"})
        bare = p95([sys.executable, "-I", "-S", "-c", "pass"], "")
        hook = p95([sys.executable, "-I", "-S", str(SCRIPT), "hook"], payload)
        self.assertLess(hook - bare, 0.05, f"hook p95 {hook * 1000:.0f} ms, bare {bare * 1000:.0f} ms")


if __name__ == "__main__":
    unittest.main()
