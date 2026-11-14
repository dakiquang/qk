import contextlib
import io
import json
import os
import re
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import qk_run  # noqa: E402


def run(cwd, *args):
    return subprocess.run(args, cwd=cwd, check=True, capture_output=True, text=True).stdout.strip()


def result(**fields):
    payload = {"status": "done", "summary": "ok", "files": [], "evidence": [], "findings": []}
    payload.update(fields)
    return f"work\n```qk-result\n{json.dumps(payload)}\n```\n"


PLAN = "# Add greeting\n\n```qk-verify\ntest -f greeting.txt\n```\n"


def planned(text=PLAN):
    return f"<<<QK-PLAN\n{text}QK-PLAN>>>\n" + result()


class Agent:
    """Scripted fake runtime: each stage name maps to a behaviour."""

    def __init__(self, **behaviour):
        self.behaviour = behaviour
        self.calls = []

    def __call__(self, spec, prompt, cwd, write, timeout, extra_dirs, **_):
        if "Independent read-only review" in prompt:
            stage = "review"
        elif "qk-plan" in prompt:
            stage = "plan"
        elif "Fix only the problems" in prompt:
            stage = "fix"
        else:
            stage = "cook"
        self.calls.append((stage, spec, write))
        action = self.behaviour.get(stage, "default")
        if callable(action):
            return action(Path(cwd), Path(extra_dirs[0]))
        if stage == "plan":
            return planned()
        if stage in ("cook", "fix"):
            (Path(cwd) / "greeting.txt").write_text("hello\n")
        return result()


class RunnerTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.remote = root / "remote.git"
        run(root, "git", "init", "-q", "--bare", "-b", "main", str(self.remote))
        seed = self.seed = root / "seed"
        run(root, "git", "clone", "-q", str(self.remote), str(seed))
        self.identity(seed)
        (seed / "README").write_text("seed\n")
        run(seed, "git", "add", "README")
        run(seed, "git", "commit", "-q", "-m", "seed")
        run(seed, "git", "push", "-q", "origin", "HEAD:main")
        self.repo = root / "repo"
        run(root, "git", "clone", "-q", str(self.remote), str(self.repo))
        self.identity(self.repo)
        os.environ["QK_RUN_STATE_DIR"] = str(root / "state")
        os.environ["GIT_AUTHOR_NAME"] = os.environ["GIT_COMMITTER_NAME"] = "qk test"
        os.environ["GIT_AUTHOR_EMAIL"] = os.environ["GIT_COMMITTER_EMAIL"] = "qk@example.invalid"
        self.gh_calls = []
        self.originals = (qk_run.call_agent, qk_run.gh, qk_run.check_identity)
        qk_run.gh = self.fake_gh

    def tearDown(self):
        qk_run.call_agent, qk_run.gh, qk_run.check_identity = self.originals
        self.tmp.cleanup()

    @staticmethod
    def identity(repo):
        run(repo, "git", "config", "user.name", "qk test")
        run(repo, "git", "config", "user.email", "qk@example.invalid")

    def fake_gh(self, cwd, *args, check=True):
        self.gh_calls.append(args)
        if args == ("api", "user", "--jq", ".login"):
            return "active-user"
        if args[:2] == ("api", "repos/example/repo"):
            return "true"
        if args[:2] == ("pr", "create"):
            return "https://github.com/example/repo/pull/7"
        return ""

    def cli(self, *argv):
        with contextlib.redirect_stdout(io.StringIO()):
            return qk_run.main(list(argv))

    def start(self, agent, **kwargs):
        qk_run.call_agent = agent
        self.cli("start", "add a greeting file", "--repo", str(self.repo), *kwargs.get("extra", []))
        return self.latest()

    def latest(self):
        runs = sorted(Path(os.environ["QK_RUN_STATE_DIR"]).iterdir())
        return json.loads((runs[-1] / "state.json").read_text())

    def remote_branches(self):
        return run(self.repo, "git", "ls-remote", "--heads", "origin")

    def push_history(self, *subjects):
        for subject in subjects:
            run(self.seed, "git", "commit", "--allow-empty", "-q", "-m", subject)
        run(self.seed, "git", "push", "-q", "origin", "HEAD:main")

    def push_merged(self, *subjects):
        for n, subject in enumerate(subjects, 1):
            run(self.seed, "git", "checkout", "-q", "-b", f"topic-{n}")
            run(self.seed, "git", "commit", "--allow-empty", "-q", "-m", subject)
            run(self.seed, "git", "checkout", "-q", "-")
            run(self.seed, "git", "merge", "-q", "--no-ff", "--no-edit",
                "-m", f"Merge pull request #{n} from example/topic-{n}", f"topic-{n}")
        run(self.seed, "git", "push", "-q", "origin", "HEAD:main")

    def published_titles(self):
        state = self.latest()
        self.assertEqual(state["stage"], "done")
        commit = run(Path(state["worktree"]), "git", "log", "-1", "--format=%B")
        creates = [c for c in self.gh_calls if c[:2] == ("pr", "create")]
        self.assertEqual(len(creates), 1)
        return commit, creates[0][creates[0].index("--title") + 1]

    def test_full_run_stops_at_plan_then_opens_one_pr(self):
        state = self.start(Agent())
        self.assertEqual(state["stage"], "awaiting_approval")
        self.assertNotIn("qk/", self.remote_branches())
        self.cli("approve", state["id"])
        state = self.latest()
        self.assertEqual(state["stage"], "done")
        self.assertEqual(state["pr_url"], "https://github.com/example/repo/pull/7")
        self.assertIn(state["branch"], self.remote_branches())
        log = run(Path(state["worktree"]), "git", "log", "-1", "--format=%B")
        self.assertEqual(log.strip(), "Add greeting")
        self.assertEqual(run(self.repo, "git", "status", "--porcelain"), "")
        creates = [c for c in self.gh_calls if c[:2] == ("pr", "create")]
        self.assertEqual(len(creates), 1)
        self.assertNotIn("--draft", creates[0])
        self.assertEqual(creates[0][creates[0].index("--title") + 1], "Add greeting")

    def test_conventional_history_types_commit_and_pr_title(self):
        self.push_history("feat: a", "fix(x): b", "docs!: c")
        state = self.start(Agent())
        self.cli("approve", state["id"])
        self.assertEqual(self.published_titles(), ("feat: add greeting", "feat: add greeting"))

    def test_only_the_last_20_subjects_decide_the_convention(self):
        self.push_history(*[f"feat: old {i}" for i in range(15)], *[f"Plain {i}" for i in range(11)],
                          *[f"fix: new {i}" for i in range(9)])
        state = self.start(Agent())
        self.cli("approve", state["id"])
        self.assertEqual(self.published_titles(), ("Add greeting", "Add greeting"))

    def test_merge_commits_do_not_count_toward_the_convention(self):
        self.push_merged("feat: a", "fix: b", "docs: c")
        state = self.start(Agent())
        self.cli("approve", state["id"])
        self.assertEqual(self.published_titles(), ("feat: add greeting", "feat: add greeting"))

    def test_conventional_title_rules(self):
        half = ["feat: x"] * 10 + ["plain"] * 10
        most = ["feat: x"] * 11 + ["plain"] * 9
        self.assertEqual(qk_run.conventional_title("Add greeting", half), "Add greeting")
        self.assertEqual(qk_run.conventional_title("Add greeting", most), "feat: add greeting")
        cases = {"Fix crash on resume": "fix: fix crash on resume",
                 "Document runner": "docs: document runner",
                 "A greeting": "feat: a greeting",
                 "README badges": "feat: README badges",
                 "CI cache for tests": "feat: CI cache for tests",
                 "E2E runner tests": "feat: E2E runner tests",
                 "fix(runner): keep title": "fix(runner): keep title"}
        for title, expected in cases.items():
            self.assertEqual(qk_run.conventional_title(title, most), expected, title)
        self.assertEqual(qk_run.conventional_title("Add greeting", []), "Add greeting")
        self.assertLessEqual(len(qk_run.conventional_title("Add " + "x" * 68, most)), 72)

    def test_titles_cut_at_word_boundary_and_drop_foreign_prefix(self):
        half = ["feat: x"] * 10 + ["plain"] * 10
        most = ["feat: x"] * 11 + ["plain"] * 9
        regression = "waf-upgrade-check: `versions` and `diff` commands (project plan step 3)"
        self.assertEqual(qk_run.conventional_title(regression, most),
                         "feat: `versions` and `diff` commands (project plan step 3)")
        self.assertEqual(qk_run.conventional_title(regression, half), regression)
        self.assertLessEqual(len(regression), 72)
        full = "feat: add " + "word " * 20
        typed = qk_run.conventional_title("Add " + "word " * 20, most)
        self.assertLessEqual(len(typed), 72)
        self.assertTrue(typed.endswith("word"), typed)
        self.assertTrue(full.startswith(typed), typed)
        long_title = "Stream agent progress and stop timed-out agents cleanly in the runner loop"
        self.assertGreater(len(long_title), 72)
        clipped = qk_run.clip_title(long_title)
        self.assertLessEqual(len(clipped), 72)
        self.assertEqual(long_title[len(clipped)], " ")
        self.assertTrue(long_title.startswith(clipped))

    def test_verification_artifacts_are_not_committed(self):
        def plan(cwd, state_dir):
            return planned("# Add greeting\n\n```qk-verify\nmkdir -p cache && touch cache/a.tmp && test -f greeting.txt\n```\n")
        state = self.start(Agent(plan=plan))
        self.cli("approve", state["id"])
        state = self.latest()
        self.assertEqual(state["stage"], "done")
        files = run(Path(state["worktree"]), "git", "show", "--name-only", "--format=", "HEAD").split()
        self.assertEqual(files, ["greeting.txt"])

    def test_verification_editing_tracked_files_blocks(self):
        def plan(cwd, state_dir):
            return planned("# Add greeting\n\n```qk-verify\necho changed >> README\n```\n")
        state = self.start(Agent(plan=plan))
        self.cli("approve", state["id"])
        state = self.latest()
        self.assertEqual(state["stage"], "blocked")
        self.assertIn("modified the worktree", state["reason"])

    def test_verification_deleting_a_new_file_blocks(self):
        def plan(cwd, state_dir):
            return planned("# Add greeting\n\n```qk-verify\nrm greeting.txt\n```\n")
        state = self.start(Agent(plan=plan))
        self.cli("approve", state["id"])
        state = self.latest()
        self.assertEqual(state["stage"], "blocked")
        self.assertIn("modified the worktree", state["reason"])
        self.cli("resume", state["id"])
        self.assertEqual(self.latest()["stage"], "blocked")
        self.assertNotIn(state["branch"], self.remote_branches())

    def test_persistent_verification_failure_blocks_after_one_fix_without_publishing(self):
        def cook(cwd, state_dir):
            (cwd / "other.txt").write_text("wrong\n")
            return result()
        agent = Agent(cook=cook, fix=cook)
        state = self.start(agent)
        self.cli("approve", state["id"])
        state = self.latest()
        self.assertEqual(state["stage"], "blocked")
        self.assertEqual(state["blocked_at"], "verifying")
        self.assertEqual(state["fix_rounds"], 1)
        self.assertEqual([c[0] for c in agent.calls].count("fix"), 1)
        self.assertNotIn(state["branch"], self.remote_branches())
        self.assertFalse(self.gh_calls[1:])

    def test_one_failed_verification_is_fixed_then_published(self):
        def cook(cwd, state_dir):
            (cwd / "other.txt").write_text("wip\n")
            return result()
        state = self.start(Agent(cook=cook))
        self.cli("approve", state["id"])
        state = self.latest()
        self.assertEqual(state["stage"], "done")
        self.assertEqual(state["fix_rounds"], 1)

    def test_agent_commit_is_blocked(self):
        def cook(cwd, state_dir):
            (cwd / "greeting.txt").write_text("hello\n")
            run(cwd, "git", "add", "-A")
            run(cwd, "git", "commit", "-q", "-m", "sneaky")
            return result()
        state = self.start(Agent(cook=cook))
        self.cli("approve", state["id"])
        state = self.latest()
        self.assertEqual(state["stage"], "blocked")
        self.assertIn("HEAD", state["reason"])
        self.assertNotIn(state["branch"], self.remote_branches())

    def test_resume_after_agent_commit_stays_blocked(self):
        def cook(cwd, state_dir):
            (cwd / "greeting.txt").write_text("hello\n")
            run(cwd, "git", "add", "-A")
            run(cwd, "git", "commit", "-q", "-m", "sneaky")
            (cwd / "extra.txt").write_text("more\n")
            return result()
        state = self.start(Agent(cook=cook))
        self.cli("approve", state["id"])
        self.cli("resume", state["id"])
        state = self.latest()
        self.assertEqual(state["stage"], "blocked")
        self.assertIn("HEAD", state["reason"])
        self.assertNotIn(state["branch"], self.remote_branches())

    def test_agent_commit_before_failing_is_still_reported(self):
        def cook(cwd, state_dir):
            (cwd / "greeting.txt").write_text("hello\n")
            run(cwd, "git", "add", "-A")
            run(cwd, "git", "commit", "-q", "-m", "sneaky")
            raise qk_run.Blocked("omp exited 1: crashed")
        state = self.start(Agent(cook=cook))
        self.cli("approve", state["id"])
        self.assertIn("HEAD", self.latest()["reason"])

    def test_agent_branch_switch_at_same_commit_is_blocked(self):
        def cook(cwd, state_dir):
            run(cwd, "git", "switch", "-q", "-c", "elsewhere")
            (cwd / "greeting.txt").write_text("hello\n")
            return result()
        state = self.start(Agent(cook=cook))
        self.cli("approve", state["id"])
        state = self.latest()
        self.assertEqual(state["stage"], "blocked")
        self.assertIn("elsewhere", state["reason"])

    def test_agent_commit_in_clean_primary_checkout_is_blocked(self):
        def cook(cwd, state_dir):
            (self.repo / "touched.txt").write_text("x\n")
            run(self.repo, "git", "add", "-A")
            run(self.repo, "git", "commit", "-q", "-m", "agent wrote here")
            (cwd / "greeting.txt").write_text("hello\n")
            return result()
        state = self.start(Agent(cook=cook))
        self.cli("approve", state["id"])
        state = self.latest()
        self.assertEqual(state["stage"], "blocked")
        self.assertIn("primary checkout", state["reason"])

    def test_review_finding_triggers_single_fix(self):
        reviews = iter([
            result(findings=[{"severity": "important", "file": "greeting.txt", "line": 1, "claim": "x", "fix": "y"}]),
            result(),
        ])
        agent = Agent(review=lambda cwd, state_dir: next(reviews))
        state = self.start(agent)
        self.cli("approve", state["id"])
        state = self.latest()
        self.assertEqual(state["stage"], "done")
        self.assertEqual([c[0] for c in agent.calls].count("fix"), 1)
        review_writes = [c[2] for c in agent.calls if c[0] == "review"]
        self.assertEqual(review_writes, [False, False])

    def test_second_review_with_serious_finding_blocks_without_publishing(self):
        finding = {"severity": "blocker", "file": "greeting.txt", "line": 1, "claim": "x", "fix": "y"}
        agent = Agent(review=lambda cwd, state_dir: result(findings=[finding]))
        state = self.start(agent)
        self.cli("approve", state["id"])
        state = self.latest()
        self.assertEqual(state["stage"], "blocked")
        self.assertEqual(state["blocked_at"], "reviewing")
        self.assertEqual(state["fix_rounds"], 1)
        self.assertNotIn(state["branch"], self.remote_branches())

    def test_finding_paths_and_severity_are_normalised(self):
        reviews = iter([
            result(findings=[{"severity": "Important", "file": "./greeting.txt", "line": 1, "claim": "x", "fix": "y"}]),
            result(),
        ])
        agent = Agent(review=lambda cwd, state_dir: next(reviews))
        state = self.start(agent)
        self.cli("approve", state["id"])
        self.assertEqual([c[0] for c in agent.calls].count("fix"), 1)
        body = (Path(os.environ["QK_RUN_STATE_DIR"]) / state["id"] / "pr-body.md").read_text()
        self.assertIn("[important] greeting.txt:1 x", body)

    def test_finding_outside_diff_does_not_trigger_fix(self):
        review = lambda cwd, state_dir: result(findings=[{"severity": "blocker", "file": "README", "line": 1}])
        agent = Agent(review=review)
        state = self.start(agent)
        self.cli("approve", state["id"])
        self.assertEqual(self.latest()["stage"], "done")
        self.assertNotIn("fix", [c[0] for c in agent.calls])

    def test_reviewer_editing_files_is_blocked(self):
        def review(cwd, state_dir):
            (cwd / "greeting.txt").write_text("changed by reviewer\n")
            return result()
        state = self.start(Agent(review=review))
        self.cli("approve", state["id"])
        state = self.latest()
        self.assertEqual(state["stage"], "blocked")
        self.assertIn("read-only agent", state["reason"])

    def test_resume_after_reviewer_edit_stays_blocked(self):
        def review(cwd, state_dir):
            (cwd / "greeting.txt").write_text("changed by reviewer\n")
            return result()
        state = self.start(Agent(review=review))
        self.cli("approve", state["id"])
        self.cli("resume", state["id"])
        state = self.latest()
        self.assertEqual(state["stage"], "blocked")
        self.assertIn("read-only stage expects", state["reason"])
        self.assertNotIn(state["branch"], self.remote_branches())

    def test_plan_without_verify_block_cannot_be_approved(self):
        def plan(cwd, state_dir):
            return planned("# No checks\n")
        state = self.start(Agent(plan=plan))
        self.assertEqual(state["stage"], "blocked")
        self.assertIn("qk-verify", state["reason"])

    def test_planner_editing_repo_is_blocked(self):
        def plan(cwd, state_dir):
            (cwd / "notes.txt").write_text("scratch\n")
            return planned()
        state = self.start(Agent(plan=plan))
        self.assertEqual(state["stage"], "blocked")
        self.assertEqual(state["blocked_at"], "planning")

    def test_missing_result_block_blocks(self):
        state = self.start(Agent(plan=lambda cwd, state_dir: "I am done!"))
        self.assertEqual(state["stage"], "blocked")
        self.assertIn("qk-result", state["reason"])

    def test_dirty_primary_checkout_is_refused_without_stash(self):
        (self.repo / "local.txt").write_text("user work\n")
        state = self.start(Agent())
        self.assertEqual(state["stage"], "blocked")
        self.assertEqual(state["blocked_at"], "preflight")
        self.assertTrue((self.repo / "local.txt").is_file())
        self.assertEqual(run(self.repo, "git", "stash", "list"), "")

    def test_identity_failure_blocks_before_worktree(self):
        run(self.repo, "git", "remote", "set-url", "origin", "git@github.com:example/repo.git")

        def denied_gh(cwd, *args, check=True):
            if args[:2] == ("api", "repos/example/repo"):
                return "false"
            if args[:2] == ("auth", "status"):
                return "Logged in to github.com account active-user\nLogged in to github.com account other-user"
            return self.fake_gh(cwd, *args, check=check)

        qk_run.gh = denied_gh
        state = self.start(Agent())
        self.assertEqual(state["stage"], "blocked")
        self.assertEqual(state["blocked_at"], "preflight")
        self.assertIn("Push permission | false", state["reason"])
        self.assertIn("other-user", state["reason"])
        self.assertNotIn("worktree", state)
        self.assertEqual(run(self.repo, "git", "worktree", "list", "--porcelain").count("worktree "), 1)

    def test_identity_failure_at_publishing_prevents_push(self):
        checks = []

        def changing_identity(repo, gh_call=None, git_call=None):
            checks.append(Path(repo))
            return (True, "preflight passed") if len(checks) == 1 else (False, "publishing identity denied")

        qk_run.check_identity = changing_identity
        state = self.start(Agent())
        self.cli("approve", state["id"])
        blocked = self.latest()
        self.assertEqual(blocked["stage"], "blocked")
        self.assertEqual(blocked["blocked_at"], "publishing")
        self.assertEqual(blocked["reason"], "publishing identity denied")
        self.assertEqual([path.resolve() for path in checks],
                         [self.repo.resolve(), Path(blocked["worktree"]).resolve()])
        self.assertNotIn(blocked["branch"], self.remote_branches())

    def test_hidden_repository_blocks_with_identity_report(self):
        run(self.repo, "git", "remote", "set-url", "origin", "git@github.com:example/repo.git")

        def hidden_gh(cwd, *args, check=True):
            if args[:2] == ("api", "repos/example/repo"):
                raise qk_run.Blocked("gh api repos/example/repo failed (1): gh: Not Found (HTTP 404)")
            if args[:2] == ("auth", "status"):
                return "Logged in to github.com account active-user\nLogged in to github.com account other-user"
            return self.fake_gh(cwd, *args, check=check)

        qk_run.gh = hidden_gh
        state = self.start(Agent())
        self.assertEqual(state["stage"], "blocked")
        self.assertIn("not visible to the active account", state["reason"])
        self.assertIn("other-user", state["reason"])
        self.assertNotIn("worktree", state)

    def test_same_model_family_is_rejected(self):
        qk_run.call_agent = Agent()
        with self.assertRaises(SystemExit):
            self.cli("start", "task", "--repo", str(self.repo), "--impl", "claude:opus",
                     "--review", "omp:anthropic/claude-opus-5-5")

    def test_family_check_fails_closed(self):
        for spec in ("omp:", "omp:mystery-model"):
            with self.assertRaises(SystemExit):
                qk_run.family(spec)
        self.assertEqual(qk_run.family("omp:opus"), qk_run.family("claude:"))
        self.assertEqual(qk_run.family("omp:openai-codex/gpt-6.1-sol"), qk_run.family("codex:"))
        self.assertEqual(qk_run.family("omp:google-antigravity/claude-sonnet-4-6"), "anthropic")
        self.assertNotEqual(qk_run.family(qk_run.DEFAULT_IMPL), qk_run.family(qk_run.DEFAULT_REVIEW))
        self.assertEqual(qk_run.family("codex:openrouter/anthropic/claude-sonnet-x"), "anthropic")

    def test_fixer_updating_the_plan_status_still_publishes(self):
        def cook(cwd, state_dir):
            (cwd / "other.txt").write_text("wip\n")
            return result()

        def fix(cwd, state_dir):
            (cwd / "greeting.txt").write_text("hello\n")
            plan = state_dir / "plan.md"
            plan.write_text(plan.read_text().replace("# Add greeting", "# Add greeting (done)"))
            return result()
        state = self.start(Agent(cook=cook, fix=fix))
        self.cli("approve", state["id"])
        state = self.latest()
        self.assertEqual(state["stage"], "done")
        self.assertEqual(state["fix_rounds"], 1)

    def test_existing_branch_is_refused(self):
        original = qk_run.secrets.token_hex
        qk_run.secrets.token_hex = lambda n: "abc123"
        try:
            run(self.repo, "git", "branch", "qk/add-a-greeting-file-abc123")
            state = self.start(Agent())
        finally:
            qk_run.secrets.token_hex = original
        self.assertEqual(state["stage"], "blocked")
        self.assertEqual(state["blocked_at"], "preflight")
        self.assertIn("already exists", state["reason"])

    def test_approve_uses_the_edited_plan_and_freezes_it(self):
        def cook(cwd, state_dir):
            (cwd / "greeting.txt").write_text("hello\n")
            (state_dir / "plan.md").write_text("# Rewritten by agent\n")
            return result()
        state = self.start(Agent(cook=cook))
        plan = Path(os.environ["QK_RUN_STATE_DIR"]) / state["id"] / "plan.md"
        plan.write_text("# Add greeting\n\n```qk-verify\ntest -f greeting.txt\ntest -f README\n```\n")
        self.cli("approve", state["id"])
        state = self.latest()
        self.assertEqual(state["stage"], "done")
        self.assertEqual(state["verify"], ["test -f greeting.txt", "test -f README"])
        body = (plan.parent / "pr-body.md").read_text()
        self.assertIn("test -f README", body)
        self.assertNotIn("Rewritten by agent", body)

    def test_editing_the_approved_plan_blocks(self):
        def cook(cwd, state_dir):
            (cwd / "greeting.txt").write_text("hello\n")
            (state_dir / "approved-plan.md").write_text("# Widened scope\n")
            return result()
        state = self.start(Agent(cook=cook))
        self.cli("approve", state["id"])
        state = self.latest()
        self.assertEqual(state["stage"], "blocked")
        self.assertIn("approved-plan.md", state["reason"])

    def test_existing_pr_is_reused(self):
        def gh_with_pr(cwd, *args, check=True):
            self.gh_calls.append(args)
            if args[:2] == ("pr", "list"):
                return "https://github.com/example/repo/pull/3"
            return ""
        qk_run.gh = gh_with_pr
        state = self.start(Agent())
        self.cli("approve", state["id"])
        state = self.latest()
        self.assertEqual(state["pr_url"], "https://github.com/example/repo/pull/3")
        self.assertFalse([c for c in self.gh_calls if c[:2] == ("pr", "create")])

    def test_resume_after_push_does_not_recommit_or_repush(self):
        state = self.start(Agent())
        calls = {"n": 0}

        def flaky_gh(cwd, *args, check=True):
            if args[:2] == ("pr", "create"):
                calls["n"] += 1
                if calls["n"] == 1:
                    raise qk_run.Blocked("network down")
            return self.fake_gh(cwd, *args)
        qk_run.gh = flaky_gh
        self.cli("approve", state["id"])
        blocked = self.latest()
        self.assertEqual(blocked["stage"], "blocked")
        self.assertEqual(blocked["blocked_at"], "publishing")
        qk_run.check_identity = lambda *args, **kwargs: self.fail("identity rechecked after push")
        self.cli("resume", state["id"])
        done = self.latest()
        self.assertEqual(done["stage"], "done")
        self.assertEqual(done["commit"], blocked["commit"])
        count = run(Path(done["worktree"]), "git", "rev-list", "--count", f"{done['base_sha']}..HEAD")
        self.assertEqual(count, "1")

    def test_revise_replans_with_feedback(self):
        agent = Agent()
        state = self.start(agent)
        self.cli("revise", state["id"], "keep it smaller")
        self.assertEqual(self.latest()["stage"], "awaiting_approval")
        self.assertEqual([c[0] for c in agent.calls], ["plan", "plan"])
        self.assertEqual([c[2] for c in agent.calls], [False, False])


