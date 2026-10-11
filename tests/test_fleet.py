import tempfile
import unittest
import uuid
import sqlite3
from pathlib import Path

from app.devices.device_adapter import AdapterDescriptor
from app.devices.registry import default_registry
from app.services.fleet_manager import FleetError, FleetManager


class FleetManagerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp.name) / "fleet.sqlite3"
        self.fleet = FleetManager(self.db_path)

    def tearDown(self):
        self.temp.cleanup()

    def test_default_fleet_has_multiple_explicitly_simulated_profiles(self):
        machines = self.fleet.machines()
        self.assertEqual({m["machine_id"] for m in machines}, {"lab-compact-01", "lab-connected-01"})
        self.assertTrue(all(m["simulated"] for m in machines))
        self.assertTrue(all(m["protocol"] == "simulator://in-process" for m in machines))

    def test_registry_exposes_mqtt_transport_without_claiming_vending_support(self):
        catalog = default_registry().catalog()
        by_id = {adapter["adapter_id"]: adapter for adapter in catalog}
        self.assertEqual(set(by_id), {"simulation.compact", "simulation.connected", "protocol.mqtt.generic.v1"})
        self.assertTrue(by_id["simulation.compact"]["simulated"])
        self.assertTrue(by_id["simulation.connected"]["simulated"])
        mqtt_capabilities = {capability["name"] for capability in by_id["protocol.mqtt.generic.v1"]["capabilities"]}
        self.assertTrue({"status.read", "telemetry.read", "diagnostics.read", "device.ping"}.issubset(mqtt_capabilities))
        self.assertFalse(by_id["protocol.mqtt.generic.v1"]["simulated"])

    def test_mqtt_device_registers_through_existing_fleet_manager(self):
        machine = self.fleet.register_machine({
            "machine_id": "lab-mqtt-01", "name": "MQTT lab device",
            "adapter_id": "protocol.mqtt.generic.v1",
            "configuration": {"broker": "127.0.0.1", "port": "1883", "device_id": "lab-mqtt-01"},
        })
        self.assertFalse(machine["simulated"])
        self.assertEqual(machine["protocol"], "MQTT 5.0")
        caps = {item["name"]: item for item in self.fleet.capabilities("lab-mqtt-01")}
        self.assertEqual(caps["telemetry.read"]["state"], "available")
        self.assertEqual(caps["vend.simulate"]["state"], "unsupported")

    def test_capabilities_differ_by_simulator_profile(self):
        compact = {c["name"]: c for c in self.fleet.capabilities("lab-compact-01")}
        connected = {c["name"]: c for c in self.fleet.capabilities("lab-connected-01")}
        self.assertEqual(compact["sales.read"]["state"], "unsupported")
        self.assertEqual(connected["sales.read"]["state"], "available")
        self.assertEqual(connected["sales.read"]["source"], "local_simulator")
        self.assertFalse(connected["sales.read"]["writable"])
        self.assertTrue(connected["vend.simulate"]["writable"])

    def test_register_machine_persists_and_rejects_unknown_adapters(self):
        machine = self.fleet.register_machine({"machine_id": "test-vm-01", "name": "Test", "adapter_id": "simulation.compact"})
        self.assertEqual(machine["machine_id"], "test-vm-01")
        with self.assertRaises(FleetError) as error:
            self.fleet.register_machine({"machine_id": "unknown-vm-01", "name": "Unknown", "adapter_id": "vendor.real"})
        self.assertEqual(error.exception.code, "adapter_unavailable")
        restarted = FleetManager(self.db_path)
        self.assertIn("test-vm-01", {m["machine_id"] for m in restarted.machines()})

    def test_adapter_configuration_is_allowlisted_and_persisted_without_secrets(self):
        seen = []

        class ConfigAdapter:
            def __init__(self, config):
                self.configuration = config
                self.descriptor = AdapterDescriptor("test.http", "TestCo", "Model X", "https", ("endpoint",),
                                                     ("TEST_API_TOKEN",), 2.0, "reconnect", (), False)
                seen.append(config)

            def capabilities(self): return []
            def read_status(self, machine_id): return {"machine_id": machine_id, "simulated": False}
            def read_inventory(self, machine_id): return []
            def diagnostics(self, machine_id): return {}
            def read_resource(self, machine_id, capability): return {}
            def recover(self, machine_id): return {}
            def execute(self, machine_id, command_id, actor, capability, parameters): raise AssertionError

        from app.devices.registry import AdapterRegistry
        registry = AdapterRegistry()
        descriptor = ConfigAdapter({}).descriptor
        registry.register(lambda config: ConfigAdapter(config), descriptor)
        fleet = FleetManager(self.db_path, registry=registry, seed_demo=False)
        machine = fleet.register_machine({"machine_id": "configured-01", "name": "Configured", "adapter_id": "test.http", "configuration": {"endpoint": "https://localhost/api"}})
        self.assertEqual(machine["protocol"], "https")
        self.assertNotIn("adapter_config", machine)
        self.assertEqual(fleet.machine("configured-01")["model"], "Model X")
        self.assertIn({"endpoint": "https://localhost/api"}, seen)
        with self.assertRaises(FleetError):
            fleet.register_machine({"machine_id": "bad-config-01", "name": "Bad", "adapter_id": "test.http", "configuration": {"api_token": "secret"}})
        with self.assertRaises(FleetError):
            fleet.register_machine({"machine_id": "bad-url-01", "name": "Bad URL", "adapter_id": "test.http", "configuration": {"endpoint": "https://user:pass@example.test/api"}})

    def test_commands_are_confirmed_as_simulated_and_idempotent(self):
        request_id = str(uuid.uuid4())
        payload = {"request_id": request_id, "capability": "diagnostics.run", "parameters": {}}
        first = self.fleet.run_command("lab-connected-01", payload)
        duplicate = self.fleet.run_command("lab-connected-01", payload)
        self.assertEqual(first["status"], "confirmed")
        self.assertTrue(first["verified"])
        self.assertTrue(first["simulated"])
        self.assertTrue(duplicate["duplicate"])
        self.assertEqual(len(self.fleet.command_history("lab-connected-01")), 1)

    def test_pending_command_is_marked_unknown_after_manager_restart(self):
        request_id = str(uuid.uuid4())
        with sqlite3.connect(self.db_path) as db:
            db.execute("INSERT INTO commands(request_id,machine_id,actor,capability,parameters,status,requested_at,simulated) VALUES(?,?,?,?,?,?,?,?)",
                       (request_id, "lab-connected-01", "local-admin", "device.restart", "{}", "pending", "2026-01-01T00:00:00+00:00", 1))
        restarted = FleetManager(self.db_path)
        command = next(item for item in restarted.command_history() if item["request_id"] == request_id)
        self.assertEqual(command["status"], "interrupted_unknown")
        self.assertFalse(command["verified"])

    def test_access_audit_records_denials_without_credentials(self):
        self.fleet.record_access("anonymous", "/api/machines", "authentication_denied")
        item = self.fleet.access_history()[0]
        self.assertEqual(item["actor"], "anonymous")
        self.assertEqual(item["decision"], "authentication_denied")
        self.assertNotIn("token", item)

    def test_unsupported_command_and_read_only_capability_are_rejected(self):
        unsupported = self.fleet.run_command("lab-compact-01", {"request_id": str(uuid.uuid4()), "capability": "device.restart", "parameters": {}})
        readonly = self.fleet.run_command("lab-connected-01", {"request_id": str(uuid.uuid4()), "capability": "sales.read", "parameters": {}})
        self.assertEqual(unsupported["status"], "rejected")
        self.assertEqual(unsupported["error"], "capability_unsupported")
        self.assertEqual(readonly["status"], "rejected")
        self.assertEqual(readonly["error"], "capability_is_read_only")
        self.assertEqual(len(self.fleet.command_history()), 2)

    def test_simulated_timeout_is_recorded_without_verification(self):
        result = self.fleet.run_command("lab-connected-01", {"request_id": str(uuid.uuid4()), "capability": "diagnostics.run", "parameters": {"simulation_fault": "timeout"}})
        self.assertEqual(result["status"], "timed_out")
        self.assertFalse(result["verified"])
        self.assertTrue(result["simulated"])
        self.assertEqual(self.fleet.command_history("lab-connected-01")[0]["status"], "timed_out")

    def test_simulated_vend_updates_inventory_and_sales(self):
        before = self.fleet.resource("lab-connected-01", "sales.read")["total_count"]
        initial_stock = next(item["stock"] for item in self.fleet.resource("lab-connected-01", "inventory.read") if item["product_id"] == "water")
        result = self.fleet.run_command("lab-connected-01", {"request_id": str(uuid.uuid4()), "capability": "vend.simulate", "parameters": {"product_id": "water"}})
        new_stock = next(item["stock"] for item in self.fleet.resource("lab-connected-01", "inventory.read") if item["product_id"] == "water")
        self.assertTrue(result["simulated"])
        self.assertEqual(new_stock, initial_stock - 1)
        self.assertEqual(self.fleet.resource("lab-connected-01", "sales.read")["total_count"], before + 1)
        restarted = FleetManager(self.db_path)
        persisted_stock = next(item["stock"] for item in restarted.resource("lab-connected-01", "inventory.read") if item["product_id"] == "water")
        persisted_sales = restarted.resource("lab-connected-01", "sales.read")["total_count"]
        self.assertEqual(persisted_stock, initial_stock - 1)
        self.assertEqual(persisted_sales, before + 1)

    def test_simulated_disconnect_and_recovery_change_reported_state(self):
        disconnected = self.fleet.run_command("lab-connected-01", {"request_id": str(uuid.uuid4()), "capability": "diagnostics.run", "parameters": {"simulation_fault": "disconnect"}})
        self.assertEqual(disconnected["status"], "disconnected")
        self.assertEqual(self.fleet.resource("lab-connected-01", "status.read")["connection"], "simulated_offline")
        recovered = self.fleet.run_command("lab-connected-01", {"request_id": str(uuid.uuid4()), "capability": "connection.recover", "parameters": {}})
        self.assertTrue(recovered["verified"])
        self.assertEqual(self.fleet.resource("lab-connected-01", "status.read")["connection"], "simulated_online")

    def test_machine_and_command_inputs_are_validated(self):
        for payload in (
            {"machine_id": "../machine", "name": "bad", "adapter_id": "simulation.compact"},
            {"machine_id": "safe-id", "name": "", "adapter_id": "simulation.compact"},
            {"machine_id": "safe-id", "name": "x", "adapter_id": "simulation.compact", "extra": True},
        ):
            with self.subTest(payload=payload), self.assertRaises(FleetError):
                self.fleet.register_machine(payload)
        with self.assertRaises(FleetError) as error:
            self.fleet.run_command("lab-connected-01", {"request_id": "duplicate", "capability": "diagnostics.run", "parameters": {}})
        self.assertEqual(error.exception.code, "request_id_must_be_uuid")


if __name__ == "__main__":
    unittest.main()
