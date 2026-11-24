# Runtime status

[Tiếng Việt](../vi/runtime-status.md) · [Docs index](README.md) · [Overnight runs](overnight.md) · [Runner](runner.md)

See what the runner (and any other tool you list) is doing from inside omp, Claude Code or Codex. You also get a reminder when cards wait for your decision, and you can decide them in the chat. The adapters only display and ask. Decisions still go through `qk decide`, on your own stated choice.

Each adapter reads the same commands:

- `qk run status --line`: one line per run that is working, stopped mid-stage, waiting for plan approval or for a usage limit, plus `+N queued`. Status lines leave out runs nobody touched for a day, and several runs left mid-stage share one line; `--json` lists them all. See [Runner](runner.md#use).
- `qk brief --pending`: one line when cards wait for a decision, otherwise nothing. `qk brief --json` gives the cards to a skill or an extension. See [CLI contract](cli-contract.md#commands).
- `adapters/status_lines.py`: runs every command listed in `~/.config/qk/status-commands`, one per line (default: `qk run status --line`). Each command gets 1 second; output is cached for 5 seconds. Add other tools' status commands to that file; for example, qk-harness has `qk-harness status --line`.

Nothing below is installed for you. Each step changes your own runtime settings, so back them up first. The adapters add to what you already use and replace nothing.

| | Live status | Reminder at session start | Decide in the chat |
|---|---|---|---|
| omp 19.0.0 | yes, in the status bar every 15 s | notification | `/qk-brief` (select dialog), or the skill |
| Claude Code | yes, status line refreshed every 10 s | yes | skill `qk-morning`, with question dialogs |
| codex-cli 0.160.0 | no: `[tui] status_line` only takes built-in items | yes, as a warning line | skill `qk-morning`, in plain text |

## omp

```bash
ln -s <qk>/adapters/omp/qk-status.ts ~/.omp/agent/extensions/qk-status.ts
```

Install the `qk-morning` skill like the other qk skills ([Getting started](getting-started.md)); omp reads `~/.agents/skills`.

The extension sets a `qk` status entry from `status_lines.py` every 15 seconds and after each agent turn. When a session starts with cards waiting, it shows a notification. `/qk-brief` runs `qk sync`, then shows each card in a select dialog with exactly the choices `qk decide` accepts, plus `skip`. It asks for the merge method only when the repository allows several. Other extensions (for example Orca's) keep working.

## Claude Code

In `~/.claude/settings.json`, wrap the status line you already have. The words after the script path are your current command. Then add the hook:

```json
"statusLine": {
  "type": "command",
  "refreshInterval": 10,
  "command": "/bin/sh <qk>/adapters/claude/statusline.sh <your current status line command>"
},
"hooks": {
  "SessionStart": [{"hooks": [{"type": "command", "command": "python3 <qk>/adapters/session_start.py"}]}]
}
```

Install the `qk-morning` skill like the other qk skills ([Getting started](getting-started.md)).

The status line prints your current line first, then one line per qk item. The hook prints nothing when nothing waits. Otherwise it shows you the reminder and up to three status lines (`systemMessage`). Only when cards wait for a decision does it add that one line, plus a pointer to `qk-morning`, to the session's context: the only part that costs tokens. Whether the desktop app's Code tab shows the custom status line has not been checked yet.

## Codex

In `~/.codex/hooks.json`:

```json
{"hooks": {"SessionStart": [{"hooks": [{"type": "command", "command": "python3 <qk>/adapters/session_start.py"}]}]}}
```

Codex reads the `qk-morning` skill from `~/.agents/skills` ([Getting started](getting-started.md)). Codex skips new or changed hooks until you trust them with `/hooks`. Codex shows `systemMessage` as a warning line. Keep your existing `notify` setting as it is; this adapter does not use it.

## Morning

Invoke the skill by name, for example `/qk-morning` in Claude Code, `$qk-morning` in Codex, or `/qk-brief` in omp. It runs `qk sync`, then goes card by card. It records only the choices you state, and ends with the four-line report. `abort-later` and `resume-later` only record your intent; you still run `qk run abort` or `qk run resume`.
