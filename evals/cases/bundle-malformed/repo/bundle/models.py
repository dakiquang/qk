"""Data types of a deployment bundle."""
from dataclasses import dataclass, field
from typing import List


class BundleError(ValueError):
    """A bundle document is structurally invalid."""


@dataclass
class Statement:
    effect: str  # "Allow" or "Deny"
    actions: List[str]


@dataclass
class Policy:
    name: str
    statement: Statement


@dataclass
class Version:
    name: str
    created: str  # ISO 8601 date


@dataclass
class Bundle:
    name: str
    capacity: int
    policy: Policy
    versions: List[Version] = field(default_factory=list)
