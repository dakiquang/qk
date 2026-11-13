# Getting started

[Tiếng Việt](../vi/getting-started.md) · [Docs index](README.md)

## 1. Install

qk is plain Markdown: no build and no package to install. Clone it once and link each skill folder into the skills directory of every runtime you use. All runtimes then read the same files, and `git pull` updates them all.

You need `git` and at least one supported runtime. The optional scripts (`qk_run.py`, `qk_prefs.py`, `qk_preflight.py` and the validator) need Python 3.9 or later; `qk-run` and the push identity check also need the GitHub CLI `gh`.

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

```bash
git -C ~/src/qk pull
```

Links pick up the new version at the next session. Read the [changelog](../../CHANGELOG.md) for what changed.

Skills are symlinks to the clone, so whatever is checked out is live in every runtime at the next session. To pin a release, check out its tag (see the [changelog](../../CHANGELOG.md) for the list):

```bash
git -C ~/src/qk fetch --tags
```

```bash
git -C ~/src/qk checkout v0.1.0
```

To return to the latest on `main`:

```bash
git -C ~/src/qk checkout main
```

```bash
git -C ~/src/qk pull
```

## 5. Uninstall

Remove only links you have verified point at your qk clone, never the whole skills directory. For example, inspect one link:

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
