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


SHA = "a" * 40
OTHER_SHA = "b" * 40
URL = "https://github.com/example/project/pull/10"


class CliTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        environment = mock.patch.dict(os.environ, {"QK_STATE_DIR": str(self.root / "ledger")})
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
        self.assertNotIn("#2", brief)
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


if __name__ == "__main__":
    unittest.main()
