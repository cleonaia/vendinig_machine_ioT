"""Serializable evidence and findings used by lab assessments."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class Evidence:
    source: str
    observation: str
    observed_at: str = field(default_factory=utc_now)
    simulated: bool = False


@dataclass(frozen=True)
class Finding:
    finding_id: str
    title: str
    severity: str
    impact: str
    evidence: tuple[Evidence, ...]
    false_positive_notes: str
    mitigation: str


@dataclass
class Assessment:
    subject_id: str
    profile: str
    simulated: bool
    findings: list[Finding] = field(default_factory=list)
    checks: dict[str, dict[str, Any]] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
