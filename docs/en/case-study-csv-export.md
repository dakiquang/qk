# Case study: export the current task page as CSV

[Tiếng Việt](../vi/case-study-csv-export.md) · [Docs index](README.md) · [Workflows](workflows.md)

This is a **worked example**, not a report of a feature shipped in this repository. qk contains skills, not a task application. The app, file names, PR number and feature below are illustrative; replace them with discovered repository facts. No review score, test output, PR URL or deployment result is fabricated here.

The goal is to show a realistic complete loop, not make every skill mandatory. We use one writing agent and one independent reviewer. More agents would add coordination without making this small feature safer.

## Situation and done criteria

Assume an existing task dashboard already loads an authorised, filtered and sorted page. A user wants a CSV download. Brainstorm must first resolve whether “export” means the current page or all matching records.

For this example, the user chooses **the current visible page**:

- Button is labelled **Export current page**, never implying all records.
- Export exactly the rows and order currently displayed, using a snapshot at click time. Do not fetch another page or add an endpoint.
- Columns are `title`, `status`, `createdAt`; do not add hidden/internal fields.
- A zero-row page produces a header-only file. Unicode, commas, quotes and newlines are preserved with correct CSV encoding.
- Spreadsheet-formula-like cell values are neutralised under an explicit policy agreed in the plan; quoting alone is not a defence.
- The download follows the app's existing browser/download conventions and cleans up temporary object URLs if it creates them.
- Existing filtering, sorting, permissions and normal task actions do not change. Add no dependency merely for this feature.

These are example acceptance criteria, not claims about an existing app. Confirm the real app's rules and spreadsheet requirements before adopting them.

## Roles and authority

| Role | Owns | Does not own |
|---|---|---|
| You | Product choice, plan approval, external-action authority, final ship decision | Repeating facts already available in the repo |
| Coordinator | Sources, plan, worker contract, evidence checking, integration proposal | Treating a worker's “done” as proof |
| Writer | Smallest approved implementation and its verification in one assigned checkout | Unrelated refactors, pushing or merging by inference |
| Independent reviewer | Read-only findings tied to the exact revision | Editing, test runs that write files, posting or merging in review mode |

Use the existing session as coordinator. Pick the writer route only when it can honour the requested model and permissions. A model quota/auth failure is **blocked**, not permission to choose another model.

All prompts below use Claude Code syntax. Use `$qk-…` in Codex or `/skill:qk-…` in omp. The companion is named **pr-orchestrator**, not `pr-orchestration` or a new qk skill; invoke it using that runtime's installed-skill syntax.

## 1. Brainstorm: resolve the product choice

```text
/qk-brainstorm Users want CSV export from the task dashboard. Compare exporting the visible page, exporting all filtered tasks, and keeping manual copy/paste. Inspect the actual task-list data flow first. We want a small change without background jobs or new infrastructure. Do not implement or write files yet.
```

The output should compare semantics, cost and reversibility. In this example you choose visible-page export because the data is already loaded and it needs no new server path. That means accepting the deliberate limitation: other pages are not included.

If the existing download utility's behaviour is unclear, a focused optional call is enough:

```text
/qk-research Does this repo already have a browser download helper and CSV/formula handling? Read its code and version-matched primary sources. Explain what we can reuse. Do not install packages or modify files.
```

**Gate:** you approve “current page only”. If users actually need all filtered records, change the plan before implementation; do not quietly ship a narrower feature.

## 2. Plan: turn intent into a bounded contract

```text
/qk-plan create Implement Export current page as CSV using the criteria above. Discover real paths and verification commands from this repo. Reuse the loaded task-page data and download conventions. Specify exact CSV escaping and formula-neutralisation rules, including leading whitespace/control characters, plus encoding expectations. No backend, new dependency or refactor. Save plans/task-page-csv.md. Do not implement.
```

The plan should identify the real task-list component, formatter/helper, tests and docs. Illustrative decomposition:

