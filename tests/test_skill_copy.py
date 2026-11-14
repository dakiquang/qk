"""Skills must keep working when an installer copies only the skill folder."""
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SKILLS = Path(__file__).resolve().parent.parent / "skills"
SCRIPT_REF = re.compile(r"<skill folder>/(scripts/[\w.]+\.py)")


class CopiedSkillFolder(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)

    def copy(self, name):
        target = Path(self.tmp.name) / "installed" / name
        shutil.copytree(SKILLS / name, target)
        return target

    def referenced_scripts(self, skill):
        refs = set(SCRIPT_REF.findall((skill / "SKILL.md").read_text(encoding="utf-8")))
        self.assertTrue(refs, f"{skill.name}: SKILL.md names no script inside the skill folder")
        return refs

    def run_script(self, script, *args, env=None):
        return subprocess.run([sys.executable, "-I", str(script), *args], capture_output=True,
                              text=True, timeout=30, env=env)

    def test_every_referenced_script_ships_with_its_skill(self):
        for skill in sorted(p for p in SKILLS.iterdir() if (p / "SKILL.md").is_file()):
            text = (skill / "SKILL.md").read_text(encoding="utf-8")
            self.assertNotIn("../../scripts", text, f"{skill.name} reaches outside its folder")
            for ref in SCRIPT_REF.findall(text):
                self.assertTrue((skill / ref).is_file(), f"{skill.name}: missing {ref}")

    def test_copied_qk_commit_runs_its_identity_script(self):
        skill = self.copy("qk-commit")
        for ref in self.referenced_scripts(skill):
            result = self.run_script(skill / ref, "--help")
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("identity", result.stdout)

    def test_copied_qk_prefs_runs_its_store_script(self):
        skill = self.copy("qk-prefs")
        env = {**os.environ, "QK_PREFS_STATE_DIR": str(Path(self.tmp.name) / "state")}
        for ref in self.referenced_scripts(skill):
            result = self.run_script(skill / ref, "list", env=env)
            self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == "__main__":
    unittest.main()
