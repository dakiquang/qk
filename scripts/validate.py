#!/usr/bin/env python3
"""Check that every qk skill is well-formed, explicit-invocation only, and safe to publish.

Optional: set QK_DENYLIST to a UTF-8 file of literal terms (one per line).
Terms are checked in UTF-8 text file contents outside .git, including this script.
"""
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SKILLS = ROOT / "skills"
READMES = ("README.md", "README.vi.md")
ALLOWED_FIELDS = {"name", "description", "disable-model-invocation"}
NAME_RE = re.compile(r"^qk-[a-z0-9]+(-[a-z0-9]+)*$")
LINK_RE = re.compile(r"\]\((?!https?:|mailto:|#)([^)#\s]+)")
PERSONAL_RE = re.compile("/" + "Users/|/" + r"home/[a-z]")
SECRET_RE = re.compile(r"\b(ghp_|github_pat_|sk-ant-|sk-proj-|AKIA|xox[bp]-)[A-Za-z0-9_-]{8,}")
DESCRIPTION_BLOCKS = {">", ">-", "|", "|-"}
SELF = Path(__file__).resolve()

errors = []


def fail(path, message):
    errors.append(f"{path.relative_to(ROOT)}: {message}")


def parse_frontmatter(path, text):
    match = re.match(r"^---\n(.*?)\n---\n", text, re.S)
    if not match:
        fail(path, "missing frontmatter")
        return None
    fields, key, block = {}, None, False
    for line in match[1].splitlines():
        if not line.strip():
            continue
        if line[:1] in (" ", "\t"):
            if not block or "\t" in line:
                fail(path, "indented frontmatter requires a space-indented description block")
                return None
            fields[key] = f"{fields[key]} {line.strip()}".strip()
            continue
        name, sep, value = line.partition(":")
        if not sep or not name.strip():
            fail(path, f"unparseable frontmatter line: {line!r}")
            return None
        key = name.strip()
        if key in fields:
            fail(path, f"duplicate frontmatter key: {key}")
        value = value.strip()
        block = key == "description" and value in DESCRIPTION_BLOCKS
        if key == "description" and not value:
            fail(path, "description must be a string, not an empty or nested mapping")
            return None
        fields[key] = "" if block else value.strip("'\"")
    return fields


def check_skill(skill_dir):
    skill_md = skill_dir / "SKILL.md"
    if not skill_md.is_file():
        fail(skill_dir, "missing SKILL.md")
        return
    text = skill_md.read_text(encoding="utf-8")
    fields = parse_frontmatter(skill_md, text)
    if fields is None:
        return

    name = fields.get("name", "")
    if name != skill_dir.name:
        fail(skill_md, f"name {name!r} must equal folder name {skill_dir.name!r}")
    if not NAME_RE.match(name) or len(name) > 64:
        fail(skill_md, f"name {name!r} must match qk-<lowercase-words> and be at most 64 characters")

    description = fields.get("description", "")
    if not description or len(description) > 1024:
        fail(skill_md, "description must be 1-1024 characters")
    trigger = "qk/" + skill_dir.name.removeprefix("qk-")
    if trigger not in description:
        fail(skill_md, f"description must name its explicit trigger {trigger}")

    if fields.get("disable-model-invocation") != "true":
        fail(skill_md, "disable-model-invocation must be true (explicit invocation only)")
    unknown = set(fields) - ALLOWED_FIELDS
    if unknown:
        fail(skill_md, f"unsupported frontmatter fields: {', '.join(sorted(unknown))}")

    if text.count("\n") > 500:
        fail(skill_md, "SKILL.md is longer than 500 lines; move detail into references/")

    policy = skill_dir / "agents" / "openai.yaml"
    if not policy.is_file():
        fail(skill_dir, "missing agents/openai.yaml")
    else:
        check_policy_file(policy)

    for doc in skill_dir.rglob("*.md"):
        check_links(doc, boundary=skill_dir)