1. Pure CSV formatting from the selected fields; test observable output for empty input, special characters and formula-like cells.
2. Wire the existing page snapshot to the button using current UI/download patterns.
3. Exercise the browser: filter/sort, move to a non-first page, export, inspect the downloaded contents and confirm ordinary actions still work.

Do not write a test merely proving the button calls a mock helper. The consumer-visible boundary is the downloaded CSV and which rows it contains.

Optionally audit the plan with another model:

```text
/qk-agent-coord Ask Codex with model gpt-6.1-sol to audit plans/task-page-csv.md against this repo. Read-only. Check page-versus-all semantics, sensitive fields, CSV/formula cases and verification coverage. Return evidence and rejected hypotheses. No edits or configuration changes.
```

If the requested route cannot run, report why and let you decide. Apply accepted findings with `/qk-plan revise plans/task-page-csv.md …`, then explicitly approve the plan. Approval authorises the specified implementation, not later GitHub actions.

## 3. Orchestrate implementation: one writer is enough

Two valid choices; choose one, do not run both on the same checkout:

- **Simplest:** the current session implements via `/qk-cook plans/task-page-csv.md`. The session remains the only writer.
- **Delegated:** the current session coordinates a named implementation worker in a dedicated worktree/branch. Use the contract below. The worker follows the cook-style implementation contract inline; it does not automatically load `qk/cook`.

For the delegated path, first authorise creating the isolated worktree/branch. The coordinator records its real path and base revision; it must not invent a branch or overwrite an existing worktree.

```text
/qk-agent-coord Delegate implementation to Codex with model gpt-6.1-sol. I authorise creation of a dedicated worktree and feature branch for this task; discover the base from the repo. Implement the approved plans/task-page-csv.md there. Scope: the page export, its formatter, behaviour tests and feature docs. Preserve unrelated work. Run the discovered checks and browser smoke; report actual commands, results and gaps. No commit, push, PR, merge, tag or deploy. Do not integrate into my primary checkout. If the model or required browser tooling cannot run, report the blocker, do not substitute silently.
```

Before dispatch, the coordinator reads back a contract containing goal, non-goals, allowed files/checkout, acceptance criteria, model, permissions, verification and stop conditions. A worktree is not a sandbox; runtime permission limits still matter. If UI runtime verification is unavailable, that gap remains a ship blocker for this example, not a claimed pass.

After the worker returns, the coordinator reads the diff and evidence itself. Confirm the requested model from runtime output or mark it unverified. Inspect CSV contents—not just a “download succeeded” message. Integrate into the main working checkout only if you separately authorise integration, or continue towards the PR from the isolated feature worktree without integration. Never let both checkouts become active writers for the same task.

## 4. Verify and create the PR

The writer already verifies its work. An optional `/qk-test` can run broader checks, but it does not perform the browser interaction or replace missing UI evidence automatically.

Before PR creation, collect:

- Actual base and head revision; clean separation from unrelated changes.
- Acceptance-to-evidence mapping: formatter output tests, page/filter/sort download inspection and ordinary-action smoke.
- Exact local commands and exit codes discovered from this repo; failures classified with evidence, not assumed baseline.
- UI evidence if available, with private data removed; remaining limitations.

Then give specific external authority, for example:

```text
I authorise committing only this feature's changes on its feature branch, pushing that branch to this repo and opening one PR to the discovered base. Use the repo's commit convention. Include the approved plan and verification evidence in the PR body. Do not merge, release, deploy, force-push or delete branches. Tell me first if opening/pushing the PR triggers a preview with sensitive data or other side effects outside the known repo workflow.
```

The coordinator discovers existing push/PR automation before acting. Replace any mention of “all checks passed” with observed results. Save the **real PR URL and head SHA**; do not use an illustrative PR number for the next step.

## 5. Run pr-orchestrator review on the exact PR

After installing the separate companion, call it with the returned real URL:

