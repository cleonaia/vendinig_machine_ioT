"""End-to-end tests against a local MQTT 5 broker and the generic lab device.

Run explicitly with VENDING_MQTT_TEST_BROKER=127.0.0.1 after starting Mosquitto.
The test skips when Paho or the broker is unavailable; unit tests are not a
replacement for this network integration run.
"""
from __future__ import annotations

import json
import ipaddress
import os
import socket
import subprocess
import sys
import tempfile
import time
import unittest
import uuid
from pathlib import Path

from app.devices.mqtt_adapter import MqttAdapter, mqtt
from app.devices.registry import default_registry
from app.services.fleet_manager import FleetManager


class MqttBrokerIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if mqtt is None:
            raise unittest.SkipTest("paho-mqtt extra is not installed")
        cls.broker = os.getenv("VENDING_MQTT_TEST_BROKER", "127.0.0.1")
        cls.port = int(os.getenv("VENDING_MQTT_TEST_PORT", "1883"))
        try:
            if not ipaddress.ip_address(cls.broker).is_loopback:
                raise unittest.SkipTest("MQTT integration lab intentionally accepts loopback brokers only")
        except ValueError:
            if cls.broker.lower() != "localhost":
                raise unittest.SkipTest("MQTT integration lab intentionally accepts loopback brokers only")
        try:
            with socket.create_connection((cls.broker, cls.port), timeout=0.5):
                pass
        except OSError as exc:
            raise unittest.SkipTest(f"MQTT broker unavailable at {cls.broker}:{cls.port}: {exc}") from exc

    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.machine_id = f"it-{uuid.uuid4().hex[:12]}"
        self.lab_process = None
        self.env = os.environ.copy()
        self.env["VENDING_MQTT_TIMEOUT"] = "1.5"
        self.previous_timeout = os.environ.get("VENDING_MQTT_TIMEOUT")
        os.environ["VENDING_MQTT_TIMEOUT"] = "1.5"
        self.configuration = {"broker": self.broker, "port": str(self.port), "device_id": self.machine_id,
                              "tls": "false" if self.broker in {"127.0.0.1", "localhost", "::1"} else "true"}
        if self.configuration["tls"] == "true":
            ca_file = os.getenv("VENDING_MQTT_CA_FILE")
            if ca_file:
                self.configuration["ca_file"] = ca_file
        self.manager = FleetManager(Path(self.tempdir.name) / "integration.sqlite3", default_registry(), seed_demo=False)
        self.manager.register_machine({"machine_id": self.machine_id, "name": "MQTT integration lab",
                                       "adapter_id": "protocol.mqtt.generic.v1", "configuration": self.configuration})
        self.adapter = self.manager._adapter(self.manager._machine(self.machine_id))
        self._start_device()

    def tearDown(self):
        self._stop_device()
        self.adapter.disconnect()
        if self.previous_timeout is None:
            os.environ.pop("VENDING_MQTT_TIMEOUT", None)
        else:
            os.environ["VENDING_MQTT_TIMEOUT"] = self.previous_timeout
        self.tempdir.cleanup()

    def _start_device(self):
        self.lab_process = subprocess.Popen(
            [sys.executable, "-m", "app.devices.mqtt_lab_device", "--broker", self.broker,
             "--port", str(self.port), "--device-id", self.machine_id],
            cwd=Path(__file__).resolve().parents[1], env=self.env,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    def _stop_device(self):
        if self.lab_process and self.lab_process.poll() is None:
            self.lab_process.terminate()
            try:
                self.lab_process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                self.lab_process.kill()
                self.lab_process.wait(timeout=3)

    def test_telemetry_ping_duplicate_disconnect_timeout_and_recovery(self):
        telemetry = {}
        deadline = time.monotonic() + 8
        while time.monotonic() < deadline:
            telemetry = self.manager.resource(self.machine_id, "telemetry.read")
            if telemetry.get("temperature_c") == 22.0:
                break
            time.sleep(0.1)
        self.assertEqual(telemetry.get("data_origin"), "mqtt_device")
        self.assertEqual(telemetry.get("temperature_c"), 22.0)

        request_id = str(uuid.uuid4())
        body = {"request_id": request_id, "capability": "device.ping", "parameters": {}}
        confirmed = self.manager.run_command(self.machine_id, body, actor="integration-test")
        self.assertEqual(confirmed["status"], "confirmed")
        self.assertTrue(confirmed["verified"])
        self.assertTrue(confirmed["result"]["broker_acknowledged"])
        self.assertTrue(confirmed["result"]["application_confirmed"])
        self.assertTrue(self.manager.run_command(self.machine_id, body, actor="integration-test")["duplicate"])

        db_path = Path(self.tempdir.name) / "integration.sqlite3"
        self.adapter.disconnect()
        self.manager = FleetManager(db_path, default_registry(), seed_demo=False)
        self.adapter = self.manager._adapter(self.manager._machine(self.machine_id))
        duplicate_after_restart = self.manager.run_command(self.machine_id, body, actor="integration-test")
        self.assertTrue(duplicate_after_restart["duplicate"])
        self.assertEqual(duplicate_after_restart["status"], "confirmed")

        # Remember the current retained telemetry before stopping the device.
        # A cached value from before the restart must not count as recovery.
        previous_telemetry_id = self.manager.resource(self.machine_id, "telemetry.read").get("message_id")

        self._stop_device()
        timed_out = self.manager.run_command(self.machine_id,
                                             {"request_id": str(uuid.uuid4()), "capability": "device.ping", "parameters": {}},
                                             actor="integration-test")
        self.assertEqual(timed_out["status"], "timed_out")
        self.assertTrue(timed_out["result"]["broker_acknowledged"])
        self.assertFalse(timed_out["result"]["application_confirmed"])
        self.assertFalse(timed_out["verified"])

        self._start_device()
        deadline = time.monotonic() + 5
        telemetry = {}
        while time.monotonic() < deadline:
            telemetry = self.manager.resource(self.machine_id, "telemetry.read")
            if (telemetry.get("temperature_c") == 22.0
                    and telemetry.get("message_id") != previous_telemetry_id):
                break
            time.sleep(0.05)
        self.assertEqual(telemetry.get("temperature_c"), 22.0)
        self.assertNotEqual(telemetry.get("message_id"), previous_telemetry_id,
                            "device restart must produce fresh telemetry before recovery is tested")
        recovered = self.manager.run_command(self.machine_id,
                                             {"request_id": str(uuid.uuid4()), "capability": "device.ping", "parameters": {}},
                                             actor="integration-test")
        self.assertEqual(recovered["status"], "confirmed")
        self.assertTrue(recovered["verified"])

    def test_invalid_mqtt_payload_does_not_leak_or_become_telemetry(self):
        publisher = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, protocol=mqtt.MQTTv5)
        username, password = os.getenv("VENDING_MQTT_USERNAME"), os.getenv("VENDING_MQTT_PASSWORD")
        if username or password:
            publisher.username_pw_set(username or None, password or None)
        tls = self.configuration["tls"] == "true"
        if tls:
            import ssl
            publisher.tls_set(ca_certs=self.configuration.get("ca_file") or None,
                              cert_reqs=ssl.CERT_REQUIRED, tls_version=ssl.PROTOCOL_TLS_CLIENT)
        publisher.connect(self.broker, self.port, keepalive=15)
        publisher.loop_start()
        try:
            adapter = self.adapter
            adapter._require_client(self.machine_id)
            previous_telemetry = adapter._telemetry.get(self.machine_id)
            adapter._last_error = None
            payload = json.dumps({"schema_version": 1, "message_id": str(uuid.uuid4()), "type": "telemetry",
                                  "device_id": self.machine_id, "timestamp": "2026-01-01T00:00:00Z",
                                  "payload": {"password": "synthetic-secret-marker"}})
            info = publisher.publish(adapter.telemetry_topic, payload, qos=1)
            info.wait_for_publish(timeout=2)
            deadline = time.monotonic() + 2
            while time.monotonic() < deadline and adapter._last_error is None:
                time.sleep(0.05)
            self.assertEqual(adapter._last_error, "invalid_or_unexpected_message")
            self.assertEqual(adapter._telemetry.get(self.machine_id), previous_telemetry)
            public = json.dumps(self.manager.machine(self.machine_id), sort_keys=True)
            self.assertNotIn("synthetic-secret-marker", public)
            self.assertNotIn("password", public.lower())
        finally:
            publisher.disconnect()
            publisher.loop_stop()


if __name__ == "__main__":
    unittest.main()
