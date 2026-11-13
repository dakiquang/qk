import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SKILL = Path("skills/qk-cook/SKILL.md")
CLOSING = "**Needs your decision**: what waits on the user\n"
SKIP = shutil.ignore_patterns("." + "git", "__pycache__")


class ReportContract(unittest.TestCase):
    def run_on(self, edit):
        with tempfile.TemporaryDirectory() as tmp:
            copy = Path(tmp) / "qk"
            shutil.copytree(ROOT, copy, ignore=SKIP)
            path = copy / SKILL
            path.write_text(edit(path.read_text(encoding="utf-8")), encoding="utf-8")
            return subprocess.run(
                [sys.executable, "-B", str(copy / "scripts" / "validate.py")],
                capture_output=True, text=True, timeout=60,
            )

    def test_unchanged_repository_passes(self):
        self.assertEqual(self.run_on(lambda text: text).returncode, 0)

    def test_labels_only_inside_a_fence_fail(self):
        def fence(text):
            start = text.index("**Done**: ")
            end = text.index(CLOSING) + len(CLOSING)
            return text[:start] + "```text\n" + text[start:end] + "```\n" + text[end:]
        done = self.run_on(fence)
        self.assertEqual(done.returncode, 1)
        self.assertIn("qk-cook", done.stdout)

    def test_earlier_example_label_still_passes(self):
        example = "## Report\n\n```text\n**Evidence**: example\n```\n"
        self.assertEqual(self.run_on(lambda text: text.replace("## Report\n", example, 1)).returncode, 0)

    def test_contract_row_only_in_prose_fails(self):
        def move(text):
            row = next(line for line in text.splitlines() if line.startswith("| **Result** |"))
            return text.replace(row + "\n", "", 1) + "\nSee the table: " + row + "\n"
        done = self.run_on(move)
        self.assertEqual(done.returncode, 1)
        self.assertIn("Result", done.stdout)


if __name__ == "__main__":
    unittest.main()
