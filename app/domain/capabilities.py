"""Shared capability and command result vocabulary for all device adapters."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import Enum
from typing import Any


class CapabilityState(str, Enum):
    AVAILABLE = "available"
    UNSUPPORTED = "unsupported"
    UNVERIFIED = "unverified"


@dataclass(frozen=True)
class Capability:
    name: str
    state: CapabilityState
    source: str
    method: str | None
    verified: bool
    limitation: str | None = None
    writable: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {**asdict(self), "state": self.state.value}


@dataclass(frozen=True)
class CommandResult:
    command_id: str
    machine_id: str
    actor: str
    capability: str
    status: str
    requested_at: str
    completed_at: str | None
    simulated: bool
    verified: bool
    confirmation: str | None
    result: dict[str, Any]
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
