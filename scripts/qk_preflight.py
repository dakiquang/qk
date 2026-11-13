#!/usr/bin/env python3
"""Check whether the active GitHub CLI account can push to origin."""
import argparse
import re
import shutil
import subprocess
from pathlib import Path
from urllib.parse import urlparse


SECRET_RE = re.compile(r"(ghp_|github_pat_|gho_)[A-Za-z0-9_]{8,}")
ACCOUNT_RE = re.compile(r"Logged in to github\.com account\s+([^\s(]+)")


def github_repository(remote):
    """Return owner/name for a github.com origin, or None."""
    if remote.lower().startswith("git@github.com:"):
        path = remote.split(":", 1)[1]
    else:
        parsed = urlparse(remote)
        if parsed.scheme not in ("https", "ssh") or parsed.hostname != "github.com":
            return None
        path = parsed.path.lstrip("/")
    parts = path.strip("/").removesuffix(".git").split("/")
    if len(parts) != 2 or not all(re.fullmatch(r"[A-Za-z0-9_.-]+", part) for part in parts):
        return None
    return "/".join(parts)


def _git(repo, *args, check=True):
    proc = subprocess.run(["git", *args], cwd=str(repo), capture_output=True, text=True)
    if check and proc.returncode:
        raise RuntimeError("git command failed")
    return proc.stdout.strip()


def _gh(repo, *args, check=True):
    proc = subprocess.run(["gh", *args], cwd=str(repo), capture_output=True, text=True)
    if check and proc.returncode:
        raise RuntimeError("Not Found" if "Not Found" in proc.stderr or "404" in proc.stderr
                           else "gh command failed")
    if args[:2] == ("auth", "status"):
        return "\n".join(stream.strip() for stream in (proc.stdout, proc.stderr) if stream.strip())
    return (proc.stdout or proc.stderr).strip()


def _accounts(status):
    return sorted({match.group(1) for match in ACCOUNT_RE.finditer(status)})


def check_identity(repo, gh_call=None, git_call=None):
    """Return (can_push, safe_report) for the active gh account and origin."""
    repo = Path(repo)
    git_call = git_call or _git
    gh_call = gh_call or _gh
    try:
        remote = git_call(repo, "remote", "get-url", "origin", check=False)
    except (OSError, RuntimeError):
        return False, "git could not read origin"
    if not remote:
        return True, "not applicable: no origin remote"
    repository = github_repository(remote)
    if not repository:
        return True, "not applicable: origin is not a github.com repository"
    if gh_call is _gh and not shutil.which("gh"):
        return False, "gh is not installed; install GitHub CLI to check push permission"

    email = git_call(repo, "config", "user.email", check=False) or "(unset)"
    try:
        account = gh_call(repo, "api", "user", "--jq", ".login") or "(unknown)"
    except Exception:
        account = "(unknown)"
    try:
        permission = gh_call(repo, "api", f"repos/{repository}", "--jq", ".permissions.push")
        visible = True
    except Exception as exc:
        permission = "unavailable"
        visible = False
        not_found = "404" in str(exc) or "Not Found" in str(exc)
    else:
        not_found = False

    lines = ["Field | Value", "--- | ---", f"Repository | {repository}",
             f"Active gh account | {account}", f"git user.email | {email}",
             f"Push permission | {permission if permission in ('true', 'false') else 'unavailable'}"]
    if remote.lower().startswith("git@github.com:") or urlparse(remote).scheme == "ssh":
        lines.append("SSH origin | Push uses your SSH key; this API check does not verify which account that key belongs to.")
    if permission == "true":
        return True, SECRET_RE.sub("[redacted]", "\n".join(lines))

    if not_found:
        lines.append("Repository is not visible to the active account (404 / Not Found).")
    elif visible and permission == "false":
        lines.append("The active account does not have push permission.")
    else:
        lines.append("Could not confirm push permission for the active account.")
    try:
        accounts = _accounts(gh_call(repo, "auth", "status", check=False))
    except Exception:
        accounts = []
    others = [name for name in accounts if name != account]
    lines.append("Other logged-in gh accounts: " + (", ".join(others) if others else "none found"))
    lines.append("Switch accounts yourself with gh auth switch -u <name>, then retry.")
    return False, SECRET_RE.sub("[redacted]", "\n".join(lines))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    identity = sub.add_parser("identity")
    identity.add_argument("--repo", default=".")
    args = parser.parse_args(argv)
    ok, report = check_identity(args.repo)
    print(report)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
