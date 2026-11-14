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
            out = action(Path(cwd), Path(extra_dirs[0]))
            return out if isinstance(out, tuple) else (out, None)
        if stage == "plan":
            return planned(), None
        if stage in ("cook", "fix"):
            (Path(cwd) / "greeting.txt").write_text("hello\n")
        return result(), None


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

    def test_turns_in_the_same_second_keep_separate_records(self):
        from unittest import mock
        finding = {"severity": "blocker", "file": "greeting.txt", "line": 1, "claim": "x", "fix": "y"}
        agent = Agent(review=lambda cwd, state_dir: result(findings=[finding]))
        with mock.patch.object(qk_run.time, "time", return_value=1_800_000_000.0):
            state = self.start(agent)
            self.cli("approve", state["id"])
        outs = list(qk_run.run_dir(state["id"]).glob("*.out.md"))
        self.assertEqual([c[0] for c in agent.calls].count("review"), 2)
        self.assertEqual(len(outs), len(agent.calls), sorted(p.name for p in outs))

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

    def test_long_foreign_prefix_is_dropped_before_clipping(self):
        most = ["feat: a", "fix: b", "docs: c"]
        title = "some-very-long-project-name-prefix: Add streaming of agent progress to the runner loop"
        self.assertGreater(len(title), 72)
        self.push_history(*most)
        plan = f"# {title}\n\n```qk-verify\ntest -f greeting.txt\n```\n"
        state = self.start(Agent(plan=lambda cwd, state_dir: planned(plan)))
        self.cli("approve", state["id"])
        expected = "feat: add streaming of agent progress to the runner loop"
        self.assertEqual(self.published_titles(), (expected, expected))

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
        (Path(self.latest()["worktree"]) / "notes.txt").write_text("hand fix\n")
        self.cli("resume", state["id"])
        state = self.latest()
        self.assertEqual(state["stage"], "blocked")
        self.assertIn("read-only stage expects", state["reason"])
        self.assertNotIn(state["branch"], self.remote_branches())

    def test_resume_after_hand_fix_verifies_and_publishes(self):
        finding = {"severity": "blocker", "file": "greeting.txt", "line": 1, "claim": "x", "fix": "y"}
        serious = {"on": True}
        agent = Agent(review=lambda cwd, state_dir: result(findings=[finding] if serious["on"] else []))
        state = self.start(agent)
        self.cli("approve", state["id"])
        blocked = self.latest()
        self.assertEqual(blocked["blocked_at"], "reviewing")
        worktree = Path(blocked["worktree"])
        (worktree / "greeting.txt").write_text("hello, fixed by hand\n")
        (worktree / "notes.txt").write_text("why\n")
        serious["on"] = False
        self.cli("resume", state["id"])
        self.assertEqual(self.latest()["stage"], "done")
        self.assertEqual([c[0] for c in agent.calls].count("fix"), 1)
        run_log = (qk_run.run_dir(state["id"]) / "run.log").read_text()
        recorded = run_log.index("manual changes recorded: greeting.txt, notes.txt")
        self.assertIn("$ test -f greeting.txt", run_log[recorded:])
        files = run(worktree, "git", "show", "--name-only", "--format=", "HEAD").split()
        self.assertEqual(sorted(files), ["greeting.txt", "notes.txt"])

    def test_agent_usage_is_stored_per_stage(self):
        usage = {"input": 100, "cached": 40, "output": 7}
        state = self.start(Agent(review=lambda cwd, state_dir: (result(), dict(usage))))
        self.cli("approve", state["id"])
        state = self.latest()
        self.assertEqual(state["stage"], "done")
        self.assertEqual(state["usage"], {"reviewing": [{"spec": "codex:", **usage}]})

    def test_read_only_mcp_is_refused_when_codex_runs_a_read_only_stage(self):
        qk_run.call_agent = Agent()
        for roles in ([], ["--impl", "codex:", "--review", "claude:"]):
            with self.assertRaises(SystemExit) as caught:
                self.cli("start", "task", "--repo", str(self.repo), "--read-only-mcp", "aws-mcp", *roles)
            self.assertIn("not supported for codex", str(caught.exception.code))
        with self.assertRaises(SystemExit) as caught:
            self.cli("start", "task", "--repo", str(self.repo), "--read-only-mcp", "",
                     "--review", "omp:openai-codex/gpt-6.1-sol")
        self.assertIn("needs a server name", str(caught.exception.code))
        state = self.start(Agent(), extra=["--read-only-mcp", "aws-mcp", "--review", "omp:openai-codex/gpt-6.1-sol"])
        self.assertEqual(state["stage"], "awaiting_approval")
        self.assertEqual(state["read_only_mcp"], ["aws-mcp"])

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
        qk_run.agent_command = (lambda spec, write, cwd, extra_dirs, read_only_mcp=():
                                ([sys.executable, "-c", script, *args], None, None))

    def call(self, timeout=30, spec="omp:anthropic/x", write=True, read_only_mcp=()):
        return qk_run.call_agent(spec, "prompt", self.dir, write, timeout, [self.dir],
                                 events=self.dir / "events.jsonl", progress=self.progress.append,
                                 read_only_mcp=read_only_mcp)

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

    def test_omp_tool_only_message_keeps_earlier_final_text(self):
        omp = qk_run.EVENT_PARSERS["omp"]
        self.assertEqual(omp({"type": "message_end", "message": {"role": "assistant", "content": [
            {"type": "toolCall", "name": "read", "arguments": {"path": "a"}}]}}), (None, None))
        self.assertEqual(omp({"type": "message_end", "message": {"role": "assistant"}}), (None, None))

    def test_display_root_is_replaced_only_as_a_whole_segment(self):
        qk_run.DISPLAY_ROOTS[:] = [("/w/tree", "")]
        self.addCleanup(qk_run.DISPLAY_ROOTS.clear)
        run = qk_run.EVENT_PARSERS["omp"]
        self.assertEqual(run({"type": "tool_execution_start", "toolName": "read",
                              "args": {"path": "/w/tree-old/x"}})[0], "read /w/tree-old/x")
        self.assertEqual(run({"type": "tool_execution_start", "toolName": "bash",
                              "args": {"command": "cd /w/tree && ls /w/tree/src"}})[0], "run cd . && ls src")

    def test_display_paths_are_relative_to_the_worktree(self):
        qk_run.DISPLAY_ROOTS[:] = [("/w/tree", ""), ("/u/me", "~/")]
        self.addCleanup(qk_run.DISPLAY_ROOTS.clear)
        omp = qk_run.EVENT_PARSERS["omp"]
        self.assertEqual(omp({"type": "tool_execution_start", "toolName": "read",
                              "args": {"path": "/w/tree/src/a.py"}})[0], "read src/a.py")
        self.assertEqual(omp({"type": "tool_execution_start", "toolName": "read",
                              "args": {"path": "/w/tree"}})[0], "read .")
        self.assertEqual(omp({"type": "tool_execution_start", "toolName": "read",
                              "args": {"path": "/u/me/x/y.md"}})[0], "read ~/x/y.md")

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
        self.assertEqual(self.call()[0], "DONE")
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

        result, _ = qk_run.call_agent("omp:anthropic/x", "prompt", self.dir, True, 30, [self.dir],
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

    def test_agent_command_isolates_skills_and_read_only_mcp(self):
        def command(spec, write, read_only_mcp=()):
            return qk_run.agent_command(spec, write, self.dir, [self.dir], read_only_mcp)
        claude_read, _, env = command("claude:", False)
        self.assertIsNone(env)
        self.assertIn("--disable-slash-commands", claude_read)
        self.assertIn("--strict-mcp-config", claude_read)
        self.assertNotIn("--strict-mcp-config", command("claude:", False, ["aws-mcp"])[0])
        claude_write = command("claude:", True)[0]
        self.assertIn("--disable-slash-commands", claude_write)
        self.assertNotIn("--strict-mcp-config", claude_write)
        for write in (False, True):
            omp, _, env = command("omp:anthropic/x", write)
            self.assertIsNone(env)
            for flag in ("--no-skills", "--no-extensions", "--no-rules"):
                self.assertIn(flag, omp, (flag, write))

    def test_codex_runs_in_a_private_home_reused_across_calls(self):
        from unittest import mock
        real_home, real_codex, run_directory = self.dir / "home", self.dir / "codex", self.dir / "run"
        for directory in (real_home, real_codex, run_directory):
            directory.mkdir()
        (real_codex / "config.toml").write_text('model = "gpt-x"\nmodel_reasoning_effort = "high"\n'
                                                'approval_policy = "never"\n\n[mcp_servers.x]\n'
                                                'command = "srv"\nmodel = "inner"\n')
        (real_codex / "auth.json").write_text("{}\n")
        home = run_directory / "codex-home"
        with mock.patch.dict(os.environ, {"HOME": str(real_home), "CODEX_HOME": str(real_codex)}):
            for key in ("XDG_CACHE_HOME", "XDG_DATA_HOME", "UV_CACHE_DIR", "UV_PYTHON_INSTALL_DIR"):
                os.environ.pop(key, None)
            _, _, env = qk_run.agent_command("codex:", False, self.dir, [run_directory])
            self.assertEqual((env["HOME"], env["CODEX_HOME"]), (str(home), str(home / ".codex")))
            self.assertEqual(env["UV_CACHE_DIR"], str(real_home / ".cache" / "uv"))
            self.assertEqual(env["UV_PYTHON_INSTALL_DIR"], str(real_home / ".local" / "share" / "uv" / "python"))
            config = home / ".codex" / "config.toml"
            self.assertEqual(config.read_text(), 'model = "gpt-x"\nmodel_reasoning_effort = "high"\n'
                                                 '\n[features]\nplugins = false\nremote_plugin = false\napps = false\n')
            auth = home / ".codex" / "auth.json"
            self.assertTrue(auth.is_symlink())
            self.assertEqual(Path(os.readlink(auth)), real_codex / "auth.json")
            config.write_text('model = "kept"\n')
            os.environ.update(UV_CACHE_DIR="/preset/cache", UV_PYTHON_INSTALL_DIR="/preset/python")
            _, _, env = qk_run.agent_command("codex:", True, self.dir, [run_directory])
        self.assertEqual(env["HOME"], str(home))
        self.assertEqual(config.read_text(), 'model = "kept"\n')
        self.assertEqual((env["UV_CACHE_DIR"], env["UV_PYTHON_INSTALL_DIR"]), ("/preset/cache", "/preset/python"))

    def test_codex_private_home_links_a_login_made_after_it_was_created(self):
        from unittest import mock
        real_codex, run_directory = self.dir / "codex", self.dir / "run"
        real_codex.mkdir()
        run_directory.mkdir()
        auth = run_directory / "codex-home" / ".codex" / "auth.json"
        with mock.patch.dict(os.environ, {"CODEX_HOME": str(real_codex)}):
            qk_run.agent_command("codex:", False, self.dir, [run_directory])
            self.assertFalse(auth.is_symlink())
            (real_codex / "auth.json").write_text("{}\n")
            qk_run.agent_command("codex:", False, self.dir, [run_directory])
        self.assertTrue(auth.is_symlink())
        self.assertEqual(Path(os.readlink(auth)), real_codex / "auth.json")

    def test_read_only_mcp_call_stops_agent_and_blocks(self):
        qk_run.KILL_GRACE_SECONDS = 0.5
        pid_file = self.dir / "child.pid"
        self.fake_agent("import subprocess, sys, time\n"
                        "child = subprocess.Popen(['sleep', '60'])\n"
                        "open(sys.argv[1], 'w').write(str(child.pid))\n"
                        f"print({MCP_WRITE!r}, flush=True)\n"
                        "time.sleep(60)\n", str(pid_file))
        started = time.monotonic()
        with self.assertRaises(qk_run.Blocked) as caught:
            self.call(write=False)
        self.assertEqual(str(caught.exception), "read-only stage called mcp mcp__aws_mcp_aws_run_script")
        self.assertLess(time.monotonic() - started, 5)
        pid = int(pid_file.read_text())
        gone = False
        while time.monotonic() - started < 4.5 and not gone:
            try:
                os.kill(pid, 0)
                time.sleep(0.05)
            except ProcessLookupError:
                gone = True
        self.assertTrue(gone, "agent child survived the guard")
        self.assertEqual((self.dir / "events.jsonl").read_text(encoding="utf-8").splitlines(), [MCP_WRITE])
        self.assertIn("mcp mcp__aws_mcp_aws_run_script", self.progress)

    def test_read_only_guard_names_runtime_devices_and_claude_mcp_tools(self):
        claude_mcp = json.dumps({"type": "assistant", "message": {"content": [
            {"type": "tool_use", "id": "t1", "name": "mcp__srv__tool", "input": {"q": "x"}}]}})
        for spec, event, shown in (("omp:anthropic/x", REPORT_ISSUE, "tool report_issue"),
                                   ("claude:", claude_mcp, "mcp mcp__srv__tool")):
            self.fake_agent(f"import time\nprint({event!r}, flush=True)\ntime.sleep(60)\n")
            with self.assertRaises(qk_run.Blocked) as caught:
                self.call(spec=spec, write=False)
            self.assertEqual(str(caught.exception), f"read-only stage called {shown}")

    def test_read_only_mcp_allows_only_listed_servers(self):
        done = (FIXTURES / "omp.jsonl").read_text(encoding="utf-8").splitlines()[3]
        self.fake_agent(f"print({MCP_WRITE!r}, flush=True)\nprint({done!r}, flush=True)\n")
        self.assertEqual(self.call(write=False, read_only_mcp=["aws-mcp"])[0], "DONE")
        self.assertEqual(self.call(write=True)[0], "DONE")
        self.fake_agent(f"import time\nprint({REPORT_ISSUE!r}, flush=True)\ntime.sleep(60)\n")
        with self.assertRaises(qk_run.Blocked) as caught:
            self.call(write=False, read_only_mcp=["aws-mcp"])
        self.assertEqual(str(caught.exception), "read-only stage called tool report_issue")

    def test_read_only_guard_ignores_search_patterns(self):
        done = (FIXTURES / "omp.jsonl").read_text(encoding="utf-8").splitlines()[3]
        grep_omp = json.dumps({"type": "tool_execution_start", "toolName": "grep",
                               "args": {"pattern": "xd://mcp__", "path": "."}})
        grep_claude = json.dumps({"type": "assistant", "message": {"content": [
            {"type": "tool_use", "id": "t1", "name": "Grep", "input": {"pattern": "mcp://x"}}]}})
        self.fake_agent(f"print({grep_omp!r}, flush=True)\nprint({done!r}, flush=True)\n")
        self.assertEqual(self.call(write=False)[0], "DONE")
        self.fake_agent(f"print({grep_claude!r}, flush=True)\n"
                        "print('{\"type\": \"result\", \"result\": \"DONE\"}', flush=True)\n")
        self.assertEqual(self.call(spec="claude:", write=False)[0], "DONE")

    def test_read_only_mcp_never_allows_mcp_resources_or_empty_names(self):
        self.assertFalse(qk_run.mcp_allowed("mcp://private/resource", [""]))
        self.assertFalse(qk_run.mcp_allowed("mcp://aws-mcp/doc", ["aws-mcp"]))
        self.assertFalse(qk_run.mcp_allowed("xd://mcp__aws_mcp_aws_run_script", [""]))
        self.assertTrue(qk_run.mcp_allowed("xd://mcp__aws_mcp_aws_run_script", ["", "aws-mcp"]))

    def test_read_only_guard_keeps_the_usage_of_the_stopped_turn(self):
        qk_run.KILL_GRACE_SECONDS = 0.5
        turn = json.dumps({"type": "turn_end", "message": {"role": "assistant",
                                                           "usage": {"input": 3, "output": 2, "cacheRead": 10}}})
        self.fake_agent(f"import time\nprint({turn!r}, flush=True)\nprint({MCP_WRITE!r}, flush=True)\n"
                        "time.sleep(60)\n")
        with self.assertRaises(qk_run.Blocked) as caught:
            self.call(write=False)
        self.assertEqual(caught.exception.usage, {"input": 13, "cached": 10, "output": 2})
        self.assertIn("tokens in=13 cached=10 out=2", self.progress)

    def test_call_agent_sums_usage_per_runtime(self):
        expected = {"claude": ({"input": 4812, "cached": 4500, "output": 80}, 0.0123,
                               "tokens in=4812 cached=4500 out=80 cost=$0.0123"),
                    "codex": ({"input": 5200, "cached": 4100, "output": 150}, None,
                              "tokens in=5200 cached=4100 out=150"),
                    "omp": ({"input": 5115, "cached": 4600, "output": 100}, 0.0073,
                            "tokens in=5115 cached=4600 out=100 cost=$0.0073")}
        for runtime, (tokens, cost, line) in expected.items():
            self.progress.clear()
            lines = (FIXTURES / f"{runtime}.jsonl").read_text(encoding="utf-8").splitlines()
            self.fake_agent("import sys\nfor line in sys.argv[1:]:\n    print(line, flush=True)\n", *lines)
            text, usage = self.call(spec=f"{runtime}:x")
            self.assertEqual(text, "DONE", runtime)
            found_cost = usage.pop("cost_usd", None)
            self.assertEqual(usage, tokens, runtime)
            if cost is None:
                self.assertIsNone(found_cost, runtime)
            else:
                self.assertAlmostEqual(found_cost, cost, msg=runtime)
            self.assertEqual(self.progress[-1], line, runtime)

    def test_mcp_calls_display_with_their_identifier(self):
        omp, claude = qk_run.EVENT_PARSERS["omp"], qk_run.EVENT_PARSERS["claude"]

        def omp_call(name, args):
            return omp({"type": "tool_execution_start", "toolName": name, "args": args})[0]
        self.assertEqual(omp_call("write", {"path": "xd://mcp__a_b", "content": "{}"}), "mcp mcp__a_b")
        self.assertEqual(omp_call("mcp__a_b", {"q": "x"}), "mcp mcp__a_b")
        self.assertEqual(omp_call("write", {"path": "xd://report_issue", "content": "x"}), "tool report_issue")
        self.assertEqual(claude({"type": "assistant", "message": {"content": [
            {"type": "tool_use", "name": "mcp__aws-docs__search", "input": {}}]}})[0], "mcp mcp__aws-docs__search")


MCP_WRITE = json.dumps({"type": "tool_execution_start", "toolCallId": "m1", "toolName": "write",
                        "args": {"path": "xd://mcp__aws_mcp_aws_run_script", "content": "{}"}})
REPORT_ISSUE = json.dumps({"type": "tool_execution_start", "toolCallId": "r1", "toolName": "write",
                           "args": {"path": "xd://report_issue", "content": "x"}})


if __name__ == "__main__":
    unittest.main()
