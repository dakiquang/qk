import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).resolve().parent.parent / "skills" / "qk-commit" / "scripts" / "qk_preflight.py"
TOKEN_RE = re.compile(r"(ghp_|github_pat_|gho_)[A-Za-z0-9_]{8,}")
if str(SCRIPT.parent) not in sys.path:
    sys.path.insert(0, str(SCRIPT.parent))
import qk_preflight  # noqa: E402


class IdentityCLI(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name)
        self.repo = root / "repo"
        self.repo.mkdir()
        subprocess.run(["git", "init", "-q", str(self.repo)], check=True)
        subprocess.run(["git", "-C", str(self.repo), "config", "user.email", "test@example.invalid"], check=True)
        self.remote("git@github.com:example/repo.git")
        self.bin = root / "bin"
        self.bin.mkdir()
        fake = self.bin / "gh"
        fake.write_text(f"#!{sys.executable}\n" + '''import os
import sys
args = sys.argv[1:]
secret = 'ghp_' + 'A' * 12
if args[:2] == ['api', 'user']:
    print('active-user')
elif args[:2] == ['api', 'repos/example/repo']:
    mode = os.environ['QK_FAKE_PERMISSION']
    if mode == '404':
        print('HTTP 404: Not Found ' + secret, file=sys.stderr)
        sys.exit(1)
    print(mode)
elif args[:2] == ['auth', 'status']:
    print('Logged in to github.com account active-user (' + secret + ')')
    print('Logged in to github.com account other-user', file=sys.stderr)
    print('Logged in to enterprise.example account enterprise-user', file=sys.stderr)
else:
    sys.exit(2)
''')
        fake.chmod(0o755)
        self.env = dict(os.environ, PATH=f"{self.bin}{os.pathsep}{os.environ['PATH']}",
                        QK_FAKE_PERMISSION="true")

    def remote(self, url):
        subprocess.run(["git", "-C", str(self.repo), "remote", "remove", "origin"],
                       capture_output=True)
        if url:
            subprocess.run(["git", "-C", str(self.repo), "remote", "add", "origin", url], check=True)

    def cli(self, mode="true", env=None):
        chosen = dict(self.env if env is None else env, QK_FAKE_PERMISSION=mode)
        done = subprocess.run([sys.executable, "-B", str(SCRIPT), "identity", "--repo", str(self.repo)],
                              env=chosen, capture_output=True, text=True)
        self.assertNotRegex(done.stdout + done.stderr, TOKEN_RE)
        return done

    def test_push_permission_true(self):
        for remote in ("git@github.com:example/repo.git",
                       "https://github.com/example/repo.git",
                       "ssh://git@github.com/example/repo.git"):
            with self.subTest(remote=remote):
                self.remote(remote)
                done = self.cli()
                self.assertEqual(done.returncode, 0, done.stdout)
                self.assertIn("Push permission | true", done.stdout)
                self.assertIn("test@example.invalid", done.stdout)
                if remote.startswith(("git@", "ssh://")):
                    self.assertIn("Push uses your SSH key", done.stdout)
                    self.assertIn("does not verify which account", done.stdout)
                else:
                    self.assertNotIn("SSH origin", done.stdout)

    def test_github_remote_url_variants(self):
        for remote in ("git@GITHUB.COM:example/repo.git",
                       "https://github.com/example/repo.git/"):
            with self.subTest(remote=remote):
                self.remote(remote)
                done = self.cli()
                self.assertEqual(done.returncode, 0, done.stdout)
                self.assertIn("Repository | example/repo", done.stdout)

    def assert_cause_first(self, report, cause):
        lines = report.splitlines()
        self.assertEqual(lines[0], cause)
        self.assertEqual(lines[1:3], ["Field | Value", "--- | ---"])
        self.assertEqual(lines.count(cause), 1)
        rest = "\n".join(lines[1:])
        for expected in ("Repository | example/repo", "Push uses your SSH key", "gh auth switch -u <name>"):
            self.assertIn(expected, rest)

    def test_not_found_names_active_and_other_accounts(self):
        done = self.cli("404")
        self.assertEqual(done.returncode, 1)
        self.assert_cause_first(done.stdout, "Repository is not visible to the active account (404 / Not Found).")
        self.assertIn("Push permission | unavailable", done.stdout)
        self.assertIn("active-user", done.stdout)
        self.assertIn("other-user", done.stdout)
        self.assertNotIn("enterprise-user", done.stdout)

    def test_push_permission_false(self):
        done = self.cli("false")
        self.assertEqual(done.returncode, 1)
        self.assert_cause_first(done.stdout, "The active account does not have push permission.")
        self.assertIn("Push permission | false", done.stdout)

    def test_unconfirmed_permission_leads_with_cause(self):
        done = self.cli("null")
        self.assertEqual(done.returncode, 1)
        self.assert_cause_first(done.stdout, "Could not confirm push permission for the active account.")
        self.assertIn("Push permission | unavailable", done.stdout)

    def test_non_github_and_no_origin(self):
        for remote in ("https://example.invalid/owner/repo.git", None):
            with self.subTest(remote=remote):
                self.remote(remote)
                done = self.cli()
                self.assertEqual(done.returncode, 0)
                self.assertIn("not applicable:", done.stdout)

    def test_gh_missing(self):
        empty_bin = Path(self.tmp.name) / "git-only"
        empty_bin.mkdir()
        (empty_bin / "git").symlink_to(shutil.which("git"))
        done = self.cli(env=dict(self.env, PATH=str(empty_bin)))
        self.assertEqual(done.returncode, 1)
        self.assertIn("gh is not installed", done.stdout)


class IdentityReport(unittest.TestCase):
    def check(self, remote, permission, login="active-user"):
        def git_call(repo, *args, check=True):
            if args[:3] == ("remote", "get-url", "origin"):
                return remote
            if args[:2] == ("config", "user.email"):
                return "test@example.invalid"
            raise AssertionError(args)

        def gh_call(repo, *args, check=True):
            if args[:2] == ("api", "user"):
                return login
            if args[:2] == ("api", "repos/example/repo"):
                return permission
            if args[:2] == ("auth", "status"):
                return "Logged in to github.com account other-user"
            raise AssertionError(args)

        return qk_preflight.check_identity("/unused", gh_call=gh_call, git_call=git_call)

    def test_failing_report_redacts_after_moving_the_cause(self):
        ok, report = self.check("https://github.com/example/repo.git", "false", login="ghp_" + "A" * 12)
        self.assertFalse(ok)
        self.assertEqual(report.splitlines()[0], "The active account does not have push permission.")
        self.assertIn("Active gh account | [redacted]", report)
        self.assertNotRegex(report, TOKEN_RE)

    def test_passing_report_is_the_table(self):
        table = ["Field | Value", "--- | ---", "Repository | example/repo", "Active gh account | active-user",
                 "git user.email | test@example.invalid", "Push permission | true"]
        self.assertEqual(self.check("https://github.com/example/repo.git", "true"), (True, "\n".join(table)))
        ok, report = self.check("git@github.com:example/repo.git", "true")
        self.assertTrue(ok)
        self.assertEqual(report.splitlines(), table + [
            "SSH origin | Push uses your SSH key; this API check does not verify which account that key belongs to."])


if __name__ == "__main__":
    unittest.main()
