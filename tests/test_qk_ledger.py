import json
import multiprocessing
import os
import queue
import stat
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import qk_ledger as ledger


def append_worker(directory, output, about):
    os.environ["QK_STATE_DIR"] = directory
    try:
        shared = ledger.append("future-kind", {"value": 1}, key="shared")
        unique = ledger.append("future-kind", {"pid": os.getpid()})
        claim = ledger.append("claim", {"about": about, "text": "Model observation"},
                              key="shared-claim")
        output.put((shared["id"], unique["id"], claim["id"]))
    except Exception as error:
        output.put(("ERROR", repr(error)))


def read_worker(directory, started, output):
    os.environ["QK_STATE_DIR"] = directory
    started.set()
    try:
        output.put(ledger.records())
    except Exception as error:
        output.put(("ERROR", repr(error)))


class LedgerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.directory = self.root / "evidence"
        self.env = patch.dict(os.environ, {"QK_STATE_DIR": str(self.directory)})
        self.env.start()
        self.addCleanup(self.env.stop)

    def run_state(self):
        return {
            "id": "run-1", "repo": str(self.root / "project"), "stage": "done",
            "impl": "omp:model", "review": "codex:", "commit": "a" * 40,
            "pr_url": "https://github.com/example/project/pull/1", "fix_rounds": 1,
            "task_kind": "bugfix", "findings": [], "addressed": ["private claim"],
            "verify_results": [{"cmd": "python3 -m unittest", "exit": 0,
                                "tail": "PRIVATE VERIFY LOG"}],
            "usage": {"reviewing": [{"spec": "codex:", "input": 100,
                                      "cached": 20, "output": 10, "cost_usd": 0.01,
                                      "raw": "PRIVATE USAGE ENVELOPE"}]},
            "task": "PRIVATE TASK", "prompt": "PRIVATE PROMPT", "diff": "PRIVATE CODE",
            "updated": "first-save",
        }

    def finding(self, file="src/main.py", line=4):
        return {"severity": "important", "class": "correctness", "file": file,
                "line": line, "claim": "PRIVATE FINDING CLAIM", "fix": "PRIVATE FIX CODE"}

    def test_append_keeps_previous_bytes_and_sets_private_permissions(self):
        self.assertEqual(ledger.records(), [])
        first = ledger.append("run", {"value": 1}, refs=["artifact"])
        before = ledger.store_path().read_bytes()
        os.chmod(ledger.store_path(), 0o644)
        second = ledger.append("decision", {"value": 2})
        self.assertEqual(ledger.store_path().read_bytes()[:len(before)], before)
        self.assertEqual(ledger.records(), [first, second])
        self.assertNotEqual(first["id"], second["id"])
        self.assertEqual(stat.S_IMODE(ledger.store_path().stat().st_mode), 0o600)
        self.assertEqual(stat.S_IMODE((self.directory / ledger.LOCK_NAME).stat().st_mode), 0o600)

    def test_unknown_kind_and_fields_survive_read_and_append(self):
        first = ledger.append("future-event", {"future": {"field": [1, 2]}})
        first["future_header"] = {"mode": "preserve"}
        ledger.store_path().write_text(json.dumps(first) + "\n", encoding="utf-8")
        ledger.append("other-event", {})
        self.assertEqual(ledger.records()[0], first)

    def test_corrupt_data_is_never_discarded_or_appended_over(self):
        first = ledger.append("run", {})
        valid = ledger.store_path().read_bytes()
        damaged = [b"{broken}\n", b"{\"partial\":", b"\xff\n", b"\n", b"[]\n",
                   json.dumps(dict(first, v=2)).encode() + b"\n",
                   json.dumps(first).encode(),
                   json.dumps(dict(first, id="second")).encode().replace(b'"v": 1', b'"v": NaN') + b"\n",
                   b'{"v":1,"v":1}\n']
        for suffix in damaged:
            with self.subTest(suffix=suffix):
                raw = valid + suffix
                ledger.store_path().write_bytes(raw)
                with self.assertRaisesRegex(ValueError, "line 2"):
                    ledger.records()
                with self.assertRaises(ValueError):
                    ledger.append("run", {"new": True})
                self.assertEqual(ledger.store_path().read_bytes(), raw)

    def test_duplicate_ids_and_keys_are_explicit_corruption(self):
        first = ledger.append("run", {}, key="one")
        valid = ledger.store_path().read_bytes()
        for record in (dict(first, key="two"), dict(first, id="new")):
            with self.subTest(record=record):
                raw = valid + (json.dumps(record) + "\n").encode()
                ledger.store_path().write_bytes(raw)
                with self.assertRaisesRegex(ValueError, "duplicate"):
                    ledger.records()
                self.assertEqual(ledger.store_path().read_bytes(), raw)

    def test_short_writes_are_completed(self):
        real_write = os.write
        with patch.object(ledger.os, "write", side_effect=lambda fd, raw: real_write(fd, raw[:11])):
            record = ledger.append("run", {"value": "x" * 200})
        self.assertEqual(ledger.records(), [record])

    def test_partial_write_failure_preserves_old_evidence_and_fails_loudly(self):
        ledger.append("run", {"first": True})
        before = ledger.store_path().read_bytes()
        real_write = os.write
        calls = []

        def interrupted(fd, raw):
            if calls:
                raise OSError("disk full")
            calls.append(True)
            return real_write(fd, raw[:17])

        with patch.object(ledger.os, "write", side_effect=interrupted):
            with self.assertRaisesRegex(OSError, "disk full"):
                ledger.append("run", {"second": True})
        after = ledger.store_path().read_bytes()
        self.assertTrue(after.startswith(before))
        self.assertGreater(len(after), len(before))
        with self.assertRaisesRegex(ValueError, "torn"):
            ledger.records()
        with self.assertRaises(ValueError):
            ledger.append("run", {"third": True})
        self.assertEqual(ledger.store_path().read_bytes(), after)

    def test_fsync_failure_is_explicit_and_retry_recovers_complete_line(self):
        with patch.object(ledger.os, "fsync", side_effect=OSError("fsync failed")):
            with self.assertRaisesRegex(OSError, "fsync failed"):
                ledger.append("run", {"value": 1}, key="durable")
        synced = []
        real_fsync = os.fsync

        def sync(fd):
            synced.append(stat.S_IFMT(os.fstat(fd).st_mode))
            real_fsync(fd)

        with patch.object(ledger.os, "fsync", side_effect=sync):
            record = ledger.append("run", {"value": 1}, key="durable")
        self.assertEqual(synced, [stat.S_IFREG, stat.S_IFDIR])
        self.assertEqual(ledger.records(), [record])

    def test_invalid_json_inputs_do_not_damage_existing_evidence(self):
        ledger.append("run", {})
        before = ledger.store_path().read_bytes()
        for data in ({"value": float("nan")}, {"value": object()}, []):
            with self.subTest(data=data), self.assertRaises(ValueError):
                ledger.append("run", data)
        self.assertEqual(ledger.store_path().read_bytes(), before)

    def test_same_key_is_atomic_and_kind_collisions_fail(self):
        first = ledger.append("run", {"value": 1}, key="snapshot")
        self.assertEqual(ledger.append("run", {"value": 2}, key="snapshot"), first)
        with self.assertRaisesRegex(ValueError, "another record kind"):
            ledger.append("eval", {}, key="snapshot")
        self.assertEqual(ledger.records(), [first])

    def test_claims_require_existing_reference_and_bounded_single_line_text(self):
        parent = ledger.append("run", {})
        before = ledger.store_path().read_bytes()
        invalid = [
            {"about": "missing", "text": "observation"},
            {"about": parent["id"], "text": ""},
            {"about": parent["id"], "text": "   "},
            {"about": parent["id"], "text": "line\nother"},
            {"about": parent["id"], "text": "line\r\nother"},
            {"about": parent["id"], "text": "line\u2028other"},
            {"about": parent["id"], "text": "escape\x1b[31m"},
            {"about": parent["id"], "text": "x" * (ledger.MAX_CLAIM_TEXT + 1)},
            {"about": parent["id"], "text": "valid", "code": "not allowed"},
        ]
        for data in invalid:
            with self.subTest(data=data), self.assertRaises(ValueError):
                ledger.append("claim", data)
        self.assertEqual(ledger.store_path().read_bytes(), before)
        claim = ledger.append("claim", {"about": parent["id"], "text": "Model observation"})
        self.assertEqual(claim["source"], "model")
        self.assertEqual(claim["recorded_by"], "model")
        self.assertEqual(claim["data"]["about"], parent["id"])
        # Idempotency does not bypass checking the new request's reference.
        ledger.append("claim", claim["data"], key="claim-key")
        with self.assertRaisesRegex(ValueError, "missing"):
            ledger.append("claim", {"about": "missing", "text": "observation"}, key="claim-key")

    def test_claim_metadata_follows_its_reference_not_caller_labels(self):
        for repo, task_kind in (("project", "bugfix"), ("", "")):
            with self.subTest(repo=repo, task_kind=task_kind):
                parent = ledger.append("finding", {}, repo=repo, task_kind=task_kind)
                ledger.append("run", {}, repo="unrelated", task_kind="different")
                claim = ledger.append("claim", {"about": parent["id"], "text": "Observation"},
                                      repo="caller-label", task_kind="caller-task")
                nested = ledger.append("claim", {"about": claim["id"], "text": "Follow-up"})
                for record in (claim, nested):
                    self.assertEqual((record["repo"], record["task_kind"]), (repo, task_kind))
                    self.assertEqual((record["source"], record["recorded_by"]), ("model", "model"))

    def test_concurrent_appends_deduplicate_and_claims_remain_reachable(self):
        parent = ledger.append("run", {})
        context = multiprocessing.get_context("spawn")
        output = context.Queue()
        processes = [context.Process(target=append_worker,
                                     args=(str(self.directory), output, parent["id"]))
                     for _ in range(6)]
        for process in processes:
            process.start()
            self.addCleanup(self.stop_process, process)
        results = [output.get(timeout=20) for _ in processes]
        for process in processes:
            process.join(20)
            self.assertEqual(process.exitcode, 0)
        self.assertFalse(any(result[0] == "ERROR" for result in results), results)
        self.assertEqual(len({result[0] for result in results}), 1)
        self.assertEqual(len({result[1] for result in results}), 6)
        self.assertEqual(len({result[2] for result in results}), 1)
        records = ledger.records()
        self.assertEqual(len(records), 9)
        identifiers = {record["id"] for record in records}
        self.assertTrue(all(record["data"]["about"] in identifiers
                            for record in records if record["kind"] == "claim"))

    @staticmethod
    def stop_process(process):
        if process.is_alive():
            process.terminate()
        process.join(5)

    def test_reader_waits_for_in_progress_write(self):
        import fcntl
        first = ledger.append("run", {})
        record = dict(first, id="in-progress", data={"complete": True})
        raw = (json.dumps(record) + "\n").encode()
        context = multiprocessing.get_context("spawn")
        started, output = context.Event(), context.Queue()
        with (self.directory / ledger.LOCK_NAME).open("r+b") as lock:
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
            with ledger.store_path().open("ab", buffering=0) as store:
                store.write(raw[:20])
                process = context.Process(target=read_worker,
                                          args=(str(self.directory), started, output))
                process.start()
                self.addCleanup(self.stop_process, process)
                self.assertTrue(started.wait(20))
                with self.assertRaises(queue.Empty):
                    output.get(timeout=0.2)
                store.write(raw[20:])
            fcntl.flock(lock.fileno(), fcntl.LOCK_UN)
        self.assertEqual(output.get(timeout=20), [first, record])
        process.join(20)
        self.assertEqual(process.exitcode, 0)

    def test_state_cannot_be_written_inside_checkout_worktree_or_bare_repository(self):
        for kind in ("checkout", "worktree", "bare"):
            with self.subTest(kind=kind):
                root = self.root / kind
                root.mkdir()
                if kind == "checkout":
                    (root / ".git").mkdir()
                elif kind == "worktree":
                    (root / ".git").write_text("gitdir: /elsewhere/worktrees/item\n")
                else:
                    (root / "HEAD").write_text("ref: refs/heads/main\n")
                    (root / "objects").mkdir()
                    (root / "refs").mkdir()
                state = root / "nested" / "state"
                with patch.dict(os.environ, {"QK_STATE_DIR": str(state)}):
                    with self.assertRaisesRegex(ValueError, "outside"):
                        ledger.append("run", {})
                self.assertFalse(state.exists())

    def test_symlinked_state_cannot_bypass_repository_boundary(self):
        root = self.root / "project"
        root.mkdir()
        (root / ".git").mkdir()
        alias = self.root / "alias"
        alias.symlink_to(root, target_is_directory=True)
        with patch.dict(os.environ, {"QK_STATE_DIR": str(alias / "evidence")}):
            with self.assertRaisesRegex(ValueError, "outside"):
                ledger.append("run", {})
        self.assertFalse((root / "evidence").exists())

    def test_symlinked_store_and_lock_do_not_touch_target(self):
        self.directory.mkdir()
        target = self.root / "target"
        target.write_text("private target\n")
        for name in (ledger.STORE_NAME, ledger.LOCK_NAME):
            with self.subTest(name=name):
                link = self.directory / name
                if link.exists():
                    link.unlink()
                link.symlink_to(target)
                with self.assertRaises(OSError):
                    ledger.append("run", {})
                self.assertEqual(target.read_text(), "private target\n")
                link.unlink()

    def test_nonregular_store_is_rejected_without_blocking(self):
        self.directory.mkdir()
        os.mkfifo(ledger.store_path())
        with self.assertRaisesRegex(ValueError, "regular files"):
            ledger.records()

    def test_run_projection_omits_sensitive_raw_fields_and_keeps_provenance(self):
        state = self.run_state()
        state["findings"] = [self.finding()]
        state["verify_results"].append({"cmd": "PRIVATE COMMAND", "exit": 2})
        record = ledger.record_run(state, self.root / "artifacts")
        records = ledger.records()
        self.assertEqual(record["repo"], "project")
        self.assertEqual(record["task_kind"], "bugfix")
        self.assertEqual(record["data"]["repo_path"], str(self.root / "project"))
        self.assertEqual(record["data"]["verify_results"], [{"index": 0, "exit": 0}, {"index": 1, "exit": 2}])
        self.assertEqual(record["data"]["remaining_count"], 1)
        self.assertEqual(record["data"]["addressed_count"], 1)
        self.assertEqual(record["refs"], [str(self.root / "artifacts" / "state.json")])
        finding = records[1]
        self.assertEqual(finding["kind"], "finding")
        self.assertEqual((finding["source"], finding["recorded_by"]), ("model", "code"))
        self.assertEqual(finding["refs"], [record["id"]])
        self.assertEqual(finding["data"]["file"], "src/main.py")
        self.assertEqual(finding["data"]["verdict"], "reported")
        self.assertNotIn("repo_path", finding["data"])
        encoded = json.dumps(records)
        for sensitive in ("PRIVATE", "private claim", "claim\":", "fix\":", "tail\":"):
            self.assertNotIn(sensitive, encoded)
        self.assertNotIn("python3 -m unittest", encoded)
        self.assertEqual(state["verify_results"][1]["cmd"], "PRIVATE COMMAND")
        self.assertNotIn("raw", record["data"]["usage"]["reviewing"][0])

    def test_run_rejects_active_stages_and_projects_minimal_aborted_state(self):
        for stage in ("planning", "implementing", "reviewing", "awaiting_approval"):
            with self.subTest(stage=stage), self.assertRaises(ValueError):
                ledger.record_run({"id": "run", "stage": stage}, self.root / "run")
        record = ledger.record_run({"id": "run", "stage": "aborted"}, self.root / "run")
        self.assertEqual(record["repo"], "")
        self.assertEqual(record["data"]["repo_path"], "")
        self.assertEqual(record["data"]["remaining_count"], 0)

    def test_changed_resumed_snapshot_appends_but_repeated_save_does_not(self):
        state = self.run_state()
        state["stage"] = "blocked"
        first = ledger.record_run(state, self.root / "run")
        state["updated"] = "second-save"
        self.assertEqual(ledger.record_run(state, self.root / "run"), first)
        state.update(stage="done", commit="b" * 40)
        second = ledger.record_run(state, self.root / "run")
        self.assertNotEqual(first["id"], second["id"])
        self.assertEqual(first["data"]["run_key"], second["data"]["run_key"])
        self.assertEqual([item["data"]["status"] for item in ledger.records()], ["blocked", "done"])

    def test_history_reports_absence_without_inventing_a_human_fixed_verdict(self):
        state = self.run_state()
        old, remaining = self.finding(), self.finding("src/other.py", 9)
        state["findings"] = [remaining]
        state["review_history"] = [{"round": 0, "findings": [old, remaining]},
                                   {"round": 1, "findings": [remaining]}]
        ledger.record_run(state, self.root / "run")
        findings = [record["data"] for record in ledger.records() if record["kind"] == "finding"]
        self.assertEqual([finding["round"] for finding in findings], [0, 0, 1])
        self.assertEqual([finding["verdict"] for finding in findings],
                         ["not-reported-in-final-review", "reported", "reported"])

    def test_old_backfill_does_not_infer_fixed_findings_from_addressed_strings(self):
        state = self.run_state()
        state["findings"] = [self.finding()]
        ledger.record_run(state, self.root / "old-run")
        finding = ledger.records()[1]["data"]
        self.assertEqual(finding["verdict"], "reported")
        self.assertEqual(finding["round"], 1)
        self.assertEqual(len(ledger.records()), 2)

    def test_interrupted_finding_projection_is_repaired_idempotently(self):
        state = self.run_state()
        state["findings"] = [self.finding(), self.finding("second.py", 2)]
        real_append = ledger.append
        calls = []

        def interrupted(kind, *args, **kwargs):
            if kind == "finding":
                calls.append(True)
                if len(calls) == 2:
                    raise OSError("interrupted projection")
            return real_append(kind, *args, **kwargs)

        with patch.object(ledger, "append", side_effect=interrupted):
            with self.assertRaisesRegex(OSError, "interrupted projection"):
                ledger.record_run(state, self.root / "run")
        before = ledger.store_path().read_bytes()
        self.assertEqual(len(ledger.records()), 2)
        run = ledger.record_run(state, self.root / "run")
        self.assertTrue(ledger.store_path().read_bytes().startswith(before))
        self.assertEqual(len(ledger.records()), 3)
        self.assertEqual(ledger.record_run(state, self.root / "run"), run)
        self.assertEqual(len(ledger.records()), 3)

    def test_finding_paths_cannot_copy_absolute_or_traversal_paths(self):
        state = self.run_state()
        invalid = [str(self.root / "private.py"), "../secret.py", "src/../../secret.py",
                   "C:\\private.py", "src/\nprivate.py", "x" * 241]
        state["findings"] = [self.finding(file) for file in invalid] + [self.finding("src/ok.py")]
        ledger.record_run(state, self.root / "run")
        findings = [record["data"] for record in ledger.records() if record["kind"] == "finding"]
        self.assertEqual([item["file"] for item in findings], [""] * len(invalid) + ["src/ok.py"])

    def eval_result(self, passed=True, error=None):
        return {"criteria": [{"name": "works", "passed": passed, "message": "PRIVATE MESSAGE"}],
                "usage": {"raw": "PRIVATE USAGE"}, "tokens": 125, "seconds": 1.25,
                "error": error, "final": "PRIVATE FINAL OUTPUT"}

    def test_eval_projection_retains_only_outcomes_and_artifact_references(self):
        attempt = self.root / "eval" / "attempt-1"
        record = ledger.record_eval("omp:model", "case-name", self.eval_result(), attempt)
        self.assertEqual(record["source"], "code")
        self.assertEqual(record["recorded_by"], "code")
        self.assertEqual(record["data"], {
            "case": "case-name", "kit": "qk", "runtime": "omp:model",
            "criteria": [{"name": "works", "passed": True}], "passed": True,
            "tokens": 125, "seconds": 1.25, "agent_error": False,
        })
        self.assertEqual(record["refs"], [str(attempt), str(attempt / "check.json"),
                                          str(attempt / "final.md")])
        self.assertNotIn("PRIVATE", json.dumps(record))

    def test_eval_flip_attempts_are_independent_and_individually_idempotent(self):
        first_dir, second_dir = self.root / "attempt-1", self.root / "attempt-2"
        first = ledger.record_eval("codex:", "case-name", self.eval_result(False), first_dir, "custom")
        second = ledger.record_eval("codex:", "case-name", self.eval_result(True), second_dir, "custom")
        self.assertNotEqual(first["id"], second["id"])
        self.assertFalse(first["data"]["passed"])
        self.assertTrue(second["data"]["passed"])
        self.assertEqual(second["data"]["kit"], "custom")
        self.assertEqual(ledger.record_eval("codex:", "case-name", self.eval_result(True), first_dir,
                                            "custom"), first)
        self.assertEqual(ledger.records(), [first, second])

    def test_eval_error_is_boolean_only_and_unknown_tokens_stay_unknown(self):
        result = self.eval_result(True, "PRIVATE AGENT ERROR /secret/path")
        result["tokens"] = None
        record = ledger.record_eval("claude:", "case-name", result, self.root / "attempt")
        self.assertFalse(record["data"]["passed"])
        self.assertTrue(record["data"]["agent_error"])
        self.assertIsNone(record["data"]["tokens"])
        self.assertNotIn("PRIVATE", json.dumps(record))
        self.assertNotIn("/secret/path", json.dumps(record))

    def test_eval_rejects_invalid_criteria_and_numeric_data_without_appending(self):
        invalid = [dict(self.eval_result(), criteria=[{"name": "works", "passed": "yes"}]),
                   dict(self.eval_result(), criteria=[{"passed": True}]),
                   dict(self.eval_result(), tokens=-1),
                   dict(self.eval_result(), seconds=float("inf"))]
        for result in invalid:
            with self.subTest(result=result), self.assertRaises(ValueError):
                ledger.record_eval("codex:", "case-name", result, self.root / "attempt")
        self.assertEqual(ledger.records(), [])


if __name__ == "__main__":
    unittest.main()
