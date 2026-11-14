# qk

[Tiếng Việt](README.vi.md) · [Documentation](docs/en/README.md) · [Changelog](CHANGELOG.md)

Agent skills for Claude Code, Codex and omp that add a small set of disciplined workflows on top of the runtime you already use: compare approaches, plan, implement with verification, debug, test, hand off between sessions, coordinate a second model, commit, and draft release notes.

qk extends the runtime and does not replace it. Every skill runs only when you call it by name, as configured and checked on Claude Code, Codex and omp. Ordinary requests, plan mode, subagents, model settings, permissions and repository rules stay with the runtime.

> **Status.** A personal project, not affiliated with any company, published as is. It is maintained for its author's own work and versioned with tags, but there is no support commitment. Issues and pull requests are welcome; a reply is not guaranteed.

## Why qk

> **Understand enough to decide.** Getting code to run is easy now; what stays hard is seeing clearly enough to make the call. qk optimizes only for that.

Most kits help AI do more on its own. qk hands back what you need to decide, through three principles:

- **Three roles: make, check, decide.** Whoever makes a change is not its final checker, and authority to commit, merge or publish stays with you.
- **Evidence, not claims.** Reports separate what was seen from what was only told, and say what was not checked. Every report ends with Done, Evidence, Not verified, Needs your decision.
- **Enough.** Check only what could change the decision, once; no mandatory pipeline; twelve skills, about 50 KB, nothing loaded until you call a skill.

Read the [philosophy](docs/en/philosophy.md) for what each principle does and does not mean.

## Skills

| Skill | Result |
|---|---|
| [qk/brainstorm](docs/en/skills/qk-brainstorm.md) | Two to four approaches, their trade-offs and a recommendation |
| [qk/research](docs/en/skills/qk-research.md) | A decision question answered from primary sources and controlled experiments |
| [qk/plan](docs/en/skills/qk-plan.md) | A plan created, audited or revised, with checkable completion criteria |
| [qk/cook](docs/en/skills/qk-cook.md) | A clear request or approved plan implemented, verified and self-reviewed |
| [qk/debug](docs/en/skills/qk-debug.md) | A reproduction, a verified root cause and the smallest proposed fix |
| [qk/test](docs/en/skills/qk-test.md) | Independent checks, classified failures and verification gaps |
| [qk/handoff](docs/en/skills/qk-handoff.md) | Session context saved, or resumed with drift checks |
| [qk/agent-coord](docs/en/skills/qk-agent-coord.md) | A bounded task run on the agent and model you name, with the result checked |
| [qk/commit](docs/en/skills/qk-commit.md) | Scoped commits; push and PR only when asked, after an account check |
| [qk/release-notes](docs/en/skills/qk-release-notes.md) | Traceable release-note and changelog drafts, never published |
| [qk/dogfood](docs/en/skills/qk-dogfood.md) | Evidence-based proposals to improve instructions, never applied |
| [qk/prefs](docs/en/skills/qk-prefs.md) | Recorded preference proposals reviewed one by one; only approved ones are written |

Two opt-in tools sit beside the skills:

- **[qk-run](docs/en/runner.md)** drives one task from request to a ready-for-review pull request: one plan-approval gate, the plan's own checks, a review by a different model family, and never a merge.
- **[The preference hook](docs/en/preference-hook.md)** turns "from now on…" requests into proposals you review with `qk/prefs`.

Pull-request review and scoring live in the companion project [pr-orchestrator](https://github.com/dakiquang/pr-orchestrator).

## Quick start

Install for the runtimes you use with one command (needs Node.js):

```bash
npx skills add dakiquang/qk -g -a claude-code codex qwen-code -y
```

[Getting started](docs/en/getting-started.md) covers pinning a release, updating, removing, and a manual install without Node.js. Then open a new session and call a skill:

| Runtime | Example |
|---|---|
| Claude Code | `/qk-brainstorm Should the app read its configuration from environment variables or a TOML file?` |
| Codex | `$qk-brainstorm …` |
| omp | `/skill:qk-brainstorm …` (RPC mode checked; interactive mode not yet checked) |

The docs write a skill as `qk/brainstorm`; that is the workflow's name, not something to type. Support differs by runtime and Qwen Code is not yet checked; see [Runtimes](docs/en/runtimes.md).

## Documentation

- [Getting started](docs/en/getting-started.md): install, call, update, pin a release, uninstall.
- [Workflows](docs/en/workflows.md): which skills to use for an unclear idea, a clear change, a bug, a session switch or a release.
- [Case study](docs/en/case-study-csv-export.md): one feature from idea to merged pull request.
- [Runtimes](docs/en/runtimes.md) and [Test evidence](docs/en/evidence.md): what each runtime supports and what was actually checked.
- [Full index](docs/en/README.md).

Skill instructions are written in English. Human documentation is available in English and Vietnamese. Reports follow the language you write in.

## Validate

```bash
python3 scripts/validate.py
python3 -m unittest discover -s tests
```

The validator checks skill metadata, explicit-invocation settings, internal links, English and Vietnamese page pairs, personal paths and secret-like strings; Static checks do not prove runtime isolation; [Getting started](docs/en/getting-started.md#6-check-the-kit) lists the other limits. CI runs both commands and a gitleaks scan.

## License

[MIT](LICENSE). Built by [Quang Dang](https://quangdk.com).
