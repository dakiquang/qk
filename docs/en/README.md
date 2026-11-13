# qk documentation

[Tiếng Việt](../vi/README.md) · [Back to the project README](../../README.md)

qk is a set of agent skills that extends Claude Code, Codex and omp. Each skill is a workflow with a clear result, a clear authority boundary and a clear definition of done. You call a skill by name; it does not take over ordinary requests.

## Start here

- [Getting started](getting-started.md): install, call a skill, update, pin a release, uninstall.
- [Workflows](workflows.md): which skills to chain for an unclear idea, a clear change, a bug, a session switch or a release.
- [Case study: CSV export](case-study-csv-export.md): a worked feature from brainstorm and planning through an isolated worker, PR review, merge and shipping.

## Guides

- [qk-run runner](runner.md): opt-in automation from a request to a ready-for-review PR, with one plan-approval gate.
- [Preference hook](preference-hook.md): an opt-in hook that turns "from now on…" requests into proposals you approve.
- [Lean setup](lean-setup.md): measure and trim what your runtimes load into every session, alongside other kits.

## Reference

- [Runtimes](runtimes.md): support status, explicit-only settings, hook registration, known quirks and model selection.
- [Test evidence](evidence.md): dated records of what was checked, on which version, and the manual smoke checklist.

## Skills

| Skill | Use it to |
|---|---|
| [qk/brainstorm](skills/qk-brainstorm.md) | Compare approaches and recommend one |
| [qk/research](skills/qk-research.md) | Answer a decision question from primary sources |
| [qk/plan](skills/qk-plan.md) | Create, audit or revise a plan |
| [qk/cook](skills/qk-cook.md) | Implement a clear request or approved plan, with verification |
| [qk/debug](skills/qk-debug.md) | Find a root cause with evidence |
| [qk/test](skills/qk-test.md) | Run independent verification |
| [qk/handoff](skills/qk-handoff.md) | Hand work to a fresh session, or resume it |
| [qk/agent-coord](skills/qk-agent-coord.md) | Give a bounded task to a named agent and model |
| [qk/release-notes](skills/qk-release-notes.md) | Draft release notes and changelog entries |
| [qk/dogfood](skills/qk-dogfood.md) | Propose minimal instruction improvements from work evidence, without applying them |
| [qk/prefs](skills/qk-prefs.md) | Review recorded preference proposals and apply the ones you approve |
| [qk/commit](skills/qk-commit.md) | Commit scoped work; push and open a PR only when asked |

Pull-request review and scoring are handled by the companion skill [pr-orchestrator](https://github.com/dakiquang/pr-orchestrator), a separate project.

## Principles every skill follows

1. **Know what "done" means before starting**: result, what must not change, scope, acceptance evidence. Ask only for a decision the sources cannot answer.
2. **Delegating work is not delegating authority.** Editing code does not include commit, push, merge, tag, deploy or publish.
3. **A "done" report is not evidence.** Verify behaviour, revision or source.
4. **Decisions live outside the session**, in a plan or handoff file, not only in chat.
5. **Pick the process by what is missing.** Unclear direction → brainstorm; missing facts → research; clear work → cook. No mandatory pipeline.
6. **Continue within approved scope**; stop for a new decision, a blocker, or new authority.
7. **Extend the runtime, never take it over.** The runtime keeps its tools, plan mode, subagents, model settings and permissions; repository rules beat qk.
8. **Close every report consistently.** End with Done, Evidence, Not verified, Needs your decision, in that order.