FIXTURES = Path(__file__).resolve().parent / "fixtures" / "agent-streams"


class AgentStreamTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        self.originals = (qk_run.agent_command, qk_run.HEARTBEAT_SECONDS, qk_run.KILL_GRACE_SECONDS)
        self.progress = []

    def tearDown(self):
        qk_run.agent_command, qk_run.HEARTBEAT_SECONDS, qk_run.KILL_GRACE_SECONDS = self.originals
        self.tmp.cleanup()

    def fake_agent(self, script, *args):
        qk_run.agent_command = lambda spec, write, cwd, extra_dirs: ([sys.executable, "-c", script, *args], None)

    def call(self, timeout=30):
        return qk_run.call_agent("omp:anthropic/x", "prompt", self.dir, True, timeout, [self.dir],
                                 events=self.dir / "events.jsonl", progress=self.progress.append)

    def test_event_parsers_match_captured_streams(self):
        expected = {"claude": ["read /work/a.txt", "run ls"],
                    "codex": ["run /bin/zsh -lc 'cat a.txt'", "run /bin/zsh -lc 'cat a.txt' -> exit 0"],
                    "omp": ["read a.txt", "run ls"]}
        for runtime, displays in expected.items():
            shown, final = [], None
            for line in (FIXTURES / f"{runtime}.jsonl").read_text(encoding="utf-8").splitlines():
                display, text = qk_run.EVENT_PARSERS[runtime](json.loads(line))
                if display:
                    shown.append(display)
                if text is not None:
                    final = text
            self.assertEqual(shown, displays, runtime)
            self.assertEqual(final, "DONE", runtime)

    def test_event_parsers_skip_unhashable_tool_names(self):
        events = {"claude": {"type": "assistant", "message": {"content": [
                      {"type": "tool_use", "name": ["Read"], "input": {"file_path": "x"}}]}},
                  "omp": {"type": "tool_execution_start", "toolName": {"read": 1}, "args": {"path": "x"}}}
        for runtime, event in events.items():
            self.assertEqual(qk_run.EVENT_PARSERS[runtime](event), (None, None), runtime)

    def test_heartbeat_reports_quiet_agent(self):
        qk_run.HEARTBEAT_SECONDS = 0.2
        lines = (FIXTURES / "omp.jsonl").read_text(encoding="utf-8").splitlines()
        read_event, end_event = lines[0], lines[3]
        self.fake_agent("import sys, time\n"
                        "time.sleep(0.5)\n"
                        "print('not json', flush=True)\n"
                        f"print({read_event!r}, flush=True)\n"
                        "time.sleep(0.5)\n"
                        f"print({end_event!r}, flush=True)\n")
        self.assertEqual(self.call(), "DONE")
        self.assertIn("read a.txt", self.progress)
        for last in ("no action yet", "read a.txt"):
            pattern = re.compile(rf"still running \(\d+s, last: {last}\)")
            self.assertTrue(any(pattern.fullmatch(line) for line in self.progress), self.progress)
        self.assertEqual((self.dir / "events.jsonl").read_text(encoding="utf-8").splitlines(),
                         [read_event, end_event])

    def test_line_after_heartbeat_deadline_prints_heartbeat_and_continues(self):
        qk_run.HEARTBEAT_SECONDS = 0.2
        lines = (FIXTURES / "omp.jsonl").read_text(encoding="utf-8").splitlines()
        read_event, end_event = lines[0], lines[3]
        self.fake_agent("import sys, time\n"
                        f"print({read_event!r}, flush=True)\n"
                        "time.sleep(0.3)\n"
                        "print('not json', flush=True)\n"
                        f"print({end_event!r}, flush=True)\n")

        def slow_progress(message):
            self.progress.append(message)
            if message == "read a.txt":
                time.sleep(0.4)

        result = qk_run.call_agent("omp:anthropic/x", "prompt", self.dir, True, 30, [self.dir],
                                   events=self.dir / "events.jsonl", progress=slow_progress)
        self.assertEqual(result, "DONE")
        pattern = re.compile(r"still running \(\d+s, last: read a\.txt\)")
        self.assertTrue(any(pattern.fullmatch(line) for line in self.progress), self.progress)
        self.assertEqual((self.dir / "events.jsonl").read_text(encoding="utf-8").splitlines(),
                         [read_event, end_event])

    def test_timeout_stops_agent_process_group(self):
        qk_run.KILL_GRACE_SECONDS = 0.5
        pid_file = self.dir / "grandchild.pid"
        self.fake_agent("import signal, subprocess, sys, time\n"
                        "signal.signal(signal.SIGTERM, signal.SIG_IGN)\n"
                        "child = subprocess.Popen(['sleep', '60'])\n"
                        "open(sys.argv[1], 'w').write(str(child.pid))\n"
                        "time.sleep(60)\n", str(pid_file))
        started = time.monotonic()
        with self.assertRaises(qk_run.Blocked) as caught:
            self.call(timeout=1)
        self.assertEqual(str(caught.exception), "omp:anthropic/x timed out after 1s; agent stopped")
        pid = int(pid_file.read_text())
        gone = False
        while time.monotonic() - started < 4.5 and not gone:
            try:
                os.kill(pid, 0)
                time.sleep(0.05)
            except ProcessLookupError:
                gone = True
        self.assertTrue(gone, "grandchild survived the timeout")
        self.assertLess(time.monotonic() - started, 5)


if __name__ == "__main__":
    unittest.main()
