"""Check the AWS managed rule groups in a web ACL against a target version."""

from __future__ import annotations

from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from botocore.utils import parse_to_aware_datetime

from .diff import diff_versions
from .model import RuleGroupVersion

LEVELS = ("error", "warning", "info")


@dataclass(frozen=True)
class Finding:
    code: str
    level: str
    rule_group: str
    message: str
    details: dict[str, Any]


@dataclass(frozen=True)
class ManagedRef:
    """A top-level AWS managed rule group statement in a web ACL rule."""

    rule_name: str
    group: str
    pinned: str | None
    overrides: tuple[tuple[str, str], ...]  # (source, rule name)
    priority: int | None


@dataclass(frozen=True)
class RuleGroupCatalog:
    """What is known about one managed rule group.

    ``available`` holds ``(version name, LastUpdateTimestamp)`` in API order; ``versions``
    holds every described version (in use and target). A ``default`` that is missing from
    ``versions`` could not be described.
    """

    default: str | None
    available: tuple[tuple[str, Any], ...]
    versions: Mapping[str, RuleGroupVersion]


class TargetError(ValueError):
    """The requested target version cannot be resolved for a rule group."""


def managed_references(web_acl: Mapping[str, Any]) -> list[ManagedRef]:
    """Return the top-level AWS (not Marketplace) managed rule group references in order."""
    refs = []
    for rule in web_acl["WebACL"].get("Rules", []):
        statement = rule.get("Statement", {}).get("ManagedRuleGroupStatement")
        if not statement or statement.get("VendorName") != "AWS":
            continue
        overrides = tuple(
            ("RuleActionOverrides", override["Name"])
            for override in statement.get("RuleActionOverrides", [])
        ) + tuple(
            ("ExcludedRules", excluded["Name"]) for excluded in statement.get("ExcludedRules", [])
        )
        refs.append(
            ManagedRef(
                rule["Name"],
                statement["Name"],
                statement.get("Version"),
                overrides,
                rule.get("Priority"),
            )
        )
    return refs


def resolve_versions(
    group: str,
    pinned: str | None,
    default: str | None,
    available: Sequence[tuple[str, Any]],
    target: str,
) -> tuple[str | None, str | None]:
    """Return ``(in-use version, target version)``; either is ``None`` when there is none.

    The in-use version is the pinned version, or the default when nothing is pinned. A pinned
    version that is not available has no in-use version. ``target`` is ``default``, ``latest``
    (newest ``LastUpdateTimestamp``, first in API order on a tie) or an explicit version name.
    """
    names = [name for name, _ in available]
    if pinned is None:
        in_use = default
    else:
        in_use = pinned if pinned in names else None

    if target == "default":
        return in_use, default
    if target == "latest":
        if not available:
            return in_use, None
        stamped = [(name, stamp) for name, stamp in available if stamp is not None]
        if not stamped:
            raise TargetError(
                f"cannot resolve latest version for {group}: no version has a LastUpdateTimestamp"
            )
        try:
            latest = max(stamped, key=lambda pair: parse_to_aware_datetime(pair[1]))
        except ValueError as exc:
            raise TargetError(f"cannot resolve latest version for {group}: {exc}") from exc
        return in_use, latest[0]
    if target not in names:
        raise TargetError(
            f"target version {target} is not available for {group}; "
            f"available: {', '.join(names) or 'none'}"
        )
    return in_use, target


def _label_matches(statement: Mapping[str, Any]) -> Iterator[tuple[str, str]]:
    """Yield ``(scope, key)`` for every LabelMatchStatement in a statement tree."""
    label = statement.get("LabelMatchStatement")
    if label:
        yield label["Scope"], label["Key"]
    for name in ("AndStatement", "OrStatement"):
        for child in statement.get(name, {}).get("Statements", []):
            yield from _label_matches(child)
    child = statement.get("NotStatement", {}).get("Statement")
    if child:
        yield from _label_matches(child)
    for name in ("RateBasedStatement", "ManagedRuleGroupStatement"):
        child = statement.get(name, {}).get("ScopeDownStatement")
        if child:
            yield from _label_matches(child)


def _emits(version: RuleGroupVersion, scope: str, key: str) -> bool:
    if scope == "NAMESPACE":
        return any(label.startswith(key) for label in version.available_labels)
    return key in version.available_labels


def _override_missing_rule(ref: ManagedRef, target: RuleGroupVersion) -> list[Finding]:
    return [
        Finding(
            "override-missing-rule",
            "error",
            ref.group,
            f"{source} entry {name} in rule {ref.rule_name} is not a rule in {target.name}",
            {
                "rule": ref.rule_name,
                "source": source,
                "override": name,
                "target_version": target.name,
            },
        )
        for source, name in ref.overrides
        if name not in target.rules
    ]


