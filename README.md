# qk

[Tiếng Việt](README.vi.md)

A small set of agent skills for the way I actually work: decide with evidence, plan before large changes, implement with verification, hand work across sessions, and keep the person in charge of anything that leaves the machine.

qk extends Claude Code, Codex and omp; it does not replace them. Every skill is **configured to run only when you call it by name**, not because a request happens to mention planning or debugging. Your runtime keeps its own tools, plan mode, subagents, model settings and permissions.

> Personal project, not affiliated with any company, no support commitment.

## Skills

| Skill | Use it to | Writes |
|---|---|---|
| `qk/brainstorm` | Compare approaches, trade-offs and assumptions; recommend one | Nothing by default |
| `qk/research` | Answer a decision question from primary sources and controlled experiments | Nothing, or the evidence section of a plan |
| `qk/plan` | Create, audit or revise a plan with sources, decisions and done-criteria | The plan file only |
| `qk/cook` | Implement a clear request or approved plan, then verify and self-review | Files in scope; no commit, push or release unless asked |
| `qk/debug` | Find a root cause with a reproduction and evidence chain | Nothing by default |
| `qk/test` | Run independent verification and report real results | Nothing |
| `qk/handoff` | Write a handoff for a fresh session, or resume one and check for drift | The handoff file only |
| `qk/agent-coord` | Give a bounded task to a named agent and model, then check the result | The worker's own worktree |
| `qk/release-notes` | Draft release notes and changelog entries from commits and PRs | The draft only; no tag or release |

Each skill states its **result, authority and done-criteria** at the top. Skills never call each other; when a next step makes sense they name the command for you to run.

For pull-request review and scoring, use the companion skill [pr-orchestrator](https://github.com/dakiquang/pr-orchestrator). It stays a separate project; `qk/cook` and `qk/agent-coord` point to it by name.

## How to call a skill

| Runtime | Example | Explicit-only mechanism |
|---|---|---|
| Claude Code | `/qk-plan` | `disable-model-invocation: true` |
| Codex | `$qk-plan` | `agents/openai.yaml` → `allow_implicit_invocation: false` |
| omp | `/skill:qk-plan` (interactive or RPC; `omp -p` does not expand `/skill:` for any skill) | `disable-model-invocation: true` |
| Qwen Code | `/qk-plan` | not verified yet |

Orca runs these agents in its terminals and sees the skills installed for each agent.

These settings tell each runtime not to load a skill on its own; Claude Code documents that its setting also keeps the skill out of subagents. The intent: qk never takes over a request you did not route to it. Tested results are in Support status.

## Install

Clone once and link each skill folder into the skills directory of the runtimes you use. Links keep every runtime on the same source; `git pull` updates all of them.

```bash
git clone https://github.com/dakiquang/qk ~/src/qk
dest=~/.claude/skills            # or ~/.codex/skills, ~/.agents/skills, ~/.omp/agent/skills, ~/.qwen/skills
mkdir -p "$dest"
collision=0
for skill in ~/src/qk/skills/qk-*; do
  target="$dest/$(basename "$skill")"
  if [ -e "$target" ] || [ -L "$target" ]; then echo "already exists: $target"; collision=1; fi
done
if [ "$collision" = 0 ]; then
  for skill in ~/src/qk/skills/qk-*; do ln -s "$skill" "$dest/$(basename "$skill")"; done
fi
```

The script checks every target first and links nothing if any of them already exists, so an existing skill or folder is never replaced or written into. Use one install location per runtime; some runtimes read several directories and would otherwise list a skill twice. Remove a skill by deleting its link.

Start a new session after installing so the runtime discovers the skills.

## Support status

Structure and invocation settings are checked by `scripts/validate.py`. Live checks, 2026-11-08, in a scratch repository with read-only modes, one explicit call (`qk-brainstorm`) and one ordinary planning request per runtime:

| Runtime | Explicit call runs the skill | Ordinary request leaves qk alone | Notes |
|---|---|---|---|
| Claude Code (Sonnet 5.5, plan mode) | Yes | Yes, no skill loaded | |
| Codex (`codex exec -s read-only`) | Yes | Yes, no skill file read | |
| omp 18.15.0 (RPC) | Yes | Yes, no skill injected | `omp -p` passes `/skill:` through as plain text for every skill |
| Qwen Code | Not tested | Not tested | Recognised `/qk-brainstorm` as a skill, then the API returned 401 (expired login); Qwen also wrote a temporary args file under `.qwen/tmp` in plan mode |
| Orca | — | — | Lists each qk skill once |

These are single runs, not certification. Coexistence with each runtime's native commands beyond these requests has not been tested.

## Validate

```bash
python3 scripts/validate.py
```

Checks folder and frontmatter names, explicit-invocation settings for Claude Code, omp and Codex, internal links, personal paths and secret-like strings. Set `QK_DENYLIST` to a file of terms that must never appear in the repository. CI also runs gitleaks over the full history.

## License

[MIT](LICENSE). Built by [Quang Dang](https://quangdk.com).
