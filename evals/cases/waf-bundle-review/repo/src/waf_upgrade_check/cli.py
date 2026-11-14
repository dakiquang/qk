"""Command-line entry point."""

from __future__ import annotations

import argparse
import dataclasses
import json
import sys
from collections.abc import Iterable
from typing import Any, TextIO

from botocore.exceptions import BotoCoreError, ClientError

from . import __version__, aws
from .check import (
    LEVELS,
    Finding,
    RuleGroupCatalog,
    TargetError,
    check_web_acl,
    managed_references,
    resolve_versions,
)
from .diff import VersionDiff, diff_versions
from .model import RuleGroupVersion

PROG = "waf-upgrade-check"


class UsageError(Exception):
    """A combination of options that argparse cannot reject on its own."""


def _common_options() -> argparse.ArgumentParser:
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument(
        "--scope",
        choices=["REGIONAL", "CLOUDFRONT"],
        default="REGIONAL",
        help="rule group scope (default: REGIONAL; CLOUDFRONT always uses us-east-1)",
    )
    common.add_argument("--region", default=None, help="AWS region for REGIONAL scope")
    common.add_argument("--profile", default=None, help="AWS named profile")
    common.add_argument(
        "--format", choices=["text", "json"], default="text", help="output format (default: text)"
    )
    return common


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog=PROG,
        description="Check what breaks before you upgrade an AWS WAF managed rule group version.",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    common = _common_options()
    subparsers = parser.add_subparsers(dest="command", metavar="<command>")

    versions = subparsers.add_parser(
        "versions",
        parents=[common],
        help="list available versions of a managed rule group",
        description="List available versions of an AWS managed rule group.",
    )
    versions.add_argument("rule_group", help="managed rule group name")
    versions.set_defaults(handler=_cmd_versions)

    diff = subparsers.add_parser(
        "diff",
        parents=[common],
        help="compare two versions of a managed rule group",
        description="Compare two versions of an AWS managed rule group.",
    )
    diff.add_argument("rule_group", help="managed rule group name")
    diff.add_argument("from_version", metavar="from", help="current version")
    diff.add_argument("to_version", metavar="to", help="target version")
    diff.set_defaults(handler=_cmd_diff)

    check_cmd = subparsers.add_parser(
        "check",
        parents=[common],
        help="check a web ACL's AWS managed rule groups against a target version",
        description=(
            "Check every AWS managed rule group in a web ACL against a target version. "
            "Exit code 1 when at least one finding is an error."
        ),
    )
    source = check_cmd.add_mutually_exclusive_group(required=True)
    source.add_argument(
        "--web-acl-file", metavar="PATH", help="web ACL JSON as returned by get-web-acl"
    )
    source.add_argument("--web-acl", metavar="NAME", help="name of the web ACL to fetch")
    check_cmd.add_argument("--id", metavar="ID", help="web ACL ID (required with --web-acl)")
    check_cmd.add_argument(
        "--target",
        default="default",
        metavar="default|latest|VERSION",
        help=(
            "version to check against: the current default, the newest by "
            "LastUpdateTimestamp, or a version name (default: default)"
        ),
    )
    check_cmd.set_defaults(handler=_cmd_check)
    return parser


def _client(args: argparse.Namespace):
    if args.scope == "CLOUDFRONT" and args.region not in (None, aws.CLOUDFRONT_REGION):
        raise UsageError(
            f"--scope CLOUDFRONT requires region {aws.CLOUDFRONT_REGION}, got {args.region}"
        )
    return aws.make_client(args.scope, args.region, args.profile)


def _cmd_versions(args: argparse.Namespace, out: TextIO) -> None:
    client = _client(args)
    default, names = aws.list_versions(client, args.rule_group, args.scope)
    if args.format == "json":
        payload = {
            "rule_group": args.rule_group,
            "scope": args.scope,
            "default_version": default,
            "versions": names,
        }
        out.write(json.dumps(payload, indent=2) + "\n")
    else:
        out.write(_format_versions_text(default, names))


def _cmd_diff(args: argparse.Namespace, out: TextIO) -> None:
    client = _client(args)
    old = aws.describe(client, args.rule_group, args.scope, args.from_version)
    new = aws.describe(client, args.rule_group, args.scope, args.to_version)
    result = diff_versions(old, new)
    if args.format == "json":
        out.write(json.dumps(_diff_payload(args, result), indent=2) + "\n")
    else:
        out.write(_format_diff_text(args, result))


def _read_web_acl(path: str) -> dict[str, Any]:
    try:
        with open(path, encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, ValueError) as exc:
        raise UsageError(f"cannot read web ACL file {path}: {exc}") from exc
    if not isinstance(data, dict) or not isinstance(data.get("WebACL"), dict):
        raise UsageError(f"web ACL file {path} has no WebACL object")
    return data


