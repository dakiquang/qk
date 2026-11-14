# Getting started

[Tiếng Việt](../vi/getting-started.md) · [Docs index](README.md)

## 1. Install

qk is plain Markdown plus two small Python helpers; there is nothing to build. You need at least one supported runtime. The helpers used by `qk/commit` and `qk/prefs` need Python 3.9 or later, and the push identity check also needs the GitHub CLI `gh`.

### With `npx skills` (recommended)

[`npx skills`](https://github.com/vercel-labs/skills) copies the skill folders into each runtime's skills directory. It needs Node.js.

```bash
npx skills add dakiquang/qk -g -a claude-code codex qwen-code -y
```

- `-g` installs for your user rather than one project; `-a` picks the runtimes; `-y` skips the prompts.
- With more than one runtime, the files live once in `~/.agents/skills` and the other runtimes get symlinks to them. Codex's copy is `~/.agents/skills` itself, the user skills directory in Codex's documentation.
- **omp** has no target of its own. Its documentation lists `~/.agents/skills` and `~/.claude/skills` among the directories it reads, so an install for Codex or Claude Code also serves omp.
- If `CLAUDE_CONFIG_DIR` is set, the Claude Code copy goes to `$CLAUDE_CONFIG_DIR/skills` instead of `~/.claude/skills`.
- On Claude Code the skills keep their plain names, so you call `/qk-plan`, not `/qk:qk-plan`.
- If a skills directory already has a qk skill of the same name, for example a link from a manual install, `npx skills` replaces it. When switching from a manual install, remove its links first (see [Uninstall](#5-uninstall)) so no runtime keeps an old copy.

To pin a release, add its tag after `#` (releases from `v0.3.0` include the layout this method needs):

```bash
npx skills add 'dakiquang/qk#v0.3.0' -g -a claude-code codex qwen-code -y
```

`dakiquang/qk@<name>` does not select a version: `npx skills` reads the part after `@` as a skill name.

### Manual install (clone and link)

Use this when you want to run [`qk-run`](runner.md) or the validator, edit the skills, or work without Node.js. Clone once and link each skill folder into the skills directory of every runtime you use; `git pull` then updates them all.

```bash
(
  git clone https://github.com/dakiquang/qk ~/src/qk || exit 1
  dest=~/.claude/skills          # repeat for each runtime directory below
  set -- ~/src/qk/skills/qk-*
  for skill do
    [ -f "$skill/SKILL.md" ] || { echo "invalid or missing skill: $skill" >&2; exit 1; }
    target="$dest/$(basename "$skill")"
    if [ -e "$target" ] || [ -L "$target" ]; then
      echo "already exists: $target" >&2
      exit 1
    fi
  done
  mkdir -p "$dest" || exit 1
  for skill do
    ln -s "$skill" "$dest/$(basename "$skill")" || exit 1
  done
)
```

The block runs in a subshell: clone failure or a missing/invalid source stops it without exiting your interactive shell. It validates every skill and target before making links, and links nothing if a target already exists. Run it while no other process is installing skills into that directory; it is not a concurrent or rollback-capable installer.

| Runtime | Skills directory |
|---|---|
| Claude Code | `~/.claude/skills` |
| Codex | `~/.codex/skills` |
| omp | `~/.agents/skills` or `~/.omp/agent/skills` |
| Qwen Code | `~/.qwen/skills` |
| Orca | Nothing to install; it sees the skills of the agents it runs |

Some runtimes read more than one directory. Linking the same skill into two directories a runtime reads may list it twice; omp collapses links that resolve to the same folder. If in doubt, check the runtime's skill list after installing.

To try local edits of a clone through the `npx skills` layout instead, install from the clone's path: `npx skills add ~/src/qk -g -a claude-code -y`. A local install is a copy, so run the command again after each change.

Start a new session so the runtime discovers the skills.

## 2. Call a skill

| Runtime | Syntax | Example |
|---|---|---|
| Claude Code | `/qk-<name>` | `/qk-plan add a health-check endpoint` |
| Codex | `$qk-<name>` | `$qk-plan add a health-check endpoint` |
| omp | `/skill:qk-<name>` | `/skill:qk-plan add a health-check endpoint` |

In the docs a skill is written `qk/plan`; that is the name of the workflow, not something to type.

qk is configured for explicit invocation: it should not load merely because a request mentions planning, debugging or reviewing. See [Runtimes](runtimes.md) for the mechanisms, observed behaviour and unverified runtimes.

## 3. A first run

Try a read-only skill in any repository:

```text
/qk-brainstorm Should the app read its configuration from environment variables or a TOML file?
```

You should get a short problem statement, a table of options with what each gains and costs, the key assumptions, one recommendation and the decision left to you. Nothing is written to disk.

Then try the plan → cook loop on something small. See [Workflows](workflows.md).

Optional: the [preference hook](preference-hook.md) turns "from now on…" requests into proposals you review with `qk/prefs`. It is a separate, manual opt-in.

## 4. Update

With `npx skills`:

```bash
npx skills check
```

```bash
npx skills update -g -y
```

An install pinned with `#<tag>` stays on that tag; install again with a newer tag to move. An install from a local path cannot be checked or updated; run the same `npx skills add <path>` command again.

With a manual install:

```bash
git -C ~/src/qk pull
```

Links pick up the new version at the next session. Read the [changelog](../../CHANGELOG.md) for what changed.

Manual links point at the clone, so whatever is checked out is live in every runtime at the next session. To pin a release, check out its tag:

```bash
git -C ~/src/qk fetch --tags
```

```bash
git -C ~/src/qk checkout v0.3.0
```

To return to the latest on `main`:

```bash
git -C ~/src/qk checkout main
```

```bash
git -C ~/src/qk pull
```

## 5. Uninstall

With `npx skills`, remove the qk skills by name:

```bash
npx skills remove -g -y qk-agent-coord qk-brainstorm qk-commit qk-cook qk-debug qk-dogfood qk-handoff qk-plan qk-prefs qk-release-notes qk-research qk-test
```

With a manual install, remove only links you have verified point at your qk clone, never the whole skills directory. For example, inspect one link:

```bash
readlink ~/.claude/skills/qk-plan
```

If the output is the `skills/qk-plan` folder in your qk clone, remove that link:

```bash
rm ~/.claude/skills/qk-plan
```

Repeat for each owned link in the directories you installed into. Do not remove another installation's links or real directories. Delete `~/src/qk` only after removing its links and preserving any local work you need.

## 6. Check the kit

```bash
python3 scripts/validate.py
```

It checks folder and frontmatter names, explicit-only settings for Claude Code, omp and Codex, internal links and EN/VI documentation pairs. Personal-path and secret-pattern checks cover UTF-8 text files of any suffix outside `.git`, except the validator's own detection patterns. `QK_DENYLIST` is a UTF-8 file of literal terms (one per line); matching is case-insensitive with word-character boundaries and includes the validator itself. Binary files, filenames and Git history are outside these content checks. In CI, gitleaks scans the commit range of each push or pull-request event, not the full history. These are static checks; they do not prove that every runtime complies.