```text
/pr-orchestrator review <actual-PR-URL>
```

The companion's current contract matters:

- `review` is read-only: no checkout/fetch, edits, worktrees, test commands that write cache, comments or merge. It reads CI status and labels that as remote CI, not local tests.
- Default dual audit is the parent plus one auditor from a different model family; log independent first-round findings, cross-audit methods in round two and let the parent verify lines at the PR head SHA against base.
- A second audit of the same model is not dual audit. If the second family is unavailable, stop the dual-audit score and report the missing route. Do not label a single-model pass as complete review.
- Only verified PR-introduced findings enter the score. Repository rules and the companion's configured gates decide eligibility; do not copy or weaken the rubric inside qk.

For this feature, the reviewer should challenge “current page”, snapshot timing, hidden fields, CSV escaping/formula safety, URL cleanup and whether evidence actually covers the browser path. These are review questions, not predeclared findings.

If a finding is verified, explicitly authorise the repair (`/pr-orchestrator fix <actual-PR-URL>` or a bounded cook request on the feature branch). Do not let two fix flows write simultaneously. Verify the repaired path; explicitly authorise any fix commit/push not already covered. A changed PR head invalidates the old review evidence for the new diff: review the updated revision, and wait for its checks. Never merge based only on the score of the previous SHA.

## 6. Approve, merge and ship—not one hidden action

Before merge, the example's extra ship gate requires **all repository-required checks green**, no unresolved correctness/security findings, an eligible companion verdict, the reviewed head still current and browser smoke evidence. This is a stricter choice for this example, not a claim that the companion always requires green CI by default. A high score cannot compensate for missing evidence.

Discover the repository's merge method, deployment triggers and release process **before** authorising merge. If merge automatically deploys production, merge authority includes that production effect only when you explicitly acknowledge it; otherwise stop.

To let the companion carry out merge under its supported mode:

```text
/pr-orchestrator full <actual-PR-URL>
Only this PR. Revalidate the current head and merge gates. All required CI must be green and the browser smoke must have evidence. If new work or a new head appears, show it before proceeding. Do not create a release/tag, delete branches or deploy beyond the explicitly approved existing merge-triggered workflow.
```

`full` can fix, test, post its score and merge this PR under its contract; it is broader than `review`. If you want only a manual merge with no automated fixing/comment, merge yourself using the repository's documented process rather than inventing a companion `merge` mode.

For release notes, after discovering the real previous release and merged revision:

```text
/qk-release-notes Draft EN and VI notes for <actual-previous-tag>..<actual-merged-revision>. Describe current-page-only export and any spreadsheet caveats. Save a draft at the repo's usual location. Do not bump versions, tag, publish or deploy.
```

If no prior tag exists, use the actual merged PR list instead. Review the draft, then separately authorise the concrete repository release/deploy action, version, revision and environment if required. qk does not invent a universal deploy command. When merge already deployed the application, verify that deployment rather than starting a duplicate one.

**Ship is done only after:** merged revision matches the intended deployment, the existing pipeline reports success, and a smoke export on the target environment uses non-sensitive test data and produces the expected rows/content. If the app fails there, stop promotion and use the repo's authorised rollback procedure; do not claim “shipped” from a merge or tag alone.

## 7. Close with evidence, or hand off honestly

The final report records the actual PR, merged/deployed revisions, environment, local checks, CI/deployment URLs, runtime smoke, limits and any release/tag that was explicitly authorised. Never fill these fields with illustrative values as if observed.

If blocked or switching sessions, `/qk-handoff write` saves real state and next decisions. The new session resumes read-only and asks for renewed external-action authority. No hidden retries, extra agents or new framework are needed.

## What to keep from this example

The invariant is not the number of skills: **resolve ambiguity → approve a bounded change → one writer → independent evidence-based PR review → authorise external effects → verify the shipped revision**. Skip a stage only when its question is already answered, not when its evidence is inconvenient.