def _cmd_check(args: argparse.Namespace, out: TextIO) -> int:
    if args.web_acl is not None and args.id is None:
        raise UsageError("--web-acl requires --id")
    if args.web_acl_file is not None and args.id is not None:
        raise UsageError("--id cannot be used with --web-acl-file")
    web_acl = _read_web_acl(args.web_acl_file) if args.web_acl_file is not None else None
    client = _client(args)
    if web_acl is None:
        web_acl = aws.get_web_acl(client, args.web_acl, args.id, args.scope)

    refs = managed_references(web_acl)
    listed: dict[str, tuple[str | None, list[tuple[str, Any]]]] = {}
    for ref in refs:
        if ref.group not in listed:
            listed[ref.group] = aws.list_version_timestamps(client, ref.group, args.scope)

    needed: dict[tuple[str, str], None] = {}
    for ref in refs:
        default, available = listed[ref.group]
        try:
            versions = resolve_versions(ref.group, ref.pinned, default, available, args.target)
        except TargetError as exc:
            raise UsageError(str(exc)) from exc
        for version in versions:
            if version is not None:
                needed[(ref.group, version)] = None

    described: dict[str, dict[str, RuleGroupVersion]] = {group: {} for group in listed}
    for group, version in needed:
        default, available = listed[group]
        if version == default and all(name != default for name, _ in available):
            continue
        try:
            described[group][version] = aws.describe(client, group, args.scope, version)
        except ClientError as exc:
            code = exc.response.get("Error", {}).get("Code")
            if version != default or code != "WAFNonexistentItemException":
                raise

    catalogs = {
        group: RuleGroupCatalog(default, tuple(available), described[group])
        for group, (default, available) in listed.items()
    }
    findings = check_web_acl(web_acl, catalogs, args.target)
    if args.format == "json":
        payload = [dataclasses.asdict(finding) for finding in findings]
        out.write(json.dumps(payload, indent=2) + "\n")
    else:
        out.write(_format_check_text(findings))
    return 1 if any(finding.level == "error" for finding in findings) else 0


def _format_versions_text(default: str | None, names: list[str]) -> str:
    lines = [f"{name} (default)" if name == default else name for name in names]
    lines.append(f"Default version: {default or 'none'}")
    return "\n".join(lines) + "\n"


def _format_check_text(findings: list[Finding]) -> str:
    lines = [
        f"{finding.level.upper()}  {finding.rule_group}  {finding.code}  {finding.message}"
        for finding in findings
    ]
    counts = {level: sum(finding.level == level for finding in findings) for level in LEVELS}
    lines.append(
        f"Summary: {counts['error']} error(s), {counts['warning']} warning(s), "
        f"{counts['info']} info"
    )
    return "\n".join(lines) + "\n"


def _section(title: str, items: Iterable[str]) -> list[str]:
    entries = [f"  {item}" for item in items]
    return [f"{title} ({len(entries)}):", *(entries or ["  none"])]


def _format_diff_text(args: argparse.Namespace, result: VersionDiff) -> str:
    delta = result.capacity_new - result.capacity_old
    lines = [
        f"{args.rule_group} {args.from_version} -> {args.to_version} ({args.scope})",
        f"Capacity: {result.capacity_old} -> {result.capacity_new} ({delta:+d})",
    ]
    lines += _section("Rules added", result.rules_added)
    lines += _section("Rules removed", result.rules_removed)
    lines += _section(
        "Action changed",
        (
            f"{change.name}: {change.old or 'none'} -> {change.new or 'none'}"
            for change in result.actions_changed
        ),
    )
    lines += _section("Available labels added", result.available_labels_added)
    lines += _section("Available labels removed", result.available_labels_removed)
    lines += _section("Consumed labels added", result.consumed_labels_added)
    lines += _section("Consumed labels removed", result.consumed_labels_removed)
    return "\n".join(lines) + "\n"


def _diff_payload(args: argparse.Namespace, result: VersionDiff) -> dict:
    return {
        "rule_group": args.rule_group,
        "scope": args.scope,
        "from": args.from_version,
        "to": args.to_version,
        "capacity": {"old": result.capacity_old, "new": result.capacity_new},
        "rules": {
            "added": list(result.rules_added),
            "removed": list(result.rules_removed),
            "action_changed": [
                {"name": change.name, "old": change.old, "new": change.new}
                for change in result.actions_changed
            ],
        },
        "available_labels": {
            "added": list(result.available_labels_added),
            "removed": list(result.available_labels_removed),
        },
        "consumed_labels": {
            "added": list(result.consumed_labels_added),
            "removed": list(result.consumed_labels_removed),
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command is None:
        parser.print_help()
        return 0
    try:
        status = args.handler(args, sys.stdout)
    except (UsageError, BotoCoreError, ClientError) as exc:
        print(f"{PROG}: error: {exc}", file=sys.stderr)
        return 2
    return status or 0


if __name__ == "__main__":
    sys.exit(main())