def check_policy_file(path):
    """Accept only the canonical agents/openai.yaml shape used by this kit.

    Two top-level blocks, `interface` and `policy`, each at most once; two-space children; full-line
    comments only. Any other line (quoted or spaced keys, flow style, inline comments, deeper nesting)
    is rejected instead of being interpreted, so no YAML variant can hide a different policy.
    """
    allowed = {
        "interface": re.compile(r'  (display_name|short_description): "[^"\\]*"'),
        "policy": re.compile(r"  allow_implicit_invocation: (true|false)"),
    }
    seen, children, parent, values = set(), set(), None, []
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        block = re.fullmatch(r"(interface|policy):", line)
        if block:
            if block[1] in seen:
                fail(path, f"line {number}: duplicate block {block[1]}")
                return
            seen.add(block[1])
            parent = block[1]
            continue
        child = allowed[parent].fullmatch(line) if parent else None
        if not child:
            fail(path, f"line {number}: unsupported line {line.strip()!r}; use the canonical shape")
            return
        child_key = line.strip().partition(":")[0]
        if (parent, child_key) in children:
            fail(path, f"line {number}: duplicate key {parent}.{child_key}")
            return
        children.add((parent, child_key))
        if parent == "policy":
            values.append(child[1])
    if values != ["false"]:
        fail(path, "policy.allow_implicit_invocation must be false exactly once")


def check_links(doc, boundary):
    for target in LINK_RE.findall(doc.read_text(encoding="utf-8")):
        resolved = (doc.parent / target).resolve()
        if not resolved.is_relative_to(boundary.resolve()):
            fail(doc, f"link leaves {boundary.relative_to(ROOT) if boundary != ROOT else 'the repository'}: {target}")
        elif not resolved.exists():
            fail(doc, f"broken link: {target}")


def check_docs(skill_dirs):
    """Require core guides, a guide per skill, and matching EN/VI paths."""
    docs = ROOT / "docs"
    required = {
        Path(name) for name in (
            "README.md", "getting-started.md", "workflows.md", "runtimes.md",
            "case-study-csv-export.md",
        )
    }
    required.update(Path("skills") / f"{skill.name}.md" for skill in skill_dirs)
    pages = {
        language: {path.relative_to(docs / language) for path in (docs / language).rglob("*.md")}
        for language in ("en", "vi")
    }
    for relative in sorted(required | pages["en"] | pages["vi"]):
        for language in ("en", "vi"):
            if relative not in pages[language]:
                fail(docs / language / relative, "missing documentation page or language counterpart")


def text_files():
    for path in ROOT.rglob("*"):
        if ".git" in path.parts or not path.is_file():
            continue
        try:
            content = path.read_bytes()
            if b"\0" not in content:
                yield path, content.decode("utf-8")
        except UnicodeDecodeError:
            continue


def load_denylist():
    source = os.environ.get("QK_DENYLIST")
    if not source:
        return []
    path = Path(source)
    if not path.is_file():
        errors.append(f"QK_DENYLIST points to a missing file: {source}")
        return []
    terms = [line.strip() for line in path.read_text(encoding="utf-8").splitlines()]
    return [re.compile(rf"(?<!\w){re.escape(term)}(?!\w)", re.I) for term in terms if term and not term.startswith("#")]


skill_dirs = sorted(p for p in SKILLS.iterdir() if p.is_dir()) if SKILLS.is_dir() else []
if not skill_dirs:
    errors.append("skills/: no skills found")
for skill_dir in skill_dirs:
    check_skill(skill_dir)

for readme in READMES:
    path = ROOT / readme
    if not path.is_file():
        errors.append(f"{readme}: missing")
        continue
    content = path.read_text(encoding="utf-8")
    for skill_dir in skill_dirs:
        trigger = "qk/" + skill_dir.name.removeprefix("qk-")
        if trigger not in content:
            fail(path, f"does not document {trigger}")

check_docs(skill_dirs)

for doc in ROOT.rglob("*.md"):
    if ".git" not in doc.parts and SKILLS not in doc.parents:
        check_links(doc, boundary=ROOT)

denylist = load_denylist()
for path, content in text_files():
    # This script contains the detection patterns themselves; denylist still applies.
    if path.resolve() != SELF and PERSONAL_RE.search(content):
        fail(path, "contains a personal home path")
    if path.resolve() != SELF and SECRET_RE.search(content):
        fail(path, "contains something that looks like a secret")
    for pattern in denylist:
        if pattern.search(content):
            fail(path, "contains a denylisted term")

for error in errors:
    print(f"FAIL {error}")
print(f"{'FAILED' if errors else 'OK'}: {len(skill_dirs)} skills checked")
sys.exit(1 if errors else 0)
