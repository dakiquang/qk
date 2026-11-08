# qk/release-notes

[Tiếng Việt](../../vi/skills/qk-release-notes.md) · [Docs index](../README.md) · [Skill source](../../../skills/qk-release-notes/SKILL.md)

## When to use it

Use this to turn a tag range, merged PR list or upcoming version into user-facing release notes. It drafts text; it is not the release command.

## Example input

```text
/qk-release-notes Draft English and Vietnamese notes for v0.1.0..HEAD. Save to plans/release-notes-next.md. Include upgrade risks, but do not change versions, tag or publish.
```

Use a real range in your repository. If you want a changelog edit, explicitly request updating its `[Unreleased]` section. Without a bilingual request, follow the repository's language convention.

## What you get

Changes grouped for readers: additions, changes, fixes and upgrade notes (breaking behaviour, dependencies, environment variables, migrations). Every line traces to a commit or PR; diffs are read when titles are insufficient. Internal-only commits without user impact are omitted with a short reason.

A verified section includes only actual CI, command or runtime evidence. A merged PR alone does not prove verification; omit the section if no evidence exists. Keep the repository's changelog format and exclude customer/internal-system details.

## Authority and completion

Read-only Git and PR access; may write the draft or the requested `[Unreleased]` section. No version bumps, tags, `gh release`, publication or deployment.

Done means the draft is traceable and ready for your review, with version/breaking-change decisions explicit. Release separately through the repository's process or `pr-orchestrator` release mode, with explicit authority.

All higher-priority, runtime and repository rules still apply. This skill does not change models, permissions, hooks or configuration, and never invokes another qk skill automatically.
