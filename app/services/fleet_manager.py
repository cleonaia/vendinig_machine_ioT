"""Persistent simulated fleet registry and idempotent command dispatcher."""
from __future__ import annotations

import json
import re
import sqlite3
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl, urlsplit

from app.devices.registry import AdapterRegistry, default_registry
from app.domain.capabilities import CapabilityState, CommandResult


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class FleetError(ValueError):
    def __init__(self, code: str, status_code: int = 400):
        self.code = code
        self.status_code = status_code
        super().__init__(code)


class FleetManager:
    def __init__(self, path: Path, registry: AdapterRegistry | None = None, seed_demo: bool = True):
        self.path = path
        self.registry = registry or default_registry()
        self._adapters: dict[str, Any] = {}
        self._adapter_guard = threading.RLock()
        self._machine_guards: dict[str, threading.RLock] = {}
        self._initialize(seed_demo)

    def connect(self) -> sqlite3.Connection:
        db = sqlite3.connect(self.path, timeout=5, isolation_level="IMMEDIATE")
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys=ON")
        return db

    def _lock_for(self, machine_id: str) -> threading.RLock:
        with self._adapter_guard:
            return self._machine_guards.setdefault(machine_id, threading.RLock())

    def _initialize(self, seed_demo: bool) -> None:
        with self.connect() as db:
            db.execute("CREATE TABLE IF NOT EXISTS machines (machine_id TEXT PRIMARY KEY, name TEXT NOT NULL, adapter_id TEXT NOT NULL, created_at TEXT NOT NULL, source TEXT NOT NULL, simulator_state TEXT NOT NULL DEFAULT '{}', adapter_config TEXT NOT NULL DEFAULT '{}')")
            columns = {row[1] for row in db.execute("PRAGMA table_info(machines)")}
            if "simulator_state" not in columns:
                db.execute("ALTER TABLE machines ADD COLUMN simulator_state TEXT NOT NULL DEFAULT '{}'")
            if "adapter_config" not in columns:
                db.execute("ALTER TABLE machines ADD COLUMN adapter_config TEXT NOT NULL DEFAULT '{}'")
            db.execute("CREATE TABLE IF NOT EXISTS commands (request_id TEXT NOT NULL, machine_id TEXT NOT NULL, actor TEXT NOT NULL, capability TEXT NOT NULL, parameters TEXT NOT NULL, status TEXT NOT NULL, requested_at TEXT NOT NULL, completed_at TEXT, simulated INTEGER NOT NULL, verified INTEGER NOT NULL DEFAULT 0, confirmation TEXT, result TEXT NOT NULL DEFAULT '{}', error TEXT, PRIMARY KEY(machine_id, request_id), FOREIGN KEY(machine_id) REFERENCES machines(machine_id))")
            db.execute("CREATE TABLE IF NOT EXISTS access_events (id INTEGER PRIMARY KEY AUTOINCREMENT, at TEXT NOT NULL, actor TEXT NOT NULL, action TEXT NOT NULL, decision TEXT NOT NULL)")
            db.execute("UPDATE commands SET status='interrupted_unknown', completed_at=?, error='process_restarted_before_confirmation' WHERE status='pending'", (utc_now(),))
            if seed_demo and db.execute("SELECT COUNT(*) FROM machines").fetchone()[0] == 0:
                for machine_id, name, adapter_id in (
                    ("lab-compact-01", "Compact demo", "simulation.compact"),
                    ("lab-connected-01", "Connected demo", "simulation.connected"),
                ):
                    self.registry.get(adapter_id)
                    db.execute("INSERT INTO machines(machine_id,name,adapter_id,created_at,source,simulator_state,adapter_config) VALUES(?,?,?,?,?,?,?)", (machine_id, name, adapter_id, utc_now(), "local_simulator", "{}", "{}"))

    def _machine(self, machine_id: str) -> dict[str, Any]:
        with self.connect() as db:
            row = db.execute("SELECT * FROM machines WHERE machine_id=?", (machine_id,)).fetchone()
        if row is None:
            raise FleetError("machine_not_found", 404)
        return dict(row)

    def _adapter(self, machine: dict[str, Any]):
        machine_id = machine["machine_id"]
        with self._adapter_guard:
            if machine_id not in self._adapters:
                try:
                    adapter = self.registry.get(machine["adapter_id"], json.loads(machine["adapter_config"]))
                    if adapter.descriptor.simulated and hasattr(adapter, "load_state"):
                        adapter.load_state(json.loads(machine["simulator_state"]))
                    self._adapters[machine_id] = adapter
                except (LookupError, ValueError, json.JSONDecodeError) as exc:
                    raise FleetError("adapter_unavailable", 409) from exc
            return self._adapters[machine_id]

    def register_machine(self, body: object) -> dict[str, Any]:
        if (not isinstance(body, dict) or not {"machine_id", "name", "adapter_id"}.issubset(body)
                or set(body) - {"machine_id", "name", "adapter_id", "configuration"}):
            raise FleetError("expected_machine_id_name_adapter_id_and_optional_configuration")
        machine_id, name, adapter_id = body["machine_id"], body["name"], body["adapter_id"]
        if not isinstance(machine_id, str) or not re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9._-]{1,63}", machine_id):
            raise FleetError("invalid_machine_id")
        if not isinstance(name, str) or not name.strip() or len(name) > 100:
            raise FleetError("invalid_machine_name")
        if not isinstance(adapter_id, str):
            raise FleetError("invalid_adapter_id")
        configuration = body.get("configuration", {})
        if not isinstance(configuration, dict) or any(not isinstance(key, str) or not isinstance(value, str) or len(value) > 255 for key, value in configuration.items()):
            raise FleetError("invalid_adapter_configuration")
        try:
            descriptor = self.registry.describe(adapter_id)
        except LookupError as exc:
            raise FleetError("adapter_unavailable", 422) from exc
        allowed_config = set(descriptor.configuration)
        sensitive_names = ("token", "password", "secret", "private_key", "credential")
        embedded_credentials = any(
            urlsplit(value).username or urlsplit(value).password
            or any(any(marker in key.lower() for marker in sensitive_names) for key, _ in parse_qsl(urlsplit(value).query))
            for value in configuration.values()
        )
        if (not set(configuration).issubset(allowed_config)
                or any(any(part in key.lower() for part in sensitive_names) for key in configuration)
                or embedded_credentials):
            raise FleetError("adapter_configuration_not_allowed")
        try:
            adapter = self.registry.get(adapter_id, configuration)
        except LookupError as exc:
            raise FleetError("adapter_unavailable", 422) from exc
        except (ValueError, TypeError) as exc:
            raise FleetError("adapter_configuration_invalid", 422) from exc
        try:
            with self.connect() as db:
                source = "local_simulator" if adapter.descriptor.simulated else f"adapter:{adapter.descriptor.protocol}"
                db.execute("INSERT INTO machines(machine_id,name,adapter_id,created_at,source,simulator_state,adapter_config) VALUES(?,?,?,?,?,?,?)", (machine_id, name.strip(), adapter_id, utc_now(), source, "{}", json.dumps(configuration, sort_keys=True)))
        except sqlite3.IntegrityError as exc:
            raise FleetError("machine_already_registered", 409) from exc
        self._adapters[machine_id] = adapter
        return self.machine(machine_id)

    def machines(self) -> list[dict[str, Any]]:
        with self.connect() as db:
            ids = [row[0] for row in db.execute("SELECT machine_id FROM machines ORDER BY machine_id")]
        return [self.machine(machine_id) for machine_id in ids]

    def machine(self, machine_id: str) -> dict[str, Any]:
        machine = self._machine(machine_id)
        adapter = self._adapter(machine)
        machine.pop("simulator_state", None)
        machine.pop("adapter_config", None)
        with self._lock_for(machine_id):
            status = adapter.read_status(machine_id)
        machine.update({"manufacturer": adapter.descriptor.manufacturer,
                        "model": adapter.descriptor.model,
                        "protocol": adapter.descriptor.protocol,
                        "simulated": adapter.descriptor.simulated,
                        "status": status})
        return machine

    def capabilities(self, machine_id: str) -> list[dict[str, Any]]:
        machine = self._machine(machine_id)
        return [cap.to_dict() for cap in self._adapter(machine).capabilities()]

    def adapters(self) -> list[dict[str, Any]]:
        return self.registry.catalog()

    def resource(self, machine_id: str, capability: str) -> Any:
        machine = self._machine(machine_id)
        adapter = self._adapter(machine)
        cap = next((item for item in adapter.capabilities() if item.name == capability), None)
        if cap is None or cap.state != CapabilityState.AVAILABLE:
            raise FleetError("capability_unsupported", 422)
        with self._lock_for(machine_id):
            if capability == "status.read":
                return adapter.read_status(machine_id)
            if capability == "inventory.read":
                return adapter.read_inventory(machine_id)
            if capability == "diagnostics.read":
                return adapter.diagnostics(machine_id)
            if hasattr(adapter, "read_resource"):
                return adapter.read_resource(machine_id, capability)
            raise FleetError("capability_not_implemented", 501)

    @staticmethod
    def _command_from_row(row: sqlite3.Row) -> dict[str, Any]:
        return {"request_id": row["request_id"], "machine_id": row["machine_id"], "actor": row["actor"],
                "capability": row["capability"], "status": row["status"], "requested_at": row["requested_at"],
                "completed_at": row["completed_at"], "simulated": bool(row["simulated"]),
                "verified": bool(row["verified"]), "confirmation": row["confirmation"],
                "parameters": json.loads(row["parameters"]), "result": json.loads(row["result"]), "error": row["error"]}

    def run_command(self, machine_id: str, body: object, actor: str = "local-admin") -> dict[str, Any]:
        if not isinstance(body, dict) or set(body) != {"request_id", "capability", "parameters"}:
            raise FleetError("expected_request_id_capability_parameters")
        request_id, capability, parameters = body["request_id"], body["capability"], body["parameters"]
        try:
            uuid.UUID(request_id)
        except (ValueError, TypeError, AttributeError) as exc:
            raise FleetError("request_id_must_be_uuid") from exc
        if not isinstance(capability, str) or not isinstance(parameters, dict):
            raise FleetError("invalid_command_parameters")
        try:
            serialized_parameters = json.dumps(parameters, sort_keys=True, allow_nan=False)
        except (TypeError, ValueError) as exc:
            raise FleetError("invalid_command_parameters") from exc
        if len(serialized_parameters) > 2048:
            raise FleetError("invalid_command_parameters")
        machine = self._machine(machine_id)
        adapter = self._adapter(machine)
        requested_at = utc_now()
        try:
            with self.connect() as db:
                cursor = db.execute("INSERT OR IGNORE INTO commands(request_id,machine_id,actor,capability,parameters,status,requested_at,simulated) VALUES(?,?,?,?,?,?,?,?)",
                                    (request_id, machine_id, actor, capability, serialized_parameters, "pending", requested_at, int(adapter.descriptor.simulated)))
                if cursor.rowcount == 0:
                    row = db.execute("SELECT * FROM commands WHERE machine_id=? AND request_id=?", (machine_id, request_id)).fetchone()
                    result = self._command_from_row(row)
                    result["duplicate"] = True
                    return result
        except sqlite3.IntegrityError as exc:
            raise FleetError("machine_not_found", 404) from exc
        caps = {item.name: item for item in adapter.capabilities()}
        cap = caps.get(capability)
        with self._lock_for(machine_id):
            if cap is None or cap.state != CapabilityState.AVAILABLE:
                result = CommandResult(request_id, machine_id, actor, capability, "rejected", requested_at,
                                       utc_now(), adapter.descriptor.simulated, False, None, {}, "capability_unsupported").to_dict()
            elif not cap.writable or cap.method != capability:
                result = CommandResult(request_id, machine_id, actor, capability, "rejected", requested_at,
                                       utc_now(), adapter.descriptor.simulated, False, None, {}, "capability_is_read_only").to_dict()
            else:
                try:
                    result = adapter.execute(machine_id, request_id, actor, capability, parameters).to_dict()
                except Exception:
                    result = CommandResult(request_id, machine_id, actor, capability, "failed", requested_at,
                                           utc_now(), adapter.descriptor.simulated, False, None, {}, "adapter_execution_error").to_dict()
            with self.connect() as db:
                db.execute("UPDATE commands SET status=?,completed_at=?,verified=?,confirmation=?,result=?,error=? WHERE machine_id=? AND request_id=?",
                           (result["status"], result["completed_at"], int(result["verified"]), result["confirmation"],
                            json.dumps(result["result"], sort_keys=True), result["error"], machine_id, request_id))
                if adapter.descriptor.simulated and hasattr(adapter, "export_state"):
                    db.execute("UPDATE machines SET simulator_state=? WHERE machine_id=?",
                               (json.dumps(adapter.export_state(), sort_keys=True), machine_id))
        result["parameters"] = parameters
        result["duplicate"] = False
        return result

    def command_history(self, machine_id: str | None = None) -> list[dict[str, Any]]:
        with self.connect() as db:
            if machine_id:
                rows = db.execute("SELECT * FROM commands WHERE machine_id=? ORDER BY requested_at DESC LIMIT 100", (machine_id,)).fetchall()
            else:
                rows = db.execute("SELECT * FROM commands ORDER BY requested_at DESC LIMIT 100").fetchall()
        return [self._command_from_row(row) for row in rows]

    def record_access(self, actor: str, action: str, decision: str) -> None:
        with self.connect() as db:
            db.execute("INSERT INTO access_events(at,actor,action,decision) VALUES(?,?,?,?)",
                       (utc_now(), actor[:64], action[:256], decision[:32]))
            db.execute("DELETE FROM access_events WHERE id NOT IN (SELECT id FROM access_events ORDER BY id DESC LIMIT 5000)")

    def access_history(self) -> list[dict[str, Any]]:
        with self.connect() as db:
            rows = db.execute("SELECT id,at,actor,action,decision FROM access_events ORDER BY id DESC LIMIT 100").fetchall()
        return [dict(row) for row in rows]
