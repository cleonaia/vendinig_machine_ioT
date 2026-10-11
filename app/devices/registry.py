"""Adapter discovery and selection. No physical adapter is bundled yet."""
from __future__ import annotations

from collections.abc import Callable
from typing import Any

from app.devices.device_adapter import AdapterDescriptor, DeviceAdapter
from app.devices.simulator import SimulatorAdapter
from app.devices.mqtt_adapter import MqttAdapter


class AdapterRegistry:
    def __init__(self) -> None:
        self._adapters: dict[str, tuple[Callable[[dict[str, Any]], DeviceAdapter], AdapterDescriptor]] = {}

    def register(self, factory: Callable[[dict[str, Any]], DeviceAdapter], descriptor: AdapterDescriptor) -> None:
        adapter_id = descriptor.adapter_id
        if adapter_id in self._adapters:
            raise ValueError(f"Adapter already registered: {adapter_id}")
        if not 0.05 <= descriptor.default_timeout_seconds <= 300:
            raise ValueError("adapter timeout must be between 0.05 and 300 seconds")
        if factory({}).descriptor != descriptor:
            raise ValueError("adapter factory descriptor does not match registered descriptor")
        self._adapters[adapter_id] = (factory, descriptor)

    def get(self, adapter_id: str, configuration: dict[str, Any] | None = None) -> DeviceAdapter:
        try:
            factory, descriptor = self._adapters[adapter_id]
            adapter = factory(configuration or {})
            if adapter.descriptor.adapter_id != adapter_id:
                raise LookupError(f"Adapter factory identity mismatch: {adapter_id}")
            if adapter.descriptor != descriptor:
                raise LookupError(f"Adapter descriptor changed after registration: {adapter_id}")
            return adapter
        except KeyError as exc:
            raise LookupError(f"No compatible adapter registered for {adapter_id}") from exc

    def describe(self, adapter_id: str) -> AdapterDescriptor:
        try:
            return self._adapters[adapter_id][1]
        except KeyError as exc:
            raise LookupError(f"No compatible adapter registered for {adapter_id}") from exc

    def catalog(self) -> list[dict[str, object]]:
        entries = []
        for factory, descriptor in self._adapters.values():
            adapter = factory({})
            entries.append({"adapter_id": descriptor.adapter_id,
                            "manufacturer": descriptor.manufacturer,
                            "model": descriptor.model,
                            "protocol": descriptor.protocol,
                            "configuration": list(descriptor.configuration),
                            "authentication": list(descriptor.authentication),
                            "default_timeout_seconds": descriptor.default_timeout_seconds,
                            "recovery_method": descriptor.recovery_method,
                            "limitations": list(descriptor.limitations),
                            "simulated": descriptor.simulated,
                            "capabilities": [cap.to_dict() for cap in adapter.capabilities()]})
        return entries


def default_registry() -> AdapterRegistry:
    registry = AdapterRegistry()
    for profile in SimulatorAdapter.PROFILES:
        template = SimulatorAdapter(profile)
        registry.register(lambda configuration, profile=profile: SimulatorAdapter(profile), template.descriptor)
    mqtt_template = MqttAdapter({})
    registry.register(lambda configuration: MqttAdapter(configuration), mqtt_template.descriptor)
    return registry
