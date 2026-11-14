"""Compare two versions of a managed rule group."""

from __future__ import annotations

from dataclasses import dataclass

from .model import RuleGroupVersion


@dataclass(frozen=True)
class ActionChange:
    name: str
    old: str | None
    new: str | None


@dataclass(frozen=True)
class VersionDiff:
    rules_added: tuple[str, ...]
    rules_removed: tuple[str, ...]
    actions_changed: tuple[ActionChange, ...]
    capacity_old: int
    capacity_new: int
    available_labels_added: tuple[str, ...]
    available_labels_removed: tuple[str, ...]
    consumed_labels_added: tuple[str, ...]
    consumed_labels_removed: tuple[str, ...]


def diff_versions(old: RuleGroupVersion, new: RuleGroupVersion) -> VersionDiff:
    old_rules = old.rules.keys()
    new_rules = new.rules.keys()
    return VersionDiff(
        rules_added=tuple(sorted(new_rules - old_rules)),
        rules_removed=tuple(sorted(old_rules - new_rules)),
        actions_changed=tuple(
            ActionChange(name, old.rules[name], new.rules[name])
            for name in sorted(old_rules & new_rules)
            if old.rules[name] != new.rules[name]
        ),
        capacity_old=old.capacity,
        capacity_new=new.capacity,
        available_labels_added=tuple(sorted(new.available_labels - old.available_labels)),
        available_labels_removed=tuple(sorted(old.available_labels - new.available_labels)),
        consumed_labels_added=tuple(sorted(new.consumed_labels - old.consumed_labels)),
        consumed_labels_removed=tuple(sorted(old.consumed_labels - new.consumed_labels)),
    )
