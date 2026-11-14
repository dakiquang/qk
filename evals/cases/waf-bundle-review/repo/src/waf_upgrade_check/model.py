"""Data model for a managed rule group version."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any


def _action_name(action: Mapping[str, Any] | None) -> str | None:
    """Return the single action key of a RuleSummary ``Action``, or ``None`` if absent."""
    if not action:
        return None
    if len(action) != 1:
        raise ValueError(f"expected exactly one rule action, got {sorted(action)}")
    return next(iter(action))


@dataclass(frozen=True)
class RuleGroupVersion:
    name: str
    capacity: int
    rules: dict[str, str | None]
    available_labels: frozenset[str]
    consumed_labels: frozenset[str]
    label_namespace: str | None

    @classmethod
    def from_response(cls, resp: Mapping[str, Any]) -> RuleGroupVersion:
        """Build from a ``DescribeManagedRuleGroup`` response."""
        return cls(
            name=resp["VersionName"],
            capacity=resp["Capacity"],
            rules={rule["Name"]: _action_name(rule.get("Action")) for rule in resp["Rules"]},
            available_labels=frozenset(label["Name"] for label in resp.get("AvailableLabels", [])),
            consumed_labels=frozenset(label["Name"] for label in resp.get("ConsumedLabels", [])),
            label_namespace=resp.get("LabelNamespace"),
        )
