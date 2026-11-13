import json
import os
import stat
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "qk_prefs.py"
sys.path.insert(0, str(SCRIPT.parent))
import qk_prefs  # noqa: E402

POSITIVE = [
    "Từ nay commit message viết bằng tiếng Anh nhé",
    "từ giờ dùng pnpm thay cho npm",
    "Từ lần sau đừng tạo file README mới",
    "Lần sau nhớ chạy test trước khi báo xong",
    "Mặc định trả lời bằng tiếng Việt",
    "Ok. Mặc định dùng pnpm",
    "Luôn luôn chạy lint trước khi commit",
    "Lúc nào cũng phải viết test cho bug fix",
    "Đừng bao giờ push thẳng lên main",
    "Không bao giờ được sửa file migration cũ",
    "Ghi nhớ: dự án này dùng Laravel 11",
    "Nhớ là repo này dùng tab, không dùng space",
    "From now on, write commit messages in English",
    "Going forward please use pnpm",
    "By default reply in Vietnamese",
    "Always run the tests before saying done",
    "Never amend a pushed commit",
    "Thanks. Never push to main.",
    "Please always use pnpm",
    "You should never commit .env files",
    "Don't ever force-push",
    "Next time, check the changelog first",
    "Remember that this repo uses tabs",
    "Stop using emoji in commit messages",
]

NEGATIVE = [
    "làm luôn đi",
    "sửa luôn file này",
    "luôn tiện xem log giúp mình",
    "Fix the failing test in auth.ts",
    "Thêm endpoint health-check",
    "never mind, revert that",
    # one-off choices that use words a standing rule would also use
    "This function never returns",
    "Use a dict instead of a list here",
    "Dùng dict thay vì list ở đây",
    "Lần sau mình làm tiếp nhé",
    "Can you always check null here?",
    "Rename it, by default the arg is None",
    "giá trị mặc định là None",
    "I prefer option B for this PR",
    "từ giờ đến tối xong nhé",
    "Next time we will continue",
    "/qk-plan từ nay dùng pnpm",
    "$qk-plan always use pnpm",
    "Why does this fail?\n```\nwhile (always) { never(); }\n```",
    "Rename `alwaysRetry` to `retry`",
    "> from now on use tabs\nwhat does this quote mean?",
    "",
]


def run_hook(stdin, runtime="claude"):
    return subprocess.run(
        [sys.executable, "-I", "-S", str(SCRIPT), "hook", "--runtime", runtime],
        input=stdin,
        capture_output=True,
        text=True,
        timeout=30,
    )


class Detection(unittest.TestCase):
    def test_positive_prompts_match(self):
        for prompt in POSITIVE:
            with self.subTest(prompt=prompt):
                self.assertTrue(qk_prefs.has_cue(prompt))

    def test_negative_prompts_do_not_match(self):
        for prompt in NEGATIVE:
            with self.subTest(prompt=prompt):
                self.assertFalse(qk_prefs.has_cue(prompt))

    def test_decomposed_vietnamese_matches(self):
        import unicodedata

        self.assertTrue(qk_prefs.has_cue(unicodedata.normalize("NFD", "Từ nay dùng pnpm")))

    def test_only_the_start_of_a_long_prompt_is_scanned(self):
        filler = "x" * qk_prefs.MAX_PROMPT
        self.assertTrue(qk_prefs.has_cue("From now on use tabs. " + filler))
        self.assertFalse(qk_prefs.has_cue(filler + " From now on use tabs."))


class Hook(unittest.TestCase):
    def test_match_prints_claude_context(self):
        for runtime in ("claude", "codex"):
            with self.subTest(runtime=runtime):
                done = run_hook(json.dumps({"prompt": "Từ nay dùng pnpm"}), runtime)
                self.assertEqual(done.returncode, 0)
                output = json.loads(done.stdout)["hookSpecificOutput"]
                self.assertEqual(output["hookEventName"], "UserPromptSubmit")
                self.assertIn("propose", output["additionalContext"])
                self.assertIn(str(SCRIPT), output["additionalContext"])

    def test_no_match_prints_nothing(self):
        done = run_hook(json.dumps({"prompt": "làm luôn đi"}))
        self.assertEqual((done.returncode, done.stdout, done.stderr), (0, "", ""))

    def test_oversized_payload_is_ignored(self):
        prompt = "From now on use pnpm. " + "x" * qk_prefs.MAX_STDIN
        done = run_hook(json.dumps({"prompt": prompt}))
        self.assertEqual((done.returncode, done.stdout, done.stderr), (0, "", ""))

    def test_bad_input_is_silent(self):
        for stdin in ("", "not json", "[1, 2]", '{"session_id": "x"}', '{"prompt": 42}'):
            with self.subTest(stdin=stdin):
                done = run_hook(stdin)
                self.assertEqual((done.returncode, done.stdout, done.stderr), (0, "", ""))

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