def _label_no_longer_emitted(
    ref: ManagedRef,
    rules: Sequence[Mapping[str, Any]],
    in_use: RuleGroupVersion,
    target: RuleGroupVersion,
) -> list[Finding]:
    findings = []
    for rule in rules:
        if rule["Name"] == ref.rule_name:
            continue
        priority = rule.get("Priority")
        if priority is not None and ref.priority is not None and priority <= ref.priority:
            continue
        seen = set()
        for scope, key in _label_matches(rule.get("Statement", {})):
            if key in seen or not _emits(in_use, scope, key) or _emits(target, scope, key):
                continue
            seen.add(key)
            findings.append(
                Finding(
                    "label-no-longer-emitted",
                    "error",
                    ref.group,
                    f"rule {rule['Name']} matches {scope} {key}, not emitted by {target.name}",
                    {
                        "rule": rule["Name"],
                        "managed_rule": ref.rule_name,
                        "scope": scope,
                        "key": key,
                        "in_use_version": in_use.name,
                        "target_version": target.name,
                    },
                )
            )
    return findings


def _version_unavailable(ref: ManagedRef, catalog: RuleGroupCatalog) -> list[Finding]:
    if ref.pinned is None or any(name == ref.pinned for name, _ in catalog.available):
        return []
    return [
        Finding(
            "version-unavailable",
            "error",
            ref.group,
            f"pinned version {ref.pinned} is not available; default is {catalog.default or 'none'}",
            {"rule": ref.rule_name, "version": ref.pinned, "default_version": catalog.default},
        )
    ]


def _capacity_increase(
    ref: ManagedRef,
    in_use: RuleGroupVersion,
    target: RuleGroupVersion,
    web_acl_capacity: int | None,
) -> list[Finding]:
    if target.capacity <= in_use.capacity:
        return []
    message = (
        f"capacity {in_use.capacity} -> {target.capacity} WCU "
        f"({target.capacity - in_use.capacity:+d})"
    )
    details: dict[str, Any] = {
        "rule": ref.rule_name,
        "in_use_version": in_use.name,
        "target_version": target.name,
        "in_use_capacity": in_use.capacity,
        "target_capacity": target.capacity,
    }
    if web_acl_capacity is not None:
        message += f"; web ACL capacity {web_acl_capacity}"
        details["web_acl_capacity"] = web_acl_capacity
    return [Finding("capacity-increase", "warning", ref.group, message, details)]


def _behind_default(ref: ManagedRef, default: str | None) -> list[Finding]:
    if ref.pinned is None or default is None or ref.pinned == default:
        return []
    return [
        Finding(
            "behind-default",
            "info",
            ref.group,
            f"pinned version {ref.pinned} differs from default {default}",
            {"rule": ref.rule_name, "version": ref.pinned, "default_version": default},
        )
    ]


def _default_not_describable(ref: ManagedRef, default: str) -> list[Finding]:
    return [
        Finding(
            "default-not-describable",
            "warning",
            ref.group,
            f"default version {default} cannot be described; comparisons that need it are skipped",
            {"rule": ref.rule_name, "default_version": default},
        )
    ]


def _described(catalog: RuleGroupCatalog, name: str | None) -> RuleGroupVersion | None:
    if name is None or (name == catalog.default and name not in catalog.versions):
        return None
    return catalog.versions[name]


def _rules_changed(
    ref: ManagedRef, in_use: RuleGroupVersion, target: RuleGroupVersion
) -> list[Finding]:
    result = diff_versions(in_use, target)
    added = len(result.rules_added)
    removed = len(result.rules_removed)
    changed = len(result.actions_changed)
    if not (added or removed or changed):
        return []
    return [
        Finding(
            "rules-changed",
            "info",
            ref.group,
            f"{in_use.name} -> {target.name}: {added} added, {removed} removed, "
            f"{changed} action changed",
            {
                "rule": ref.rule_name,
                "in_use_version": in_use.name,
                "target_version": target.name,
                "added": added,
                "removed": removed,
                "action_changed": changed,
            },
        )
    ]


def check_web_acl(
    web_acl: Mapping[str, Any], catalogs: Mapping[str, RuleGroupCatalog], target: str
) -> list[Finding]:
    """Return the findings for every AWS managed rule group in ``web_acl``, most severe first.

    ``catalogs`` must hold every referenced group with its in-use and target versions described,
    except a default that cannot be described.
    """
    acl = web_acl["WebACL"]
    rules = acl.get("Rules", [])
    findings: list[Finding] = []
    for ref in managed_references(web_acl):
        catalog = catalogs[ref.group]
        in_use_name, target_name = resolve_versions(
            ref.group, ref.pinned, catalog.default, catalog.available, target
        )
        in_use = _described(catalog, in_use_name)
        wanted = _described(catalog, target_name)

        default = catalog.default
        undescribable = default is not None and default not in catalog.versions
        if undescribable and default in (in_use_name, target_name):
            findings += _default_not_describable(ref, default)
        findings += _version_unavailable(ref, catalog)
        if not undescribable:  # default-not-describable already covers an unusable default
            findings += _behind_default(ref, catalog.default)
        if wanted is not None:
            findings += _override_missing_rule(ref, wanted)
        if in_use is not None and wanted is not None:
            findings += _label_no_longer_emitted(ref, rules, in_use, wanted)
            findings += _capacity_increase(ref, in_use, wanted, acl.get("Capacity"))
            findings += _rules_changed(ref, in_use, wanted)
    return sorted(findings, key=lambda f: (LEVELS.index(f.level), f.rule_group, f.code))
