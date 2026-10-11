"""Hardware-neutral contract. Implementations must report only verified features."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from app.domain.capabilities import Capability, CommandResult


@dataclass(frozen=True)
class AdapterDescriptor:
    adapter_id: str
    manufacturer: str | None
    model: str | None
    protocol: str
    configuration: tuple[str, ...]
    authentication: tuple[str, ...]
    default_timeout_seconds: float
    recovery_method: str
    limitations: tuple[str, ...]
    simulated: bool


class DeviceAdapter(Protocol):
    """Adapter contract; vendor transports stay behind this boundary.

    Constructors must not perform device I/O. Implementations enforce their
    declared timeout and only set verified=True after a controller response or
    a documented post-command readback confirms the result.
    """

    descriptor: AdapterDescriptor

    def capabilities(self) -> list[Capability]: ...
    def read_status(self, machine_id: str) -> dict[str, Any]: ...
    def read_inventory(self, machine_id: str) -> list[dict[str, Any]]: ...
    def diagnostics(self, machine_id: str) -> dict[str, Any]: ...
    def read_resource(self, machine_id: str, capability: str) -> Any: ...
    def recover(self, machine_id: str) -> dict[str, Any]: ...
    def execute(self, machine_id: str, command_id: str, actor: str,
                capability: str, parameters: dict[str, Any]) -> CommandResult: ...
