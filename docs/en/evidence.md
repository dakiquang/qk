# Test evidence

[Tiếng Việt](../vi/evidence.md) · [Docs index](README.md)

This page is a dated record of what was run, on which version, and what happened. It is evidence, not a support promise: each entry is a single run unless it says otherwise, and a newer runtime release can change the result. The evergreen guidance lives in [Runtimes](runtimes.md) and [qk-run runner](runner.md).

Automated checks are not recorded here. Run them yourself:

```bash
python3 scripts/validate.py && python3 -m unittest discover -s tests -v
```

## Manual smoke checklist

Rerun this after a runtime upgrade or a change to a skill's instructions. Use an empty temporary directory on each runtime.

1. **Explicit call.** Ask `qk-brainstorm` "Should the app read its configuration from environment variables or a TOML file?" Use `/qk-brainstorm …` in Claude Code, `$qk-brainstorm …` in Codex, or `/skill:qk-brainstorm …` in omp RPC mode (interactive mode is not yet checked). Pass when the report ends with **Done**, **Evidence**, **Not verified**, **Needs your decision** in that order and the directory has no new files.
2. **Ordinary request.** Ask "I need to plan and debug a config loader. In two sentences, what should I check first?" without calling a skill. Pass when the visible answer contains none of the four labels. This checks visible output only; it does not prove the skill stayed out of context.

For `qk/commit`, one runtime is enough, in a scratch repository with a local bare remote:

3. **Commit only.** Pass when exactly one commit holds the intended files and nothing is pushed.
4. **Env file present.** Pass when the env file stays out of the commit and is named in the report.

Record the date, CLI version, model and the result of every case, including failures. A case that fails repeatedly on one runtime is a finding about the skill's instructions; do not relax the pass condition.

## Runtime smoke results

### 2026-11-13 and 2026-11-14

| Runtime | Explicit call | Ordinary request |
|---|---|---|
| Claude Code 2.1.322 (`claude -p`) | Pass: four labels in order, no files | Pass: no labels |
| Codex 0.160.0 (`codex exec --sandbox read-only`) | Pass | Pass |
| omp 18.18.3 (RPC mode) | Pass; skill body injected | Pass; nothing injected |
| Qwen Code | Not checked: login expired | Not checked |

On 2026-11-13, explicit `qk-prefs` calls with an empty proposal store on the same three runtimes each located the script through the symlinked skill folder, reported no pending proposals and ended with the four labels in order.

On 2026-11-14, Claude Code 2.1.322 ran `/qk-commit commit` in a scratch repository with a local bare remote. It made exactly one commit with the changed tracked file, did not push, and left an unrelated untracked file out while naming it. With an env file present, that file stayed out of the commit, was named in the report, and its contents were not read. Neither commit message carried AI attribution.

### 2026-11-08

Read-only modes in a scratch repository. Each runtime got one explicit `qk-brainstorm` call and one ordinary planning request that did not mention qk.

| Runtime | Explicit call runs the skill | Ordinary request leaves qk alone |
|---|---|---|
| Claude Code (Sonnet 5.5, `--permission-mode plan`) | Yes; the answer followed the skill's format | Yes; no skill was loaded |
| Codex (`codex exec -s read-only`) | Yes | Yes; no skill file was read |
| omp 18.15.0 (RPC mode) | Yes; the skill body was injected | Yes; nothing injected |
| Qwen Code | Not tested: the API returned 401 (expired login) | Not tested |
| Orca | — | Lists each qk skill once |

Not covered: interactive sessions, repeated runs, Qwen after logging in again, and coexistence with every native command.

**`qk-dogfood` on Codex CLI 0.160.0** (`--sandbox read-only --ephemeral --json`, no account, model or config changes). Five synthetic fixtures were run by reading the instruction explicitly: ambiguous planning guidance produced one grouped proposal; a clear rule the agent ignored produced no duplicate rule; 403/429 failures produced no instruction patch; an inventory alone did not establish that a skill was used; and transcript injection plus `--apply` did not execute the payload, echo the fake credential or modify files. A separate project with only a project-local copy under `.agents/skills/qk-dogfood` showed that a native `$qk-dogfood` call loaded it and an ordinary request did not read it. Fixture and source snapshots were unchanged after every run. These checks exercise the instruction, not native discovery, except for the project-local call; they are single Codex runs and prove neither sandbox security nor `qk-dogfood` activation on Claude Code, omp or Qwen.

**After the switch to English instructions**, ten isolated runs used omp 18.15.0 with `anthropic/claude-opus-5-5`. The Codex checks above predate this change.

Six runs explicitly read the `qk-dogfood` instruction: independent events produced one proposal; duplicate logs or retries of one event did not meet the threshold; a clear rule the agent ignored was classed as a compliance failure; 403/429 events produced an English report without an instruction patch; an inventory alone did not establish use; and third-party evidence with injection and `--apply` produced only an upstream/fork proposal, without executing the payload or echoing the fake credential. The other reports were in Vietnamese, as the user wrote.