class Store(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.state = Path(self.tmp.name) / "state"
        self.env = dict(os.environ, QK_PREFS_STATE_DIR=str(self.state))

    def cli(self, *args, check=True):
        done = subprocess.run(
            [sys.executable, str(SCRIPT), *args],
            env=self.env,
            cwd=self.tmp.name,
            capture_output=True,
            text=True,
            timeout=30,
        )
        if check and done.returncode:
            self.fail(f"{args}: {done.stderr}")
        return done

    def propose(self, content="Use pnpm", scope="global", *extra):
        return self.cli(
            "propose", "--scope", scope, "--title", "Package manager",
            "--content", content, "--quote", "từ nay dùng pnpm", *extra,
        ).stdout.strip()

    def listed(self, *args):
        return [json.loads(line) for line in self.cli("list", *args).stdout.splitlines()]

    def test_propose_list_resolve(self):
        first = self.propose()
        second = self.propose("Write commit messages in English", "project", "--project", "qk")
        items = self.listed()
        self.assertEqual([item["id"] for item in items], [first, second])
        self.assertEqual(items[0]["project"], "")
        self.assertEqual(items[1]["project"], "qk")
        self.assertEqual(items[0]["quote"], "từ nay dùng pnpm")

        self.cli("resolve", first, "applied", "--target", "memory")
        self.cli("resolve", second, "dismissed")
        self.assertEqual(self.listed(), [])
        resolved = {item["id"]: item for item in self.listed("--all")}
        self.assertEqual(resolved[first]["status"], "applied")
        self.assertEqual(resolved[first]["target"], "memory")
        self.assertEqual(resolved[second]["status"], "dismissed")
        self.assertIn("resolved", resolved[second])

    def test_propose_from_stdin_json(self):
        payload = {
            "scope": "global",
            "title": "Package manager",
            "content": "Don't use npm; use pnpm.",
            "quote": "từ nay đừng dùng npm, dùng `pnpm` $(whoami)",
        }
        done = subprocess.run(
            [sys.executable, str(SCRIPT), "propose", "--stdin"],
            input=json.dumps(payload, ensure_ascii=False),
            env=self.env, cwd=self.tmp.name, capture_output=True, text=True, timeout=30,
        )
        self.assertEqual(done.returncode, 0, done.stderr)
        item = self.listed()[0]
        self.assertEqual(item["content"], payload["content"])
        self.assertEqual(item["quote"], payload["quote"])

    def test_propose_stdin_rejects_bad_json(self):
        for stdin in ("not json", "[1]", '{"scope": "global", "title": "t", "content": 3}',
                      '{"scope": "global", "title": "t", "content": "c", "extra": "x"}',
                      '{"scope": "team", "title": "t", "content": "c"}'):
            with self.subTest(stdin=stdin):
                done = subprocess.run(
                    [sys.executable, str(SCRIPT), "propose", "--stdin"], input=stdin,
                    env=self.env, cwd=self.tmp.name, capture_output=True, text=True, timeout=30,
                )
                self.assertEqual(done.returncode, 1)
        self.assertFalse((self.state / qk_prefs.STORE_NAME).exists())

    def test_inferred_project_name_is_length_checked(self):
        deep = Path(self.tmp.name) / ("p" * 120)
        deep.mkdir()
        done = subprocess.run(
            [sys.executable, str(SCRIPT), "propose", "--scope", "project", "--title", "t",
             "--content", "c"],
            env=self.env, cwd=deep, capture_output=True, text=True, timeout=30,
        )
        self.assertEqual(done.returncode, 1)
        self.assertIn("project is longer", done.stderr)

    def test_project_scope_defaults_to_cwd_name(self):
        self.propose("Use tabs", "project")
        self.assertEqual(self.listed()[0]["project"], Path(self.tmp.name).name)

    def test_duplicate_pending_returns_existing_id(self):
        first = self.propose()
        self.assertEqual(self.propose("  Use   pnpm "), first)
        self.assertEqual(len(self.listed()), 1)

    def test_resolve_errors(self):
        self.assertEqual(self.cli("resolve", "missing", "applied", check=False).returncode, 1)
        first = self.propose()
        self.cli("resolve", first, "dismissed")
        again = self.cli("resolve", first, "applied", check=False)
        self.assertEqual(again.returncode, 1)
        self.assertIn("already dismissed", again.stderr)

    def test_rejects_empty_and_overlong_fields(self):
        empty = self.cli("propose", "--scope", "global", "--title", " ", "--content", "x", check=False)
        self.assertEqual(empty.returncode, 1)
        long = self.cli(
            "propose", "--scope", "global", "--title", "t", "--content", "x" * 1001, check=False
        )
        self.assertEqual(long.returncode, 1)
        self.assertFalse((self.state / qk_prefs.STORE_NAME).exists())

    def test_store_is_private(self):
        self.propose()
        mode = stat.S_IMODE((self.state / qk_prefs.STORE_NAME).stat().st_mode)
        self.assertEqual(mode, 0o600)
        self.cli("resolve", self.listed()[0]["id"], "applied")
        mode = stat.S_IMODE((self.state / qk_prefs.STORE_NAME).stat().st_mode)
        self.assertEqual(mode, 0o600)

    def test_corrupt_lines_survive_resolve(self):
        first = self.propose()
        store = self.state / qk_prefs.STORE_NAME
        with store.open("a", encoding="utf-8") as handle:
            handle.write("{broken\n")
        self.cli("resolve", first, "applied")
        self.assertIn("{broken", store.read_text(encoding="utf-8"))

    @unittest.skipIf(qk_prefs.file_lock() is None, "no file locking on this platform")
    def test_concurrent_proposals(self):
        code = (
            "import sys; sys.path.insert(0, %r); import qk_prefs\n"
            "for i in range(50):\n"
            "    qk_prefs.main(['propose', '--scope', 'global', '--title', 't',"
            " '--content', '%%s-%%d' %% (sys.argv[1], i)])\n" % str(SCRIPT.parent)
        )
        workers = [
            subprocess.Popen([sys.executable, "-c", code, name], env=self.env,
                             stdout=subprocess.DEVNULL)
            for name in ("a", "b")
        ]
        for worker in workers:
            self.assertEqual(worker.wait(timeout=60), 0)
        lines = (self.state / qk_prefs.STORE_NAME).read_text(encoding="utf-8").splitlines()
        self.assertEqual(len(lines), 100)
        self.assertEqual(len({json.loads(line)["content"] for line in lines}), 100)


if __name__ == "__main__":
    unittest.main()
