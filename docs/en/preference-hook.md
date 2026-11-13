# Preference hook

[Tiếng Việt](../vi/preference-hook.md) · [Docs index](README.md)

You often tell an agent something meant to last: "from now on, commit messages in English", "never amend a pushed commit". The runtime forgets it, or the agent writes it straight into memory without asking. The opt-in preference hook sits between the two. When a prompt contains a lasting-preference phrase, the hook asks the agent to record a **proposal** in a local file and carry on with the task. Nothing reaches memory, rules, `CLAUDE.md` or `AGENTS.md` until you approve it.

> **Status:** the hook and the proposal store are [`scripts/qk_prefs.py`](../../scripts/qk_prefs.py), tested by [`tests/test_qk_prefs.py`](../../tests/test_qk_prefs.py). You review proposals with [qk/prefs](skills/qk-prefs.md) ([example 5](#5-decide-on-a-proposal)). It works with Claude Code and Codex; see [Runtimes](runtimes.md#preference-hook) for what has been checked on each.

The hook only adds a reminder to the prompt. It cannot make the agent record anything, and it never decides what counts as a preference: the agent judges, and you approve.

## 1. What triggers it

The hook looks for phrases that state a standing rule, in Vietnamese and English. Common words such as "always", "never", "by default" and "mặc định" count only at the start of a sentence or after a lead-in such as "please", "you should" or "hãy", because elsewhere they usually describe the task at hand.

| Prompt | Reminder? | Why |
|---|---|---|
| `Từ nay commit message viết bằng tiếng Anh` | Yes | "từ nay" (from now on) |
| `Mặc định trả lời bằng tiếng Việt` | Yes | "mặc định" (by default) |
| `Never amend a pushed commit` | Yes | "never" starts the sentence |
| `Please always use pnpm` | Yes | "always" after "please" |
| `Next time, check the changelog first` | Yes | "next time," |
| `This function never returns` | No | "never" in the middle of a sentence |
| `Use a dict instead of a list here` | No | "instead of" is not a cue: it is usually a one-off choice |
| `Rename it, by default the arg is None` | No | "by default" after a comma describes code |
| `Lần sau mình làm tiếp nhé` | No | "lần sau" counts only with "nhớ", "hãy", "đừng", "phải", "luôn" or "cứ" |
| `làm luôn đi` | No | A bare "luôn" usually means "right away". Only "luôn luôn" (always) counts |
| `never mind, revert that` | No | "never mind" is excluded |
| ``Rename `alwaysRetry` to `retry` `` | No | Inline code and fenced code blocks are ignored |
| `> from now on use tabs` (a quoted line) | No | Quoted lines are ignored |
| `/qk-plan từ nay dùng pnpm` | No | Skill and slash-command invocations are skipped |

Because the trigger is a phrase list, it still produces false positives (`Always the same error here` matches because "always" starts the sentence; `See you next time, bye` matches "next time,") and misses preferences worded differently (`I prefer short commit subjects`, `Dùng vitest thay vì jest`). Only the first 4,000 characters of a prompt are scanned, so a preference stated at the end of a long message is missed. A false positive costs one ignored reminder; the agent decides whether anything is worth recording. The full phrase list is `CUE_RE` in the script, and the test cases in `POSITIVE`/`NEGATIVE` show the intended behaviour.

## 2. Try the hook without enabling it

Pipe a hook payload in by hand. A match prints the reminder as Claude Code hook JSON; no match prints nothing.

```bash
echo '{"prompt":"Từ nay commit message viết bằng tiếng Anh"}' | python3 ~/src/qk/scripts/qk_prefs.py hook --runtime claude
```

```bash
echo '{"prompt":"làm luôn đi"}' | python3 ~/src/qk/scripts/qk_prefs.py hook --runtime claude
```

The paths assume the clone location from [Getting started](getting-started.md).

## 3. Enable it in one project first

qk never edits runtime configuration. Add the hook yourself, and start with a single test project so other sessions are unaffected. In that project's `.claude/settings.local.json`:

```json
{
  "hooks": {
    "UserPromptSubmit": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "python3 ~/src/qk/scripts/qk_prefs.py hook --runtime claude",
            "timeout": 5
          }
        ]
      }
    ]
  }
}
```

If the file already has a `hooks` block, add the `UserPromptSubmit` entry to it instead of replacing the block. Start a new session. To enable it everywhere later, put the same entry in `~/.claude/settings.json`. To disable it, remove the entry.

**Codex** uses the same shape. Put the same JSON in the project's `.codex/hooks.json`, or in `~/.codex/hooks.json` for every project, with `--runtime codex`. If the file already exists, merge the entry instead of replacing the file. Then open Codex and run `/hooks` to review and trust it, because Codex skips untrusted hooks.

Each prompt starts one short Python process. The latency check in the test file asserts that the hook adds less than 50 ms on top of a bare interpreter start; it runs on local machines only and is skipped in CI.

## 4. What the agent records

Say in the session: `Từ nay commit message viết bằng tiếng Anh`. The agent gets the reminder and, if it judges the request lasting, runs something like:

```bash
python3 ~/src/qk/scripts/qk_prefs.py propose --stdin <<'QK_PREF'
{"scope": "global", "title": "Commit message language", "content": "Write commit messages in English.", "quote": "Từ nay commit message viết bằng tiếng Anh"}
QK_PREF
```

The JSON goes through a quoted heredoc, so apostrophes, `$` or backticks in your words need no shell escaping. The same fields also work as flags (`--scope`, `--title`, `--content`, `--quote`) for typing by hand.

`"scope": "project"` is for preferences that only apply to the current repository; the project name defaults to the current folder name, so two repositories with the same folder name share it. Proposing the same content again returns the existing ID instead of adding a duplicate. See `--help` on each subcommand for the limits.

List what is waiting:

```bash
python3 ~/src/qk/scripts/qk_prefs.py list
```

Each line is one JSON proposal, for example:

```json
{"id": "2cd33227", "created": "2026-11-13T15:59:32+07:00", "status": "pending", "scope": "global", "project": "", "title": "Commit message language", "content": "Write commit messages in English.", "quote": "Từ nay commit message viết bằng tiếng Anh"}
```

Proposals live in `~/.local/state/qk/preferences-pending.jsonl` (or `$XDG_STATE_HOME/qk/`, or `$QK_PREFS_STATE_DIR` when set). The file is created with mode `0600`, outside any repository, because it holds your own words. The reminder tells the agent not to record secrets or customer data, but that is an instruction, not a filter: read proposals before applying them. Writes are serialized with a file lock on macOS and Linux; on Windows the script runs without a lock, so do not record or resolve proposals from two sessions at the same time there.

## 5. Decide on a proposal

Call `/qk-prefs`. It shows the pending table, suggests a target for each proposal, and writes only the ones you approve; see [qk/prefs](skills/qk-prefs.md) for an example session.

To do the same by hand, copy a proposal's `content` into the memory, rules or `AGENTS.md` file where it belongs, and then mark it:

```bash
python3 ~/src/qk/scripts/qk_prefs.py resolve 2cd33227 applied --target "~/.claude/rules/development-rules.md"
```

Or drop it:

```bash
python3 ~/src/qk/scripts/qk_prefs.py resolve 2cd33227 dismissed
```

A proposal can be resolved only once; resolving it again fails with `already applied` or `already dismissed`. `list --all` shows resolved proposals too.

## Why it is built this way

- **Proposals, not writes.** Agents misread one-off requests as rules. A pending file keeps every lasting change behind your approval, which matches qk's rule that delegating work does not delegate authority.
- **A phrase list, not intent detection.** It is cheap, local and predictable. The agent does the judging; the hook only makes sure the agent is asked.
- **Python standard library.** qk already needs Python for its validator and runner; the hook adds no dependency.

The idea of detecting standing preferences and holding them for consent comes from [personal-brain-style](https://github.com/nghiacr002/personal-brain-style) (MIT). qk's version is a separate implementation.