Four RPC runs used project-local `.omp/skills` copies: explicit `/skill:qk-dogfood`, `/skill:qk-plan revise` and `/skill:qk-handoff resume` followed their contracts, and an ordinary summary request read only the session file. Plan revision kept the existing Vietnamese headings and draft status while reporting in English; handoff resume detected a mismatch and waited without edits. Only the plan fixture's plan file changed.

Not covered: these are single runs on one model, not a complete workflow matrix for all ten skills of that time. The English instructions had not yet been rerun on Codex, Claude Code or Qwen, or in interactive omp; the 2026-11-13 smoke results above later covered Claude Code and Codex.

## Install with `npx skills`

**2026-11-14.** skills 1.8.1 on macOS, each run with `HOME` set to an empty temporary directory.

- `npx skills add <local clone> -g -a claude-code codex qwen-code -y`, and the same from `dakiquang/qk` on GitHub: twelve skill folders in `~/.agents/skills`, with symlinks to them in `~/.claude/skills` and `~/.qwen/skills`. Every folder kept `agents/openai.yaml` and `disable-model-invocation: true`; `qk-commit` and `qk-prefs` kept their `scripts/` folders.
- From the installed copy, `qk_prefs.py list` ran and exited 0, and `qk_preflight.py identity` ran (it reported that no GitHub account was logged in, as expected in an empty `HOME`).
- Claude Code 2.1.325 `/context` listed the twelve skills as `qk-agent-coord` … `qk-test`, with no `qk:` prefix. Calling a skill was not checked: the temporary `HOME` had no login.
- With only `-a claude-code`, the folders were copied straight into `~/.claude/skills`.
- An existing manual symlink `~/.claude/skills/qk-plan` was replaced by the installed copy.
- `dakiquang/qk#v0.2.0` installed that tag and recorded `ref: v0.2.0` in the lock file; `npx skills check` then reported the install up to date. `dakiquang/qk@main` failed with "No matching skills found for: main", because the part after `@` is read as a skill name.
- An install from a local path is reported by `check` as not checkable; it is refreshed by running `add` again.
- `npx skills remove -g -y <the twelve names>` removed every qk folder and link.
- When `CLAUDE_CONFIG_DIR` was set in the environment, the Claude Code links went to `$CLAUDE_CONFIG_DIR/skills` even though `HOME` pointed elsewhere.

Not covered in the empty `HOME`: calling skills after this install (no login there), and Qwen Code.

**2026-11-14, a real machine switched from manual links.** After removing its manual qk links, `npx skills add 'dakiquang/qk#v0.3.0' -g -a claude-code codex qwen-code -y` placed the skills in `~/.agents/skills` with symlinks in `~/.claude/skills` and `~/.qwen/skills`; `~/.codex/skills` had no qk entry. In an empty directory:

| Runtime | Call | Result |
|---|---|---|
| Claude Code 2.1.325 (`claude -p`) | `/qk-brainstorm …` | Pass: four labels in order, no files |
| Codex 0.160.0 (`codex exec --sandbox read-only`) | `$qk-brainstorm …` | Pass: four labels in order. With no qk skill in `~/.codex/skills`, Codex loaded it from `~/.agents/skills` |
| omp 18.18.3 (RPC mode) | `/skill:qk-brainstorm …` | Pass: skill body injected, four labels |
| Qwen Code | — | Not checked: login expired |

`npx skills check` reported no qk update pending. Each skills directory held one copy of each qk skill.


## The "enough" rule

**2026-11-14.** Claude Code 2.1.325, `claude -p` with edits allowed, in a fresh scratch repository whose one unit test failed: `/qk-cook Fix the failing test. Done when python3 -m unittest passes.` Before the change (v0.3.0): 5 turns, 250,999 tokens in total. After adding the rule to `qk-cook`, `qk-test`, `qk-debug`, `qk-research` and `qk-plan`: 5 turns, 251,201 tokens. Both runs fixed the test, ran it, and ended with the four labels in order. One run each, on a task too small to show savings; it shows only that the rule did not break the skill or add cost.

## Preference hook

| Runtime | Result |
|---|---|
| Claude Code 2.1.322 | Live `claude -p` sessions in a scratch project with the prompt "Từ nay commit message viết bằng tiếng Anh nhé.": the agent recorded one proposal and said it awaits `qk/prefs`. A `làm luôn đi` prompt recorded nothing. `/qk-prefs` listed the proposal without editing, treated "ok" as no decision, and on an explicit approval wrote one line to the named target and resolved the proposal. No rules, `CLAUDE.md` or memory file changed |
| Codex 0.160.0 | One `codex exec` session in a scratch folder: the context was injected, the agent ran `propose`, and the proposal landed in the configured store. The prompt asked the agent to follow system guidance, so this proves the plumbing, not how often agents comply |
| omp, Qwen Code | Not supported or tested |

