# qk

[Tiếng Việt](README.vi.md) · [Documentation](docs/en/README.md) · [End-to-end case study](docs/en/case-study-csv-export.md)

A small personal toolkit for evidence-based decisions, bounded plans, implementation with verification and reliable handoffs between AI coding sessions.

qk is an **extension of Claude Code, Codex and omp**, not a replacement. Skills are configured for explicit invocation: ordinary planning or debugging requests stay with the runtime. Native tools, plan mode, subagents, model choices, permissions and repository rules remain in control.

> Personal project, not affiliated with any company, no support commitment. The repository is currently private; installation requires access.

## Pick the skill you need

| Skill | Result |
|---|---|
| [qk/brainstorm](docs/en/skills/qk-brainstorm.md) | 2–4 approaches, trade-offs and a recommendation |
| [qk/research](docs/en/skills/qk-research.md) | A decision question answered with sources and controlled experiments |
| [qk/plan](docs/en/skills/qk-plan.md) | Create, audit or revise a verifiable plan |
| [qk/cook](docs/en/skills/qk-cook.md) | Implement a clear request or approved plan; verify and self-review |
| [qk/debug](docs/en/skills/qk-debug.md) | Reproduction, verified root cause and smallest proposed fix |
| [qk/test](docs/en/skills/qk-test.md) | Independent checks, classified failures and verification gaps |
| [qk/handoff](docs/en/skills/qk-handoff.md) | Save session context or resume it with drift checks |
| [qk/agent-coord](docs/en/skills/qk-agent-coord.md) | A bounded task on the agent/model you name, with checked results |
| [qk/release-notes](docs/en/skills/qk-release-notes.md) | Traceable release-note and changelog drafts, not publication |
| [qk/dogfood](docs/en/skills/qk-dogfood.md) | Evidence-based instruction improvement proposals in chat; no changes applied |
| [qk/prefs](docs/en/skills/qk-prefs.md) | Recorded preference proposals reviewed one by one; only approved ones written to the target you choose |
| [qk/commit](docs/en/skills/qk-commit.md) | Scoped commits; push and PR only when requested, after an identity check |

Each skill states its result, authority and done criteria. Skills never call each other and there is no mandatory pipeline. Implementing code does not grant authority to commit, push, open a PR, merge, tag, deploy or publish.

For end-to-end automation, the opt-in [qk-run runner](docs/en/runner.md) drives Claude Code, Codex or omp from a request to a ready-for-review PR: it stops once for plan approval, verifies with the plan's commands, gets a cross-model review, and never merges.

Canonical skill instructions and worker prompt templates are written in English. Human documentation stays available in English and Vietnamese. Reports follow the user's language unless the user or repository specifies another; edits preserve an existing artifact's language and format. Commands, paths, identifiers and fixed machine strings are not translated.

PR review and scoring use the companion [pr-orchestrator](https://github.com/dakiquang/pr-orchestrator), which remains a separate repository and installation.

## Start

[Install once and link the skill folders](docs/en/getting-started.md), then open a new runtime session. No package installation or build is needed.

| Runtime | Example invocation |
|---|---|
| Claude Code | `/qk-plan audit plans/feature.md` |
| Codex | `$qk-plan audit plans/feature.md` |
| omp | `/skill:qk-plan audit plans/feature.md` (interactive or RPC) |

`qk/plan` is the conceptual name, not literal CLI syntax. In the observed omp version, `omp -p` does not expand `/skill:`. Qwen execution and explicit-only behaviour remain unverified. See [runtime evidence and limits](docs/en/runtimes.md); single successful checks are not certification.

## Read more

- [Getting started](docs/en/getting-started.md): installation, invocation, updates and safe removal.
- [Workflows](docs/en/workflows.md): choose a process by what is missing.
- [Case study: CSV export from idea to shipped PR](docs/en/case-study-csv-export.md): prompts, coordinator/worker contracts, PR review and release gates.
- [Runtimes](docs/en/runtimes.md): native boundaries, model selection and observed support.
- [Changelog](CHANGELOG.md).

## Validate

```bash
python3 scripts/validate.py
```

Checks skill metadata, explicit-invocation settings, internal links, EN/VI documentation pairs, personal paths and secret-like strings. Optional `QK_DENYLIST` points to literal terms checked in UTF-8 text contents outside `.git`, including the validator itself; binary files and filenames are not checked. CI runs gitleaks on the commit range of each push/PR event, not a guaranteed full-history scan. Static checks do not prove runtime isolation.

## License

[MIT](LICENSE). Built by [Quang Dang](https://quangdk.com).
