"""Behavioral decisions made by the offline CLI and read-only PR sync."""

import contextlib
import importlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import types
import unittest
from unittest import mock


SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))
qk = importlib.import_module("qk")
ledger = importlib.import_module("qk_ledger")
evaluator = importlib.import_module("qk_eval")


SHA = "a" * 40
OTHER_SHA = "b" * 40
URL = "https://github.com/example/project/pull/10"


def qk_run_state(root, run_id):
    return json.loads((root / "state" / "qk-run" / run_id / "state.json").read_text())


class FakeTTY(io.StringIO):
    def isatty(self):
        return True


DIFF = "diff --git a/src/main.py b/src/main.py\n+changed\tline\x1b[2J\n"
METHOD_FIELDS = "squashMergeAllowed,mergeCommitAllowed,rebaseMergeAllowed"


class CliTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        environment = mock.patch.dict(os.environ, {"QK_STATE_DIR": str(self.root / "ledger"),
                                                  "XDG_STATE_HOME": str(self.root / "state")})
        environment.start()
        self.addCleanup(environment.stop)

    def cli(self, *argv):
        output, errors = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(output), contextlib.redirect_stderr(errors):
            status = qk.main(list(argv))
        return status, output.getvalue(), errors.getvalue()

    def run_record(self, key="one", repo="project", kind="feature", refs=(), **overrides):
        data = {"run_id": key, "run_key": str(self.root / key), "status": "done",
                "repo_path": str(self.root / "missing-checkout"), "impl": "codex/model",
                "review": "claude/model", "commit": SHA, "pr_url": URL,
                "verify_results": [{"index": 0, "exit": 0}],
                "remaining_count": 0, "addressed_count": 2}
        data.update(overrides)
        return ledger.append("run", data, repo=repo, task_kind=kind, refs=refs)

    def decision(self, run, state="OPEN", **overrides):
        data = {"run_id": run["data"]["run_id"], "run_key": run["data"]["run_key"],
                "pr_url": run["data"]["pr_url"], "title": "A concrete change",
                "state": state, "head_sha": SHA, "merged_by": None,
                "merged_at": None, "closed_at": None,
                "checked_at": "2026-11-15T10:00:00+00:00"}
        data.update(overrides)
        return ledger.append("decision", data, repo=run["repo"], refs=[run["id"]])

    def remote(self, **overrides):
        data = {"url": URL, "title": "Read-only observation", "state": "OPEN",
                "mergedAt": None, "closedAt": None, "mergedBy": None, "headRefOid": SHA}
        data.update(overrides)
        return subprocess.CompletedProcess([], 0, json.dumps(data), "")

    def counts(self, text):
        return {line.split("\t")[0]: int(line.split("\t")[1])
                for line in text.splitlines()}

    def lesson_args(self, failed=True):
        evidence = [ledger.append("eval", {"case": "csv-export", "criteria": [
                        {"name": "clean", "passed": True}, {"name": "b", "passed": not failed}]})["id"],
                    ledger.append("finding", {})["id"]]
        return ["lesson", "propose", "--class", "missing validation", "--rule",
                "Validate external input before using it.", "--scope", "stage:review",
                "--scope", "repo:example", "--evidence", evidence[0],
                "--evidence", evidence[1], "--case", "csv-export"]

    def test_lesson_propose_list_and_decide_preserve_identity_and_sources(self):
        status, output, errors = self.cli(*self.lesson_args())
        self.assertEqual((status, errors), (0, ""))
        identifier = output.strip()
        proposal = ledger.records()[-1]
        self.assertEqual(proposal["id"], identifier)
        self.assertEqual(proposal["data"]["lesson_id"], identifier)
        self.assertEqual((proposal["source"], proposal["recorded_by"]), ("model", "code"))
        status, output, errors = self.cli("lesson", "list")
        self.assertEqual((status, errors), (0, ""))
        self.assertIn("needs-measure", output)
        self.assertIn("evidence=2 measured=0", output)
        _, output, _ = self.cli("lesson", "list", "--json", "--status", "proposed")
        self.assertEqual(json.loads(output), [{"id": identifier, "status": "proposed",
            "case": "csv-export", "scope": ["stage:review", "repo:example"],
            "evidence_count": 2, "measured_count": 0, "needs_measure": True,
            "needs_remeasure": False}])
        before = ledger.store_path().read_bytes()
        status, _, errors = self.cli("lesson", "decide", identifier, "active")
        self.assertEqual(status, 1)
        self.assertIn("measure the lesson before activating it", errors)
        self.assertEqual(ledger.store_path().read_bytes(), before)
        status, output, errors = self.cli("lesson", "decide", identifier, "dismissed",
                                          "--reason", "Too narrow.")
        self.assertEqual((status, errors), (0, ""))
        dismissed = ledger.records()[-1]
        self.assertEqual(output.strip(), dismissed["id"])
        self.assertEqual((dismissed["source"], dismissed["recorded_by"]), ("user", "code"))
        self.assertEqual(dismissed["data"], dict(proposal["data"], status="dismissed", reason="Too narrow."))
        status, _, errors = self.cli("lesson", "decide", identifier, "active")
        self.assertEqual(status, 1)
        self.assertIn("dismissed -> active", errors)
        _, output, _ = self.cli("lesson", "list", "--json")
        rows = json.loads(output)
        self.assertEqual(len(rows), 1)
        self.assertEqual((rows[0]["id"], rows[0]["status"]), (identifier, "dismissed"))
        self.assertFalse(rows[0]["needs_measure"])
        _, output, _ = self.cli("lesson", "list", "--status", "proposed", "--json")
        self.assertEqual(json.loads(output), [])

    def test_lesson_propose_needs_a_failed_eval_of_its_case(self):
        args = self.lesson_args(failed=False)
        before = ledger.store_path().read_bytes()
        status, _, errors = self.cli(*args)
        self.assertEqual(status, 1)
        self.assertIn("needs an eval of case csv-export", errors)
        self.assertEqual(ledger.store_path().read_bytes(), before)

    def test_lesson_invalid_proposals_return_errors_without_writing(self):
        args = self.lesson_args()
        wrong = ledger.append("run", {})["id"]
        invalid = [("--rule", "two\nlines"), ("--rule", "x" * 301),
                   ("--class", "x" * 201), ("--scope", "stage:verify"),
                   ("--case", "missing-case"), ("--case", "../cases/csv-export"),
                   ("--evidence", "missing"), ("--evidence", wrong)]
        before = ledger.store_path().read_bytes()
        for option, value in invalid:
            changed = list(args)
            changed[changed.index(option) + 1] = value
            with self.subTest(option=option, value=value):
                status, _, errors = self.cli(*changed)
                self.assertEqual(status, 1)
                self.assertTrue(errors)
        missing = list(args)
        index = missing.index("--evidence")
        del missing[index:index + 2]
        status, _, errors = self.cli(*missing)
        self.assertEqual(status, 1)
        self.assertIn("at least 2 distinct", errors)
        self.assertEqual(ledger.store_path().read_bytes(), before)

    def test_lesson_decide_retires_measured_active_fixture(self):
        self.cli(*self.lesson_args())
        proposal = ledger.records()[-1]
        active = dict(proposal, id="active-state", source="user", data=dict(
            proposal["data"], status="active", measured=[{"at": ledger.datetime.now(ledger.timezone.utc).isoformat(), "helps": True}]))
        with ledger.store_path().open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(active) + "\n")
        status, _, errors = self.cli("lesson", "decide", proposal["id"], "retired")
        self.assertEqual((status, errors), (0, ""))
        self.assertEqual(ledger.records()[-1]["data"], dict(active["data"], status="retired"))

    def test_lesson_suggest_groups_repeated_failures_and_never_writes(self):
        failed = {"name": "validate input", "passed": False}
        first = ledger.append("eval", {"case": "csv-export", "criteria": [failed, failed,
            {"name": "one failure", "passed": False}]})
        second = ledger.append("eval", {"case": "csv-export", "criteria": [failed]})
        other = ledger.append("eval", {"case": "other-case", "criteria": [failed]})
        passed = ledger.append("eval", {"case": "csv-export", "criteria": [dict(failed, passed=True)]})
        findings = [ledger.append("finding", {"class": "correctness"}) for _ in range(2)]
        ledger.append("finding", {"class": ""})
        ledger.append("finding", {"class": " "})
        ledger.append("finding", {"class": "single"})
        for data in ({}, {"case": "csv-export", "criteria": None},
                     {"case": [], "criteria": [failed]}, {"case": "csv-export", "criteria": [None]}):
            ledger.append("eval", data)
        before = ledger.store_path().read_bytes()
        status, output, errors = self.cli("lesson", "suggest")
        self.assertEqual((status, errors), (0, ""))
        self.assertEqual(len(output.splitlines()), 2)
        for record in [first, second] + findings:
            self.assertIn(record["id"], output)
        for value in ("one failure", "other-case", other["id"], passed["id"], "single"):
            self.assertNotIn(value, output)
        _, output, _ = self.cli("lesson", "suggest", "--min", "3")
        self.assertEqual(output.strip(), "No repeated failures in the ledger (need >= 3).")
        status, _, errors = self.cli("lesson", "suggest", "--min", "0")
        self.assertEqual(status, 1)
        self.assertIn("--min", errors)
        self.assertEqual(ledger.store_path().read_bytes(), before)

    def test_lesson_help_is_short(self):
        for command in ("suggest", "propose", "list", "decide"):
            with self.subTest(command=command):
                output = io.StringIO()
                with contextlib.redirect_stdout(output), self.assertRaises(SystemExit) as error:
                    qk.main(["lesson", command, "--help"])
                self.assertEqual(error.exception.code, 0)
                self.assertLessEqual(len(output.getvalue().splitlines()), 12)


    def test_late_backfill_cannot_hide_a_newer_resumed_run(self):
        runner = importlib.import_module("qk_run")
        for old_revision in (0, 2):
            with self.subTest(old_revision=old_revision), mock.patch.dict(
                    os.environ, {"QK_STATE_DIR": str(self.root / ("ordering-%s" % old_revision)),
                                 "QK_RUN_STATE_DIR": str(self.root / "runner")}):
                stale = {"id": "resumed", "repo": str(self.root / "project"),
                         "stage": "blocked", "task_kind": "stale", "ledger_revision": old_revision}
                resumed = dict(stale, stage="done", task_kind="current", pr_url=URL,
                               commit=SHA, ledger_revision=old_revision + 1)
                runner.save(resumed)
                directory = runner.run_dir(resumed["id"])
                current = ledger.records()[-1]
                ledger.record_run(stale, directory)
                # Reimporting current evidence deduplicates it, so ingestion order stays stale.
                self.assertEqual(ledger.record_run(resumed, directory)["id"], current["id"])
                status, brief, errors = self.cli("brief")
                self.assertEqual((status, errors), (0, ""))
                self.assertIn(URL, brief)
                self.assertIn("1/1 done/total", brief)
                _, stats, _ = self.cli("stats", "--by", "task_kind")
                self.assertEqual(self.counts(stats), {"total": 1, "current": 1})
    def test_brief_risk_rules(self):
        cases = [
            ({"status": "blocked", "blocked_at": "reviewing", "pr_url": ""},
             {}, "high — blocked at reviewing: reason unknown"),
            ({"remaining_count": 2}, {}, "high — 2 findings remain (severity unknown)"),
            ({"remaining_count": 3, "serious_count": 1}, {}, "high — 1 blocker/important findings remain"),
            ({"remaining_count": 4, "serious_count": 0, "lines_added": 150, "lines_deleted": 150,
              "changed_files": ["src/file%d.py" % n for n in range(10)]}, {}, "low — no rule matched"),
            ({"verify_results": [{"exit": 1}, {"exit": 0}]}, {}, "high — verify failed (1 nonzero)"),
            *[({"changed_files": [path]}, {}, "high — sensitive file " + path) for path in (
                ".github/workflows/ci.yml", "nested/PNPM-lock.yaml", "db/migrations/001.sql", "src/Author.py",
                "requirements-dev.txt", "infra/main.TF", "custom.lock", "Gemfile", "src/policy.py")],
            ({"changed_files": ["package.json", "go.mod"]}, {}, "high — sensitive file package.json +1 more"),
            ({"fix_rounds": 1}, {}, "medium — fix round used"),
            ({"lines_added": 301, "lines_deleted": 111}, {}, "medium — 412 lines changed"),
            ({"changed_files": ["file%d.py" % n for n in range(14)]}, {}, "medium — 14 files changed"),
            ({}, {"head_sha": OTHER_SHA}, "medium — PR head differs from recorded commit"),
            ({}, None, "medium — never synced"),
            ({"changed_files": None}, {}, "medium — scope unknown"),
            ({"lines_added": 150, "lines_deleted": 150,
              "changed_files": ["src/file%d.py" % n for n in range(10)]}, {}, "low — no rule matched"),
        ]
        for index, (overrides, snapshot, expected) in enumerate(cases):
            with self.subTest(expected=expected):
                values = {"changed_files": ["src/main.py"], "lines_added": 1, "lines_deleted": 0,
                          "task": "Make a change", "fix_rounds": 0}
                values.update(overrides)
                if values.get("changed_files") is None:
                    del values["changed_files"]
                run = self.run_record("risk%d" % index, repo="risk%d" % index, **values)
                if snapshot is not None:
                    self.decision(run, **snapshot)
                with mock.patch.object(subprocess, "run", side_effect=AssertionError("brief must be offline")):
                    status, output, errors = self.cli("brief", "--repo", run["repo"])
                self.assertEqual((status, errors), (0, ""))
                self.assertIn("RISK: " + expected, output.splitlines()[0])
                self.assertIn("scope unknown" if "changed_files" not in values else
                              "%d files, +%d/-%d" % (len(values["changed_files"]), values["lines_added"], values["lines_deleted"]), output)
                self.assertEqual(len(output.splitlines()), 4 if values.get("status") == "blocked" else 6)
                self.assertTrue(all(len(line) <= (320 if line.startswith("  Evidence:") else 240)
                                    for line in output.splitlines()))
                if values.get("status") == "blocked":
                    self.assertIn("(no PR)", output)
                    self.assertIn("qk run resume risk0", output)
                    self.assertIn("qk run abort risk0", output)
                elif snapshot is None:
                    self.assertIn("Make a change", output)

    def test_brief_reads_blocked_reason_from_state_not_ledger(self):
        state = self.root / "run" / "state.json"
        state.parent.mkdir()
        state.write_text(json.dumps({"reason": "verification failed after the single fix round:\n"
                                               "`make test --token=PRIVATE` exited 1:\nPRIVATE_LOG"}))
        run = self.run_record("blocked", status="blocked", blocked_at="verifying", pr_url="",
                              refs=[str(state)])
        self.assertNotIn("PRIVATE", json.dumps(ledger.records()))
        _, output, _ = self.cli("brief")
        self.assertIn("RISK: high — blocked at verifying: verification failed after the single fix round:",
                      output.splitlines()[0])
        self.assertNotIn("PRIVATE", output)
        state.unlink()
        _, output, _ = self.cli("brief")
        self.assertIn("blocked at verifying: reason unknown", output.splitlines()[0])
        self.assertIn(run["id"], output)

    def test_brief_long_title_keeps_risk_visible(self):
        run = self.run_record(changed_files=["package.json"], lines_added=1, lines_deleted=0)
        self.decision(run, title="A detailed change " * 30)
        _, output, _ = self.cli("brief")
        header = output.splitlines()[0]
        self.assertLessEqual(len(header), 240)
        self.assertIn(URL, header)
        self.assertIn("RISK: high — sensitive file package.json", header)
        self.assertIn("full: qk show --id " + run["id"], header)

    def test_brief_orders_cards_and_filters_blocked_runs(self):
        low = self.run_record("low", changed_files=[], lines_added=0, lines_deleted=0)
        self.decision(low)
        self.run_record("medium")
        high = self.run_record("high", remaining_count=2)
        self.decision(high)
        self.run_record("blocked", status="blocked", pr_url="", task="Repair run")
        self.run_record("other-blocked", repo="other", status="blocked", pr_url="")
        self.run_record("aborted", status="aborted", pr_url=URL + "99")
        self.run_record("no-pr", pr_url="")
        _, output, _ = self.cli("brief", "--repo", "project")
        headers = [line for line in output.splitlines() if line.startswith("#")]
        self.assertEqual(len(headers), 4)
        self.assertIn("#1 project: Repair run (no PR)  RISK: high — blocked at unknown: reason unknown", headers[0])
        self.assertIn("RISK: high — 2 findings remain (severity unknown)", headers[1])
        self.assertIn("RISK: medium — never synced", headers[2])
        self.assertIn("RISK: low — no rule matched", headers[3])
        for index, header in enumerate(headers, 1):
            self.assertTrue(header.startswith("#%d " % index))
        self.assertNotIn("other-blocked", output)
        self.assertNotIn("status=aborted", output)
        self.assertNotIn(URL + "99", output)
        _, output, _ = self.cli("brief", "--repo", "missing")
        self.assertEqual(output.strip(), "No open, unknown or blocked runs recorded.")

    def test_brief_excludes_merged_and_closed_but_retains_unsynced(self):
        merged = self.run_record("merged", pr_url=URL + "1")
        closed = self.run_record("closed", pr_url=URL + "2")
        unknown = self.run_record("pending", pr_url=URL + "3")
        self.decision(merged, "MERGED")
        self.decision(closed, "CLOSED")
        with mock.patch.object(subprocess, "run", side_effect=AssertionError("brief must be offline")):
            status, output, errors = self.cli("brief")
        self.assertEqual((status, errors), (0, ""))
        self.assertNotIn(merged["data"]["pr_url"], output)
        self.assertNotIn(closed["data"]["pr_url"], output)
        self.assertIn(unknown["data"]["pr_url"], output)
        self.assertIn("PR=UNKNOWN", output)
        self.assertIn("synced=never / unknown", output)
        self.assertIn("UNKNOWN commit comparison / not verified", output)

    def test_brief_latest_decision_and_head_invalidate_recorded_checks(self):
        run = self.run_record()
        self.decision(run, head_sha=SHA)
        self.decision(run, head_sha=OTHER_SHA, checked_at="2026-11-16T01:02:03+00:00")
        status, output, errors = self.cli("brief")
        self.assertEqual((status, errors), (0, ""))
        self.assertIn("STALE / not verified", output)
        self.assertIn(OTHER_SHA, output)
        self.assertIn("synced=2026-11-16T01:02:03+00:00", output)
        self.assertNotIn("matches last synced head", output)

    def test_brief_missing_review_and_verification_are_explicit(self):
        run = self.run_record(commit=None, verify_results=[], remaining_count=None, addressed_count=None)
        self.decision(run)
        _, output, _ = self.cli("brief")
        self.assertIn("UNKNOWN commit comparison / not verified", output)
        self.assertIn("missing verify evidence", output)
        self.assertIn("remaining=unknown", output)
        self.assertIn("remaining findings=unknown", output)

    def test_brief_claims_follow_finding_and_eval_refs_without_promoting_source(self):
        run = self.run_record()
        self.decision(run)
        finding = ledger.append("finding", {"run_id": run["data"]["run_id"], "run_key": run["data"]["run_key"],
                                            "severity": "P1", "verdict": "reported"}, refs=[run["id"]])
        evaluation = ledger.append("eval", {"case": "case", "runtime": "codex/model"}, refs=[finding["id"]])
        claims = []
        for about, text in [(run["id"], "run assertion"), (finding["id"], "finding assertion"),
                            (evaluation["id"], "eval assertion")]:
            status, _, errors = self.cli("log", "claim", "--about", about, "--text", text)
            self.assertEqual((status, errors), (0, ""))
            claims.append(ledger.records()[-1])
        unrelated = ledger.append("eval", {"case": "unrelated"})
        self.cli("log", "claim", "--about", unrelated["id"], "--text", "unrelated assertion")
        _, output, _ = self.cli("brief")
        self.assertIn("3 total; preview only:", output)
        self.assertIn(claims[0]["id"], output)
        self.assertIn("run assertion", output)
        self.assertNotIn("unrelated assertion", output)
        for claim in claims:
            status, detail, errors = self.cli("show", "--id", claim["id"], "--json")
            self.assertEqual((status, errors), (0, ""))
            self.assertEqual(json.loads(detail), [claim])
        self.assertIn("not independent verification", output)
        self.assertEqual(finding["source"], "model")
        self.assertEqual(finding["recorded_by"], "code")

    def test_brief_includes_claims_about_matched_decisions(self):
        for link in ("run_key", "run_id", "refs"):
            with self.subTest(link=link):
                run = self.run_record(link, repo=link)
                data = {link: run["data"][link]} if link != "refs" else {}
                decision = ledger.append("decision", data,
                                         refs=[run["id"]] if link == "refs" else [])
                claim = ledger.append("claim", {"about": decision["id"],
                                                "text": "decision assertion"})
                status, output, errors = self.cli("brief", "--repo", link)
                self.assertEqual((status, errors), (0, ""))
                self.assertIn(claim["id"], output)
                self.assertIn("decision assertion", output)
                self.assertIn("1 total; preview only:", output)

    def test_brief_bounds_many_checks_and_claims_without_hiding_failed_checks(self):
        verifies = [{"index": index, "exit": 0} for index in range(30)]
        verifies.extend([{"index": 30, "exit": 2}, {"index": 31}])
        run = self.run_record(commit="a" * 64, verify_results=verifies)
        self.decision(run, head_sha="b" * 64)
        claims = [ledger.append("claim", {"about": run["id"], "text": "long claim " * 50},
                                refs=[run["id"]]) for _ in range(20)]
        with mock.patch.object(subprocess, "run", side_effect=AssertionError("brief must be offline")):
            status, output, errors = self.cli("brief")
        self.assertEqual((status, errors), (0, ""))
        self.assertEqual(len(output.splitlines()), 6)
        self.assertTrue(all(len(line) <= 320 for line in output.splitlines()))
        self.assertLessEqual(sum((len(line) + 79) // 80 for line in output.splitlines()), 24)
        self.assertIn("a" * 64, output)
        self.assertIn("b" * 64, output)
        self.assertIn("STALE / not verified", output)
        self.assertIn("synced=2026-11-15T10:00:00+00:00", output)
        self.assertIn("32 checks (exit=0:30 nonzero:1 unknown:1)", output)
        self.assertIn("20 total; preview only:", output)
        self.assertIn(claims[0]["id"], output)
        self.assertNotIn(claims[-1]["id"], output)
        self.assertIn("qk show --id " + run["id"], output)
        self.assertIn("qk show --kind claim", output)
        self.assertIn("queued-for-fix=2", output)
        self.assertNotIn("not-reported-in-final-review", output)
        _, detail, _ = self.cli("show", "--id", run["id"], "--json")
        self.assertEqual(json.loads(detail)[0]["data"]["verify_results"], verifies)
        _, detail, _ = self.cli("show", "--kind", "claim", "--json")
        self.assertEqual(json.loads(detail), claims)

    def test_brief_keeps_claims_on_older_run_snapshot_evidence(self):
        for kind in ("run", "finding", "eval"):
            with self.subTest(kind=kind):
                evaluation = ledger.append("eval", {"case": "older"}) if kind == "eval" else None
                old = self.run_record(kind, repo=kind, status="blocked",
                                      refs=[evaluation["id"]] if evaluation else [])
                about = evaluation or old
                if kind == "finding":
                    about = ledger.append("finding", {"run_key": old["data"]["run_key"]},
                                          refs=[old["id"]])
                claim = ledger.append("claim", {"about": about["id"], "text": "old " + kind},
                                      refs=[about["id"]])
                newest = self.run_record(kind, repo=kind, status="done")
                self.decision(newest)
                status, output, errors = self.cli("brief", "--repo", kind)
                self.assertEqual((status, errors), (0, ""))
                self.assertIn("status=done", output)
                self.assertIn(claim["id"], output)
                self.assertIn("old " + kind, output)
                self.assertIn("1 total; preview only:", output)

    def test_brief_other_run_claims_cannot_cross_unrelated_graph_links(self):
        run = self.run_record()
        foreign = self.run_record("foreign", repo="other")
        foreign_finding = ledger.append(
            "finding", {"run_key": foreign["data"]["run_key"]},
            refs=[foreign["id"], run["id"]])
        foreign_eval = ledger.append(
            "eval", {"run_key": foreign["data"]["run_key"]}, refs=[run["id"]])
        linked_foreign = ledger.append(
            "run", foreign["data"], repo="other", refs=[run["id"]])
        for kind in ("decision", "unknown-kind"):
            ledger.append(kind, {}, refs=[run["id"], foreign["id"]])
        for about in (foreign, foreign_finding, foreign_eval, linked_foreign):
            ledger.append("claim", {"about": about["id"], "text": "foreign assertion"},
                          refs=[run["id"]])
        claim = ledger.append("claim", {"about": run["id"], "text": "own assertion"},
                              refs=[foreign["id"]])
        status, output, errors = self.cli("brief", "--repo", "project")
        self.assertEqual((status, errors), (0, ""))
        self.assertIn(claim["id"], output)
        self.assertIn("own assertion", output)
        self.assertIn("1 total; preview only:", output)
        self.assertNotIn("foreign assertion", output)

    def test_resumed_snapshots_count_once_in_stats_and_history(self):
        self.run_record("one", status="blocked")
        newest = self.run_record("one", status="done")
        self.run_record("two", status="blocked", pr_url=None)
        self.decision(newest)
        self.decision(newest)
        status, output, _ = self.cli("stats", "--by", "kind")
        self.assertEqual(status, 0)
        self.assertEqual(self.counts(output), {"total": 3, "run": 2, "decision": 1})
        _, brief, _ = self.cli("brief")
        self.assertEqual(brief.count("#1 project:"), 1)
        self.assertEqual(brief.count("#2 project:"), 1)
        self.assertNotIn("#3", brief)
        self.assertEqual(brief.count("  Done: run one "), 1)
        self.assertEqual(brief.count("  Done: run two "), 1)
        self.assertIn("feature 1/2 done/total", brief)
        self.assertIn("status=done", brief)

    def test_public_stats_never_print_private_names_even_arbitrary_labels(self):
        run = self.run_record(repo="secret-company", kind="secret-task", impl="secret-runtime")
        ledger.append("secret-kind", {"name": "secret-payload"}, repo="secret-company")
        self.cli("log", "claim", "--about", run["id"], "--text", "secret-claim")
        for group in ("kind", "task_kind", "runtime"):
            with self.subTest(group=group):
                status, output, errors = self.cli("stats", "--public", "--by", group)
                self.assertEqual((status, errors), (0, ""))
                self.assertEqual(self.counts(output)["total"], 3)
                self.assertNotIn("secret", output)
                self.assertNotIn(str(self.root), output)

    def test_task_kind_filter_and_runtime_use_latest_snapshot(self):
        self.run_record("one", kind="feature", impl="old-runtime")
        self.run_record("one", kind="bugfix", impl="new-runtime")
        ledger.append("eval", {"runtime": "eval-runtime"}, task_kind="bugfix")
        self.run_record("two", kind="", pr_url=None)
        _, output, _ = self.cli("stats", "--by", "runtime", "--task-kind", "bugfix")
        self.assertEqual(self.counts(output), {"total": 2, "new-runtime": 1, "eval-runtime": 1})
        _, output, _ = self.cli("stats", "--by", "task_kind")
        self.assertEqual(self.counts(output), {"total": 3, "bugfix": 2, "unclassified": 1})

    def test_show_filters_preserve_full_source_labels(self):
        run = self.run_record()
        finding = ledger.append("finding", {"severity": "P1"}, repo="project", refs=[run["id"]])
        ledger.append("finding", {"severity": "P2"}, repo="other")
        status, output, errors = self.cli("show", "--kind", "finding", "--repo", "project", "--json")
        self.assertEqual((status, errors), (0, ""))
        selected = json.loads(output)
        self.assertEqual([item["id"] for item in selected], [finding["id"]])
        self.assertEqual((selected[0]["source"], selected[0]["recorded_by"]), ("model", "code"))
        _, output, _ = self.cli("show", "--id", finding["id"], "--since", "7d")
        self.assertIn("source=model recorded_by=code", output)
        self.assertNotIn(run["id"] + " ", output)

    def test_claims_remain_visible_in_repository_and_task_kind_filters(self):
        run = self.run_record(kind="bugfix")
        expected = []
        about = run["id"]
        for text in ("first observation", "follow-up observation"):
            status, _, errors = self.cli("log", "claim", "--about", about, "--text", text)
            self.assertEqual((status, errors), (0, ""))
            about = ledger.records()[-1]["id"]
            expected.append(about)
        foreign = self.run_record("other", repo="other-project", kind="other-task")
        self.cli("log", "claim", "--about", foreign["id"], "--text", "unrelated observation")
        status, output, errors = self.cli("show", "--repo", "project", "--kind", "claim", "--json")
        self.assertEqual((status, errors), (0, ""))
        claims = json.loads(output)
        self.assertEqual([claim["id"] for claim in claims], expected)
        self.assertTrue(all(claim["source"] == "model" and claim["recorded_by"] == "model"
                            for claim in claims))
        status, output, errors = self.cli("stats", "--task-kind", "bugfix", "--by", "kind")
        self.assertEqual((status, errors), (0, ""))
        self.assertEqual(self.counts(output), {"total": 3, "run": 1, "claim": 2})

    def test_claim_validation_never_leaves_dangling_or_multiline_records(self):
        run = self.run_record()
        before = ledger.records()
        for about, text in [("missing-event", "claim"), (run["id"], "two\nlines"), (run["id"], " ")]:
            with self.subTest(about=about, text=text):
                status, _, errors = self.cli("log", "claim", "--about", about, "--text", text)
                self.assertEqual(status, 1)
                self.assertTrue(errors)
                self.assertEqual(ledger.records(), before)

    def test_shared_pr_keeps_decisions_scoped_to_run_key(self):
        first = self.run_record("first-directory", repo="first-project", run_id="same-source-id")
        second = self.run_record("second-directory", repo="second-project", run_id="same-source-id")
        self.decision(first, "CLOSED")
        self.decision(second, "OPEN")
        status, output, errors = self.cli("brief")
        self.assertEqual((status, errors), (0, ""))
        self.assertNotIn("first-project:", output)
        self.assertIn("second-project:", output)
        self.assertNotIn("#2", output)

    def test_sync_records_actual_remote_decision_for_each_related_run(self):
        first = self.run_record("one")
        second = self.run_record("two")
        with mock.patch.object(subprocess, "run", return_value=self.remote()):
            status, _, errors = self.cli("sync")
        self.assertEqual((status, errors), (0, ""))
        decisions = [item for item in ledger.records() if item["kind"] == "decision"]
        self.assertEqual({item["data"]["run_id"] for item in decisions},
                         {first["data"]["run_id"], second["data"]["run_id"]})
        for item in decisions:
            self.assertEqual(item["data"]["state"], "OPEN")
            self.assertEqual(item["data"]["head_sha"], SHA)
            self.assertEqual(item["data"]["title"], "Read-only observation")
            self.assertTrue(item["data"]["checked_at"])
            linked = first if item["data"]["run_id"] == first["data"]["run_id"] else second
            self.assertEqual(item["refs"], [linked["id"]])
            self.assertEqual((item["source"], item["recorded_by"]), ("code", "code"))
        with mock.patch.object(subprocess, "run", return_value=self.remote()):
            status, output, errors = self.cli("sync")
        self.assertEqual((status, errors), (0, ""))
        self.assertIn("0 recorded; 2 unchanged", output)
        self.assertEqual(sum(item["kind"] == "decision" for item in ledger.records()), 2)

    def test_sync_unchanged_state_preserves_ledger_and_observation_timestamp(self):
        self.run_record()
        with mock.patch.object(subprocess, "run", return_value=self.remote()):
            with mock.patch.object(qk, "_now", return_value="2026-11-16T00:00:00+00:00"):
                status, output, errors = self.cli("sync")
            self.assertEqual((status, errors), (0, ""))
            self.assertIn("1 recorded; 0 unchanged", output)
            before = ledger.store_path().read_bytes()
            with mock.patch.object(qk, "_now", return_value="2026-11-17T00:00:00+00:00"):
                status, output, errors = self.cli("sync")
        self.assertEqual((status, errors), (0, ""))
        self.assertIn("0 recorded; 1 unchanged", output)
        self.assertEqual(ledger.store_path().read_bytes(), before)
        _, brief, _ = self.cli("brief")
        self.assertIn("synced=2026-11-16T00:00:00+00:00", brief)

    def test_sync_records_each_meaningful_change_once_using_latest_decision(self):
        self.run_record()
        changes = [{}, {"title": "Changed title"}, {"headRefOid": OTHER_SHA},
                   {"state": "CLOSED", "closedAt": "2026-11-16T01:00:00Z"},
                   {"state": "MERGED", "mergedAt": "2026-11-16T01:00:00Z",
                    "mergedBy": {"login": "reviewer"}},
                   {"mergedAt": "2026-11-16T02:00:00Z"},
                   {"closedAt": "2026-11-16T02:00:00Z"},
                   {"mergedBy": {"login": "another-reviewer"}},
                   {"state": "OPEN", "mergedAt": None, "closedAt": None, "mergedBy": None}]
        payload = {}
        for count, change in enumerate(changes, 1):
            payload.update(change)
            with self.subTest(change=change), mock.patch.object(
                    subprocess, "run", return_value=self.remote(**payload)):
                status, output, errors = self.cli("sync")
                self.assertEqual((status, errors), (0, ""))
                self.assertIn("1 recorded; 0 unchanged", output)
                before = ledger.store_path().read_bytes()
                status, output, errors = self.cli("sync")
                self.assertEqual((status, errors), (0, ""))
                self.assertIn("0 recorded; 1 unchanged", output)
                self.assertEqual(ledger.store_path().read_bytes(), before)
                self.assertEqual(sum(r["kind"] == "decision" for r in ledger.records()), count)

    def test_sync_remote_merged_and_closed_decisions_remove_pending_items(self):
        for state in ("MERGED", "CLOSED"):
            with self.subTest(state=state):
                run = self.run_record(state, pr_url=URL + ("1" if state == "MERGED" else "2"))
                payload = {"url": run["data"]["pr_url"], "state": state,
                           "closedAt": "2026-11-16T01:02:03Z"}
                if state == "MERGED":
                    payload.update(mergedAt="2026-11-16T01:02:03Z", mergedBy={"login": "reviewer"})
                reply = self.remote(**payload)
                # Each response is specific to the requested PR, not an optimistic status fallback.
                def response(argv, **kwargs):
                    if argv[3] == run["data"]["pr_url"]:
                        return reply
                    return self.remote(url=argv[3], state="CLOSED", closedAt="2026-11-16T01:02:03Z")
                with mock.patch.object(subprocess, "run", side_effect=response):
                    status, _, errors = self.cli("sync")
                self.assertEqual((status, errors), (0, ""))
                _, brief, _ = self.cli("brief")
                self.assertNotIn(run["data"]["pr_url"], brief)

    def test_invalid_remote_payloads_never_create_decisions(self):
        self.run_record()
        invalid = [[], {}, {"state": "MERGED"},
                   {"state": "UNKNOWN"}, {"headRefOid": "not-a-sha"},
                   {"url": "https://github.com/other/repo/pull/99"},
                   {"mergedAt": "yesterday"}, {"mergedBy": {"login": 3}},
                   {"state": "MERGED", "mergedAt": None},
                   {"state": "CLOSED", "closedAt": None},
                   {"state": "OPEN", "closedAt": "2026-11-16T00:00:00Z"},
                   {"title": None}]
        baseline = json.loads(self.remote().stdout)
        for changes in invalid:
            payload = dict(baseline, **changes) if isinstance(changes, dict) and changes else changes
            if changes == {"state": "MERGED"}:
                payload = changes
            with self.subTest(payload=payload):
                reply = subprocess.CompletedProcess([], 0, json.dumps(payload), "")
                with mock.patch.object(subprocess, "run", return_value=reply):
                    status, _, errors = self.cli("sync")
                self.assertEqual(status, 1)
                self.assertIn(URL, errors)
                self.assertFalse(any(item["kind"] == "decision" for item in ledger.records()))

    def test_sync_partial_failure_keeps_real_success_and_returns_nonzero(self):
        good = self.run_record("good")
        bad_url = "https://github.com/example/project/pull/11"
        self.run_record("bad", pr_url=bad_url)
        def response(argv, **kwargs):
            if argv[3] == URL:
                return self.remote()
            return subprocess.CompletedProcess([], 1, "", "authentication failed")
        with mock.patch.object(subprocess, "run", side_effect=response):
            status, _, errors = self.cli("sync")
        self.assertEqual(status, 1)
        self.assertIn(bad_url, errors)
        self.assertIn("authentication failed", errors)
        decisions = [item for item in ledger.records() if item["kind"] == "decision"]
        self.assertEqual([item["data"]["run_id"] for item in decisions], [good["data"]["run_id"]])
        _, brief, _ = self.cli("brief")
        self.assertIn("PR=UNKNOWN", brief)

    def test_failed_resync_preserves_observation_timestamp_without_fabrication(self):
        run = self.run_record()
        self.decision(run, checked_at="2026-11-01T00:00:00+00:00")
        before = ledger.records()
        for failure in (FileNotFoundError("gh missing"), subprocess.TimeoutExpired("gh", 60)):
            with self.subTest(failure=failure):
                with mock.patch.object(subprocess, "run", side_effect=failure):
                    status, _, errors = self.cli("sync")
                self.assertEqual(status, 1)
                self.assertTrue(errors)
                self.assertEqual(ledger.records(), before)
        _, output, _ = self.cli("brief")
        self.assertIn("synced=2026-11-01T00:00:00+00:00", output)

    def test_sync_uses_read_only_pr_view_in_existing_checkout(self):
        checkout = self.root / "checkout"
        checkout.mkdir()
        self.run_record(repo_path=str(checkout))
        def remote_from_checkout(argv, **kwargs):
            if argv != ["gh", "pr", "view", URL, "--json", qk.PR_FIELDS]:
                raise AssertionError("unexpected PR mutation or command")
            if kwargs.get("cwd") != str(checkout):
                raise AssertionError("wrong repository selected")
            return self.remote(title="checkout-specific PR")
        with mock.patch.object(subprocess, "run", side_effect=remote_from_checkout):
            status, _, errors = self.cli("sync")
        self.assertEqual((status, errors), (0, ""))
        decisions = [item for item in ledger.records() if item["kind"] == "decision"]
        self.assertEqual(decisions[0]["data"]["title"], "checkout-specific PR")

    def test_backfill_is_idempotent_and_skips_active_states(self):
        source = self.root / "source"
        for stage in ("done", "blocked", "aborted", "implement"):
            directory = source / stage
            directory.mkdir(parents=True)
            state = {"id": stage, "stage": stage, "repo": str(self.root / "project"),
                     "impl": "codex/model", "review": "claude/model", "commit": SHA,
                     "findings": [], "verify_results": [], "usage": {}}
            (directory / "state.json").write_text(json.dumps(state), encoding="utf-8")
        runner = types.SimpleNamespace(state_root=lambda: source)
        with mock.patch.dict(sys.modules, {"qk_run": runner}):
            first, _, first_errors = self.cli("sync", "--backfill")
            second, _, second_errors = self.cli("sync", "--backfill")
        self.assertEqual((first, second, first_errors, second_errors), (0, 0, "", ""))
        runs = [item for item in ledger.records() if item["kind"] == "run"]
        self.assertEqual(len(runs), 3)
        self.assertEqual({item["data"]["status"] for item in runs}, {"done", "blocked", "aborted"})
        self.assertEqual({item["data"]["run_key"] for item in runs},
                         {str((source / stage).resolve()) for stage in ("done", "blocked", "aborted")})

    def test_bad_backfill_reports_failure_and_retains_good_state(self):
        source = self.root / "source"
        broken = source / "broken"
        broken.mkdir(parents=True)
        (broken / "state.json").write_text('{"stage":', encoding="utf-8")
        good = source / "good"
        good.mkdir()
        (good / "state.json").write_text(json.dumps({"id": "good", "stage": "done",
            "repo": str(self.root / "project"), "findings": [], "usage": {}}), encoding="utf-8")
        with mock.patch.dict(sys.modules, {"qk_run": types.SimpleNamespace(state_root=lambda: source)}):
            status, _, errors = self.cli("sync", "--backfill")
        self.assertEqual(status, 1)
        self.assertIn("broken", errors)
        runs = [item for item in ledger.records() if item["kind"] == "run"]
        self.assertEqual(len(runs), 1)
        self.assertEqual(runs[0]["data"]["status"], "done")

    def eval_fixture(self):
        root = self.root / "state" / "qk-eval" / "20261116-100000-abcd"
        first = {"criteria": [{"name": "works", "passed": False}],
                 "tokens": 10, "seconds": 1.5, "error": None}
        final = {"criteria": [{"name": "works", "passed": True}],
                 "tokens": 20, "seconds": 2.5, "error": None, "runs": 2}
        single = dict(final, runs=1)
        for case, attempts in (("flipped", [first, final]), ("single", [single])):
            for index, result in enumerate(attempts, 1):
                attempt = root / case / ("run-%d" % index)
                attempt.mkdir(parents=True)
                (attempt / "check.json").write_text(json.dumps(result["criteria"]), encoding="utf-8")
        (root / "results.json").write_text(json.dumps({
            "runtime": "claude:opus", "kit": "none", "started": "20261116-100000",
            "cases": {"flipped": final, "single": single}, "regression": False}), encoding="utf-8")
        return root.resolve(), final, single

    def test_eval_backfill_imports_all_attempts_with_live_keys_and_is_idempotent(self):
        root, final, single = self.eval_fixture()
        # An attempt already collected live must deduplicate against the import.
        existing = ledger.record_eval("claude:opus", "flipped", final, root / "flipped" / "run-2", "none")
        status, _, errors = self.cli("sync", "--backfill")
        self.assertEqual((status, errors), (0, ""))
        records = ledger.records()
        self.assertEqual(len(records), 3)
        self.assertTrue(all(record["kind"] == "eval" for record in records))
        self.assertIn(existing, records)
        by_attempt = {record["refs"][0]: record for record in records}
        first = by_attempt[str(root / "flipped" / "run-1")]["data"]
        self.assertFalse(first["passed"])
        self.assertIsNone(first["tokens"])
        self.assertIsNone(first["seconds"])
        self.assertEqual(first["kit"], "none")
        single_data = by_attempt[str(root / "single" / "run-1")]["data"]
        self.assertEqual((single_data["runtime"], single_data["kit"], single_data["tokens"],
                          single_data["seconds"], single_data["passed"]),
                         ("claude:opus", "none", 20, 2.5, True))
        self.assertEqual(ledger.record_eval("claude:opus", "single", single,
                                          root / "single" / "run-1", "none"),
                         by_attempt[str(root / "single" / "run-1")])
        before = ledger.store_path().read_bytes()
        status, _, errors = self.cli("sync", "--backfill")
        self.assertEqual((status, errors), (0, ""))
        self.assertEqual(ledger.store_path().read_bytes(), before)

    def test_eval_backfill_warns_once_per_missing_or_malformed_results_and_continues(self):
        self.eval_fixture()
        base = self.root / "state" / "qk-eval"
        invalid = {"missing": None, "broken": "{", "array": "[]",
                   "bad-cases": json.dumps({"runtime": "codex:", "cases": []}),
                   "bad-attempt": json.dumps({"runtime": "codex:", "cases": {"case": {"runs": "two"}}})}
        for name, content in invalid.items():
            directory = base / name
            directory.mkdir()
            if content is not None:
                (directory / "results.json").write_text(content, encoding="utf-8")
        status, output, errors = self.cli("sync", "--backfill")
        self.assertEqual(status, 1)
        self.assertIn("5 failures", output)
        self.assertEqual(len(errors.splitlines()), 5)
        for name in invalid:
            self.assertIn(str(base / name / "results.json"), errors)
        self.assertEqual(len(ledger.records()), 3)

    def test_stored_and_remote_text_cannot_inject_terminal_lines(self):
        run = self.run_record(repo="project\x1b[31m\nspoof", impl="model\rspoof")
        self.decision(run, title="title\nforged\x1b[2J")
        _, output, _ = self.cli("brief")
        self.assertNotIn("\x1b", output)
        self.assertNotIn("\r", output)
        self.assertEqual(len(output.splitlines()), 6)
        self.assertIn("\\u000a", output)
        self.assertIn("\\u001b", output)

    def test_malformed_ledger_is_a_clear_nonzero_read_error(self):
        self.run_record()
        path = ledger.state_dir() / "ledger.jsonl"
        with path.open("a", encoding="utf-8") as stream:
            stream.write('{"truncated":')
        status, output, errors = self.cli("show", "--json")
        self.assertEqual(status, 1)
        self.assertEqual(output, "")
        self.assertTrue(errors)

    def tty_cli(self, answers, *argv, stdin_tty=True, stdout_tty=True):
        stdin = (FakeTTY if stdin_tty else io.StringIO)("".join(answer + "\n" for answer in answers))
        output, errors = (FakeTTY if stdout_tty else io.StringIO)(), io.StringIO()
        with mock.patch.object(sys, "stdin", stdin), mock.patch.object(sys, "stdout", output), \
                mock.patch.object(sys, "stderr", errors):
            status = qk.main(list(argv))
        return status, output.getvalue(), errors.getvalue(), stdin

    def fake_gh(self, head=SHA, allowed=("squashMergeAllowed",), merge_exit=0):
        calls = []

        def run(argv, **options):
            calls.append(argv)
            self.assertNotIn("cwd", options)
            replies = {("gh", "pr", "view"): (0, json.dumps({"headRefOid": head})),
                       ("gh", "repo", "view"): (0, json.dumps({field: field in allowed
                                                               for field in METHOD_FIELDS.split(",")})),
                       ("gh", "pr", "diff"): (0, DIFF),
                       ("gh", "pr", "merge"): (merge_exit, "")}
            code, stdout = replies[tuple(argv[:3])]
            return subprocess.CompletedProcess(argv, code, stdout, "merge refused" if code else "")
        return calls, run

    def user_records(self):
        return [record for record in ledger.records() if record["source"] == "user"]

    def test_brief_tty_merge_requires_matching_head_and_records_choice(self):
        run = self.run_record()
        self.decision(run)
        calls, gh = self.fake_gh()
        with mock.patch.object(subprocess, "run", side_effect=gh):
            status, output, errors, _ = self.tty_cli(["y"], "brief")
        self.assertEqual((status, errors), (0, ""))
        self.assertIn("[y] merge  [n] leave  [d] diff  [s] skip", output)
        self.assertEqual(calls, [["gh", "pr", "view", URL, "--json", "headRefOid"],
                                 ["gh", "repo", "view", "github.com/example/project", "--json", METHOD_FIELDS],
                                 ["gh", "pr", "merge", URL, "--squash", "--match-head-commit", SHA]])
        [record] = self.user_records()
        self.assertEqual((record["kind"], record["recorded_by"], record["repo"], record["refs"]),
                         ("decision", "code", "project", [run["id"]]))
        self.assertEqual(set(record["data"]), {"choice", "pr_url", "run_key", "run_id", "head",
                                               "decided_at", "elapsed_s"})
        self.assertEqual((record["data"]["choice"], record["data"]["head"], record["data"]["pr_url"],
                          record["data"]["run_key"], record["data"]["run_id"]),
                         ("merge", SHA, URL, run["data"]["run_key"], "one"))
        self.assertGreaterEqual(record["data"]["elapsed_s"], 0)
        with self.subTest("merge fails"):
            before = ledger.store_path().read_bytes()
            calls, gh = self.fake_gh(merge_exit=1)
            with mock.patch.object(subprocess, "run", side_effect=gh):
                status, output, errors, _ = self.tty_cli(["y", "s"], "brief")
            self.assertEqual(status, 0)
            self.assertIn("merge refused", errors)
            self.assertEqual(output.count("[y] merge"), 2)
            self.assertEqual(calls[-1][:3], ["gh", "pr", "merge"])
            self.assertEqual(ledger.store_path().read_bytes(), before)

    def test_brief_tty_merge_refuses_incomplete_merge_settings(self):
        self.decision(self.run_record())
        calls, gh = self.fake_gh()

        def partial(argv, **options):
            reply = gh(argv, **options)
            if argv[:3] == ["gh", "repo", "view"]:
                return subprocess.CompletedProcess(argv, 0, json.dumps({"squashMergeAllowed": True}), "")
            return reply
        before = ledger.store_path().read_bytes()
        with mock.patch.object(subprocess, "run", side_effect=partial):
            status, output, errors, _ = self.tty_cli(["y", "s"], "brief")
        self.assertEqual(status, 0)
        self.assertIn("invalid repository response", errors)
        self.assertNotIn(["gh", "pr", "merge"], [call[:3] for call in calls])
        self.assertEqual(ledger.store_path().read_bytes(), before)

    def test_brief_tty_merge_records_time_of_y_not_after_gh_calls(self):
        self.decision(self.run_record())
        clock = ["2026-11-19T00:00:00+00:00"]
        calls, gh = self.fake_gh()

        def delayed_gh(argv, **options):
            clock[0] = "2026-11-19T00:05:00+00:00"
            return gh(argv, **options)
        with mock.patch.object(subprocess, "run", side_effect=delayed_gh), \
                mock.patch.object(qk, "_now", side_effect=lambda: clock[0]):
            status, _, errors, _ = self.tty_cli(["y"], "brief")
        self.assertEqual((status, errors), (0, ""))
        self.assertEqual(calls[-1][:3], ["gh", "pr", "merge"])
        [record] = self.user_records()
        self.assertEqual(record["data"]["decided_at"], "2026-11-19T00:00:00+00:00")

    def test_brief_tty_merge_elapsed_stops_at_the_key_press(self):
        self.decision(self.run_record())
        ticks = iter([100.0, 102.5])
        calls, gh = self.fake_gh()
        with mock.patch.object(subprocess, "run", side_effect=gh), \
                mock.patch.object(qk.time, "monotonic", side_effect=lambda: next(ticks, 999.0)):
            status, _, errors, _ = self.tty_cli(["y"], "brief")
        self.assertEqual((status, errors), (0, ""))
        self.assertEqual(calls[-1][:3], ["gh", "pr", "merge"])
        [record] = self.user_records()
        self.assertEqual(record["data"]["elapsed_s"], 2.5)

    def test_brief_tty_changed_head_refuses_before_merge(self):
        self.decision(self.run_record())
        calls, gh = self.fake_gh(head=OTHER_SHA)
        with mock.patch.object(subprocess, "run", side_effect=gh):
            status, output, errors, _ = self.tty_cli(["y", "s"], "brief")
        self.assertEqual(status, 0)
        self.assertIn("PR head %s differs from recorded commit %s" % (OTHER_SHA, SHA), errors)
        self.assertEqual(calls, [["gh", "pr", "view", URL, "--json", "headRefOid"]])
        self.assertEqual(self.user_records(), [])

    def test_brief_tty_asks_for_method_when_several_are_allowed(self):
        self.decision(self.run_record())
        calls, gh = self.fake_gh(allowed=METHOD_FIELDS.split(","))
        with mock.patch.object(subprocess, "run", side_effect=gh):
            status, output, errors, _ = self.tty_cli(["y", "rebase"], "brief")
        self.assertEqual((status, errors), (0, ""))
        self.assertIn("Merge method [squash/merge/rebase]", output)
        self.assertEqual(calls[-1], ["gh", "pr", "merge", URL, "--rebase", "--match-head-commit", SHA])
        self.assertEqual([record["data"]["choice"] for record in self.user_records()], ["merge"])
        with self.subTest("unknown method"):
            calls, gh = self.fake_gh(allowed=METHOD_FIELDS.split(","))
            with mock.patch.object(subprocess, "run", side_effect=gh):
                status, _, errors, _ = self.tty_cli(["y", "fast-forward", "s"], "brief")
            self.assertEqual(status, 0)
            self.assertIn("merge method must be one of", errors)
            self.assertNotIn(["gh", "pr", "merge"], [call[:3] for call in calls])
            self.assertEqual(len(self.user_records()), 1)

    def test_brief_tty_leave_and_diff_record_only_the_decision(self):
        run = self.run_record()
        self.decision(run)
        with mock.patch.object(subprocess, "run", side_effect=AssertionError("leave must not call gh")):
            status, _, errors, _ = self.tty_cli(["n"], "brief")
        self.assertEqual((status, errors), (0, ""))
        [record] = self.user_records()
        self.assertEqual((record["data"]["choice"], record["data"]["head"], record["data"]["pr_url"]),
                         ("leave", SHA, URL))
        calls, gh = self.fake_gh()
        with mock.patch.object(subprocess, "run", side_effect=gh):
            status, output, errors, _ = self.tty_cli(["d", "n"], "brief")
        self.assertEqual((status, errors), (0, ""))
        self.assertEqual(calls, [["gh", "pr", "diff", URL]])
        self.assertIn("+changed" + " " * 8 + "line\\u001b[2J", output)
        self.assertNotIn("\x1b", output)
        self.assertEqual(output.count("[y] merge  [n] leave  [d] diff  [s] skip"), 2)
        self.assertEqual([record["data"]["choice"] for record in self.user_records()], ["leave", "leave"])

    def test_brief_tty_skip_and_end_of_input_record_nothing(self):
        self.decision(self.run_record())
        self.decision(self.run_record("two", pr_url=URL + "2"))
        before = ledger.store_path().read_bytes()
        for answers, prompts in ((["s", "s"], 2), ([], 1)):
            with self.subTest(answers=answers), mock.patch.object(
                    subprocess, "run", side_effect=AssertionError("skip must not call gh")):
                status, output, errors, _ = self.tty_cli(answers, "brief")
                self.assertEqual((status, errors), (0, ""))
                self.assertEqual(output.count("[y] merge"), prompts)
                self.assertEqual((output.count("#1 project:"), output.count("#2 project:")), (1, 1))
                self.assertEqual(ledger.store_path().read_bytes(), before)

    def test_brief_tty_blocked_card_records_intent_only(self):
        run = self.run_record("blocked", status="blocked", pr_url="")
        for answers, expected in ((["a"], ["abort-later"]), (["r"], ["resume-later"]),
                                  (["s"], []), (["y", "a"], ["abort-later"])):
            with self.subTest(answers=answers), mock.patch.dict(
                    os.environ, {"QK_STATE_DIR": str(self.root / ("blocked-" + "".join(answers)))}):
                ledger.append("run", run["data"], repo=run["repo"], task_kind=run["task_kind"])
                with mock.patch.object(subprocess, "run", side_effect=AssertionError("blocked cards never call gh")):
                    status, output, errors, _ = self.tty_cli(answers, "brief")
                self.assertEqual((status, errors), (0, ""))
                self.assertEqual(output.count("[a] abort later  [r] resume later  [s] skip"), len(answers))
                self.assertNotIn("[y] merge", output)
                records = self.user_records()
                self.assertEqual([record["data"]["choice"] for record in records], expected)
                for record in records:
                    self.assertEqual((record["data"]["pr_url"], record["data"]["head"]), (None, None))

    def stopped_state(self, run_id, stage="implementing", lock=False):
        directory = self.root / "state" / "qk-run" / run_id
        directory.mkdir(parents=True)
        (directory / "state.json").write_text(json.dumps({
            "id": run_id, "stage": stage, "task": "Add the thing", "repo": str(self.root / "project"),
            "impl": "omp:model", "review": "codex:", "task_kind": "feature"}))
        if lock:
            (directory / "run.lock").write_text("")
        return directory

    def test_brief_shows_runs_left_mid_stage_without_a_process(self):
        import fcntl
        self.stopped_state("no-lock-file")
        self.stopped_state("free-lock", stage="verifying", lock=True)
        held = self.stopped_state("held-lock", lock=True)
        for stage in ("queued", "awaiting_approval", "blocked", "done"):
            self.stopped_state("not-running-" + stage, stage=stage)
        self.run_record("blocked", status="blocked", pr_url="")
        free_key = str((self.root / "state" / "qk-run" / "free-lock").resolve())
        self.run_record("free-lock", status="blocked", pr_url="", run_key=free_key)  # earlier block, then killed
        with (held / "run.lock").open("a") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            before = ledger.store_path().read_bytes()
            with mock.patch.object(subprocess, "run", side_effect=AssertionError("brief must be offline")):
                status, output, errors = self.cli("brief")
        self.assertEqual((status, errors), (0, ""))
        lines = output.splitlines()
        titles = [line for line in lines if line.startswith("#")]
        self.assertEqual(len(titles), 3)
        self.assertEqual(sorted(title.split("RISK: ")[1] for title in titles[:2]),
                         ["high — stopped at implementing (runner gone)", "high — stopped at verifying (runner gone)"])
        self.assertIn("RISK: high — blocked at", titles[2])
        self.assertNotIn("held-lock", output)
        self.assertNotIn("not-running", output)
        self.assertIn("  Next: qk run status no-lock-file, then qk run abort no-lock-file", lines)
        self.assertIn("status=stopped at verifying", output)
        self.assertNotIn("qk show --id " + str(self.root), output)
        self.assertEqual(ledger.store_path().read_bytes(), before)
        self.assertFalse((self.root / "state" / "qk-run" / "no-lock-file" / "run.lock").exists())
        _, filtered, _ = self.cli("brief", "--repo", "other")
        self.assertNotIn("stopped at", filtered)

    def test_brief_stopped_scan_rereads_state_under_the_lock(self):
        directory = self.stopped_state("finishing", lock=True)
        real_open = os.open

        def finish_then_open(path, flags, *args):
            if str(path).endswith("run.lock"):  # the runner saves `done` and releases before the probe
                state = json.loads((directory / "state.json").read_text())
                (directory / "state.json").write_text(json.dumps(dict(state, stage="done")))
            return real_open(path, flags, *args)

        with mock.patch.object(qk.os, "open", side_effect=finish_then_open):
            self.assertEqual(qk._stopped_runs(), [])

    def test_brief_stopped_scan_skips_a_runner_that_takes_the_lock_meanwhile(self):
        import fcntl
        directory = self.stopped_state("starting", lock=True)
        real_read = Path.read_text
        reads, taken = [], []

        def read_then_lock(path, *args, **kwargs):
            text = real_read(path, *args, **kwargs)
            if path == directory / "state.json":
                reads.append(path)
                if len(reads) == 2:  # the re-read after the first probe: a runner takes the lock now
                    taken.append((directory / "run.lock").open("a"))
                    fcntl.flock(taken[0], fcntl.LOCK_EX | fcntl.LOCK_NB)
            return text

        try:
            with mock.patch.object(Path, "read_text", read_then_lock):
                self.assertEqual(qk._stopped_runs(), [])
        finally:
            for lock in taken:
                lock.close()
        self.assertEqual(len(taken), 1)

    def test_brief_stopped_run_hides_only_its_own_ledger_card(self):
        self.stopped_state("shared-id")
        self.run_record("shared-id", status="blocked", pr_url="")  # another source directory, same id
        _, output, _ = self.cli("brief")
        titles = [line for line in output.splitlines() if line.startswith("#")]
        self.assertEqual(len(titles), 2)
        self.assertIn("stopped at implementing (runner gone)", titles[0])
        self.assertIn("blocked at", titles[1])

    def test_brief_stopped_run_replaces_legacy_record_only_in_its_repo(self):
        self.stopped_state("legacy")  # repo label "project"
        self.run_record("legacy", status="blocked", pr_url="", run_key=None)
        self.run_record("legacy", repo="elsewhere", status="blocked", pr_url="", run_key=None)
        _, output, _ = self.cli("brief")
        titles = [line for line in output.splitlines() if line.startswith("#")]
        self.assertEqual(len(titles), 2)
        self.assertIn("#1 project: Add the thing (no PR)  RISK: high — stopped at implementing", titles[0])
        self.assertIn("#2 elsewhere:", titles[1])

    def test_brief_tty_stopped_card_records_abort_intent_only(self):
        self.stopped_state("killed")
        with mock.patch.object(subprocess, "run", side_effect=AssertionError("stopped cards never call gh")):
            status, output, errors, _ = self.tty_cli(["y", "r", "a"], "brief")
        self.assertEqual((status, errors), (0, ""))
        self.assertEqual(output.count("[a] abort later  [s] skip"), 3)
        [record] = self.user_records()
        self.assertEqual((record["data"]["choice"], record["data"]["run_id"], record["data"]["pr_url"]),
                         ("abort-later", "killed", None))
        self.assertEqual(qk_run_state(self.root, "killed")["stage"], "implementing")

    def test_brief_without_both_terminals_never_prompts_or_writes(self):
        self.decision(self.run_record())
        self.run_record("blocked", status="blocked", pr_url="")
        _, plain, _ = self.cli("brief")
        before = ledger.store_path().read_bytes()
        for stdin_tty, stdout_tty in ((False, False), (True, False), (False, True)):
            with self.subTest(stdin_tty=stdin_tty, stdout_tty=stdout_tty), mock.patch.object(
                    subprocess, "run", side_effect=AssertionError("brief must be offline")):
                status, output, errors, stdin = self.tty_cli(["y", "a"], "brief", stdin_tty=stdin_tty,
                                                             stdout_tty=stdout_tty)
                self.assertEqual((status, output, errors), (0, plain, ""))
                self.assertEqual(stdin.read(), "y\na\n")
                self.assertEqual(ledger.store_path().read_bytes(), before)

    def test_user_decisions_stay_separate_from_sync_snapshots(self):
        self.run_record()
        with mock.patch.object(subprocess, "run", return_value=self.remote()), \
                mock.patch.object(qk, "_now", return_value="2026-11-16T00:00:00+00:00"):
            self.cli("sync")
        with mock.patch.object(subprocess, "run", side_effect=AssertionError("leave must not call gh")):
            self.tty_cli(["n"], "brief")
            self.tty_cli(["n"], "brief")
        with mock.patch.object(subprocess, "run", return_value=self.remote()), \
                mock.patch.object(qk, "_now", return_value="2026-11-17T00:00:00+00:00"):
            status, output, errors = self.cli("sync")
        self.assertEqual((status, errors), (0, ""))
        self.assertIn("0 recorded; 1 unchanged", output)
        _, brief, _ = self.cli("brief")
        self.assertIn("PR=OPEN; synced=2026-11-16T00:00:00+00:00", brief)
        expected = {"total": 4, "run": 1, "decision": 1, "user_decision": 2}
        for public in ((), ("--public",)):
            with self.subTest(public=public):
                _, output, _ = self.cli("stats", "--by", "kind", *public)
                self.assertEqual(self.counts(output), expected)


if __name__ == "__main__":
    unittest.main()