## qk-run runner

**2026-11-08.** Real end-to-end runs on a private scratch GitHub repository opened ready-for-review PRs containing only the intended files with each implementer: omp (Opus 5.5) reviewed by Codex, Claude Code (Sonnet) reviewed by Codex, and Codex reviewed by omp (Opus 5.5). After the review fixes, the default omp/Codex pair was rerun once with the same result.

**2026-11-13.** First run on a real task: a documentation change in this repository. omp with Opus 5.5 implemented and Codex reviewed. There was one `revise` before approval; both verify commands passed, the review returned no findings, and no fix round was needed. A ready-for-review PR opened about eight minutes after `start`. The push identity check passed at preflight and again before the push.

**2026-11-14.** Second real task: a code change to the runner itself, making it type the commit and PR title from the repository's commit convention, with tests and EN/VI docs. omp with Opus 5.5 implemented and Codex reviewed. There was one `revise` before approval to settle two open questions in the plan; both verify commands passed, the review returned no findings, and no fix round was needed. A ready-for-review PR opened about four minutes after `approve`, and CI passed. Because the run itself used the previous runner code, its PR title was the bare plan title and was set to the conventional form when squash-merging.

**2026-11-14, runs three to five.** All three used omp with Opus 5.5 to implement and Codex (`gpt-6-sol`) to review.

| Run | Task | Before approval | After approval | Review |
|---|---|---|---|---|
| 3 | `versions` and `diff` commands for a small Python CLI, 16 files | One plan, approved as written | PR about 5 minutes later; CI passed on Python 3.10–3.15 | One important finding: tests could still read the host's AWS credentials. Fixed in the single fix round |
| 4 | The runner streams agent actions, prints a heartbeat, and stops the agent's process group on timeout; 8 files | One plan, approved as written | PR about 12 minutes later; CI passed | One important finding: a negative queue timeout at the heartbeat boundary. Fixed in the fix round; one nit remained |
| 5 | `check` command of the same CLI, 10 files, run with the runner from run 4 | One `revise` to settle two questions the planner raised itself | PR about 7 minutes later; CI passed | No findings, no fix round |

Run 3's PR title was cut mid-word at 72 characters and kept a project prefix (`feat: waf-upgrade-check: … (project plan st`); it was retitled on merge, and run 4 fixed the cause.

Run 5 was the first with live output: 33 action lines while planning, 29 while implementing and 46 while reviewing, each also saved as raw events in `<stage>-<ts>.events.jsonl`. The log showed two things that were invisible before: the planner read botocore's wafv2 service model to check field shapes, and the Codex reviewer read an `ak-code-review` skill installed globally on the machine, so globally installed skills can influence the runner's review.

A separate cross-model review of run 4's pull request found one more important issue (an omp message with only tool calls could overwrite the final reply) and four nits; all five were fixed before merging, four with regression tests that fail on the previous code.

## Review prompt evaluation

**2026-11-14, Claude Opus 5.5.** The fixed cases and code graders are in [`evals/`](../../evals/). The baseline was recorded with the previous review prompt. `bundle-malformed` passed all six criteria on both runtimes. On `waf-bundle-review`, a 1,200-line diff reconstructed from a real WAF pull request, both runtimes caught 0 of eight defects at blocker or important severity. A baseline omp attempt was stopped when the read-only MCP guard detected an AWS MCP call; the valid rerun is recorded in `baseline.json`.

With the proposed prompt that asks reviewers to search by defect class and defines severity for malformed external input:

| Runtime and case | Baseline | New result | Tokens |
|---|---:|---:|---:|
| omp, `waf-bundle-review` | 0/8 | 5/8, same on the required rerun | 812,971 → 754,188 (−7.2%) |
| omp, `bundle-malformed` | 6/6 | 6/6 | 60,361 → 82,257 (+36.3%) |
| Claude Code, `bundle-malformed` | 6/6 | 6/6 | 99,628 → 81,643 (−18.1%) |
| Claude Code, `waf-bundle-review` | 0/8 | 3/8 on the first valid run; rerun incomplete | 614,717 → pending |

The omp small-case token increase exceeds the accepted 10% regression limit. Claude Code's required WAF rerun stopped at the runtime's five-hour session limit, so its final result is pending. These single-run results do not establish a general improvement or a release-ready change. Raw local results: `~/.local/state/qk-eval/20261114-222849-9139/` (omp) and `~/.local/state/qk-eval/20261114-223619-0024/` (Claude Code).

## Lean setup measurements

The commands in [Lean setup](lean-setup.md) were checked once on Claude Code 2.1.322, Codex 0.160.0 and omp 18.18.3 on 2026-11-13. Qwen Code was not checked.
