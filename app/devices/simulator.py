"""Deterministic simulated adapters; no sockets or physical device I/O."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.devices.device_adapter import AdapterDescriptor
from app.domain.capabilities import Capability, CapabilityState, CommandResult


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


class SimulatorAdapter:
    PROFILES = {
        "compact": {
            "label": "Compact simulator",
            "capabilities": {"status.read", "inventory.read", "inventory.adjust", "diagnostics.read", "diagnostics.run"},
            "commands": {"inventory.adjust", "diagnostics.run"},
            "limitations": ("No physical sensors or controller; inventory is simulated.",),
        },
        "connected": {
            "label": "Connected simulator",
            "capabilities": {"status.read", "telemetry.read", "alarms.read", "inventory.read", "inventory.adjust", "sales.read", "payment.status", "diagnostics.read", "diagnostics.run", "maintenance.set", "device.restart", "vend.simulate", "connection.recover"},
            "commands": {"inventory.adjust", "diagnostics.run", "maintenance.set", "device.restart", "vend.simulate", "connection.recover"},
            "limitations": ("All telemetry, sales, payment state and command acknowledgements are generated locally.",),
        },
    }

    def __init__(self, profile: str):
        if profile not in self.PROFILES:
            raise ValueError(f"Unknown simulator profile: {profile}")
        self.profile = profile
        self.profile_data = self.PROFILES[profile]
        self.maintenance = False
        self.online = True
        self.inventory = {"water": {"name": "Water", "price_minor": 150, "stock": 10, "source": "simulator_profile"},
                          "snack": {"name": "Snack", "price_minor": 225, "stock": 6, "source": "simulator_profile"}}
        self.sales_count = 0
        self.descriptor = AdapterDescriptor(
            adapter_id=f"simulation.{profile}", manufacturer="Simulated", model=profile,
            protocol="simulator://in-process", configuration=(), authentication=(),
            default_timeout_seconds=1.0, recovery_method="in_process_state_reset",
            limitations=self.profile_data["limitations"], simulated=True,
        )

    def capabilities(self) -> list[Capability]:
        supported = self.profile_data["capabilities"]
        all_capabilities = (
            "status.read", "telemetry.read", "alarms.read", "inventory.read",
            "sales.read", "payment.status", "diagnostics.read", "diagnostics.run", "inventory.adjust", "maintenance.set",
            "device.restart", "vend.simulate", "connection.recover",
        )
        return [Capability(
            name=name,
            state=CapabilityState.AVAILABLE if name in supported else CapabilityState.UNSUPPORTED,
            source="local_simulator", method=name if name in supported else None,
            verified=name in supported,
            limitation=None if name in supported else "Not supported by this simulator profile.",
            writable=name in self.profile_data["commands"],
        ) for name in all_capabilities]

    def read_status(self, machine_id: str) -> dict[str, Any]:
        return {"machine_id": machine_id, "connection": "simulated_online" if self.online else "simulated_offline", "availability": "simulated",
                "maintenance": self.maintenance, "temperature_c": 5.2 if self.profile == "connected" else None,
                "last_communication": now(), "data_origin": "local_simulator", "simulated": True}

    def export_state(self) -> dict[str, Any]:
        return {"online": self.online, "maintenance": self.maintenance,
                "inventory": self.inventory, "sales_count": self.sales_count}

    def load_state(self, state: dict[str, Any]) -> None:
        if not state:
            return
        inventory = state.get("inventory")
        if (type(state.get("online")) is not bool or type(state.get("maintenance")) is not bool
                or type(state.get("sales_count")) is not int or state["sales_count"] < 0
                or not isinstance(inventory, dict) or set(inventory) != set(self.inventory)):
            raise ValueError("invalid persisted simulator state")
        for product_id, product in inventory.items():
            if (not isinstance(product, dict) or type(product.get("stock")) is not int
                    or product["stock"] < 0 or type(product.get("price_minor")) is not int
                    or not isinstance(product.get("name"), str)
                    or product.get("source") not in {"simulator_profile", "manual_simulation"}):
                raise ValueError("invalid persisted simulator inventory")
        self.online = state["online"]
        self.maintenance = state["maintenance"]
        self.sales_count = state["sales_count"]
        self.inventory = inventory

    def read_inventory(self, machine_id: str) -> list[dict[str, Any]]:
        return [{"product_id": product_id, **product, "data_origin": "local_simulator"}
                for product_id, product in self.inventory.items()]

    def diagnostics(self, machine_id: str) -> dict[str, Any]:
        return {"machine_id": machine_id, "status": "simulated_ok", "checks": ["controller", "inventory", "connectivity"],
                "data_origin": "local_simulator", "simulated": True}

    def recover(self, machine_id: str) -> dict[str, Any]:
        self.online = True
        return {"machine_id": machine_id, "connection": "simulated_online", "simulated": True}

    def read_resource(self, machine_id: str, capability: str) -> dict[str, Any]:
        resources = {
            "telemetry.read": {"temperature_c": 5.2, "data_origin": "local_simulator"},
            "alarms.read": {"items": [] if self.online else [{"code": "simulated_disconnect", "severity": "warning"}], "data_origin": "local_simulator"},
            "sales.read": {"total_count": self.sales_count, "currency": "EUR", "data_origin": "local_simulator"},
            "payment.status": {"cashless_terminal": "simulated_ready", "data_origin": "local_simulator"},
        }
        if capability not in resources or self.profile != "connected":
            raise LookupError("Capability unsupported by simulator profile")
        return {"machine_id": machine_id, **resources[capability], "simulated": True}

    def execute(self, machine_id: str, command_id: str, actor: str, capability: str,
                parameters: dict[str, Any]) -> CommandResult:
        requested_at = now()
        if capability not in self.profile_data["commands"]:
            return CommandResult(command_id, machine_id, actor, capability, "rejected", requested_at,
                                 now(), True, False, None, {}, "capability_unsupported")
        if "simulation_fault" in parameters:
            fault = parameters["simulation_fault"]
            if fault not in {"timeout", "disconnect"}:
                return CommandResult(command_id, machine_id, actor, capability, "rejected", requested_at,
                                     now(), True, False, None, {}, "invalid_simulation_fault")
            if fault == "disconnect":
                self.online = False
            return CommandResult(command_id, machine_id, actor, capability,
                                 "timed_out" if fault == "timeout" else "disconnected", requested_at,
                                 now(), True, False, None, {}, f"simulated_{fault}")
        if capability == "connection.recover":
            if parameters:
                return CommandResult(command_id, machine_id, actor, capability, "rejected", requested_at,
                                     now(), True, False, None, {}, "parameters_not_supported")
            recovery = self.recover(machine_id)
            return CommandResult(command_id, machine_id, actor, capability, "confirmed", requested_at,
                                 now(), True, True, "simulated_reconnection_verified", recovery)
        if not self.online and capability != "device.restart":
            return CommandResult(command_id, machine_id, actor, capability, "disconnected", requested_at,
                                 now(), True, False, None, {}, "simulated_device_offline")
        if capability == "device.restart":
            if parameters:
                return CommandResult(command_id, machine_id, actor, capability, "rejected", requested_at,
                                     now(), True, False, None, {}, "parameters_not_supported")
            self.online = True
            result = {"connection": "simulated_online", "data_origin": "local_simulator"}
        elif capability == "maintenance.set":
            if set(parameters) != {"enabled"} or type(parameters["enabled"]) is not bool:
                return CommandResult(command_id, machine_id, actor, capability, "rejected", requested_at,
                                     now(), True, False, None, {}, "invalid_parameters")
            self.maintenance = parameters["enabled"]
            result = {"maintenance": self.maintenance}
        elif capability == "inventory.adjust":
            if set(parameters) != {"product_id", "stock"} or not isinstance(parameters["product_id"], str) or parameters["product_id"] not in self.inventory or type(parameters["stock"]) is not int or not 0 <= parameters["stock"] <= 10000:
                return CommandResult(command_id, machine_id, actor, capability, "rejected", requested_at,
                                     now(), True, False, None, {}, "invalid_parameters")
            product_id = parameters["product_id"]
            self.inventory[product_id]["stock"] = parameters["stock"]
            self.inventory[product_id]["source"] = "manual_simulation"
            result = {"product_id": product_id, "stock": parameters["stock"], "source": "manual_simulation"}
        elif capability == "vend.simulate":
            if self.maintenance:
                return CommandResult(command_id, machine_id, actor, capability, "rejected", requested_at,
                                     now(), True, False, None, {}, "simulated_maintenance_active")
            if set(parameters) != {"product_id"} or parameters["product_id"] not in {"water", "snack"}:
                return CommandResult(command_id, machine_id, actor, capability, "rejected", requested_at,
                                     now(), True, False, None, {}, "invalid_parameters")
            product_id = parameters["product_id"]
            if self.inventory[product_id]["stock"] < 1:
                return CommandResult(command_id, machine_id, actor, capability, "rejected", requested_at,
                                     now(), True, False, None, {}, "simulated_out_of_stock")
            self.inventory[product_id]["stock"] -= 1
            self.sales_count += 1
            result = {"product_id": product_id, "dispensed": True, "remaining_stock": self.inventory[product_id]["stock"],
                      "data_origin": "local_simulator"}
        elif parameters:
            return CommandResult(command_id, machine_id, actor, capability, "rejected", requested_at,
                                 now(), True, False, None, {}, "parameters_not_supported")
        else:
            result = self.diagnostics(machine_id) if capability == "diagnostics.run" else {"status": "simulated_ok"}
        return CommandResult(command_id, machine_id, actor, capability, "confirmed", requested_at,
                             now(), True, True, "simulator_state_verified", result)
