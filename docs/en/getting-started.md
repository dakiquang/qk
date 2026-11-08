# Getting started

[Tiếng Việt](../vi/getting-started.md) · [Docs index](README.md)

## 1. Install

qk is plain Markdown: no build, no runtime dependency. Clone it once and link each skill folder into the skills directory of every runtime you use. All runtimes then read the same files, and `git pull` updates them all.

The repository is currently private; cloning requires a GitHub account with access.

```bash
git clone https://github.com/dakiquang/qk ~/src/qk
dest=~/.claude/skills            # repeat for each runtime directory below
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

The script checks every target first and links nothing if a target already exists. Run it while no other process is installing skills into that directory; it is not a concurrent installer.

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

## 4. Update

```bash
git -C ~/src/qk pull
```

Links pick up the new version at the next session. Read the [changelog](../../CHANGELOG.md) for what changed.

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

It checks folder and frontmatter names, the explicit-only settings for Claude Code, omp and Codex, internal links, that every English doc has a Vietnamese pair, and that nothing looks like a personal path or a secret. Set `QK_DENYLIST` to a file of terms (one per line) that must never appear in the repository.
