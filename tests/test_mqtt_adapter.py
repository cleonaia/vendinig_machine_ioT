from __future__ import annotations

import json
import unittest
import uuid
from types import SimpleNamespace
from unittest.mock import Mock, patch

from app.devices.mqtt_adapter import MqttAdapter


class FakePublish:
    rc = 0
    def wait_for_publish(self, timeout=None):
        return None
    def is_published(self):
        return True


class FakeClient:
    def __init__(self, adapter, respond=True):
        self.adapter = adapter
        self.respond = respond
        self.payloads = []

    def publish(self, topic, payload, qos):
        self.payloads.append((topic, payload, qos))
        if self.respond:
            command = json.loads(payload)
            response = {"schema_version": 1, "message_id": str(uuid.uuid4()), "type": "command_result",
                        "command_id": command["command_id"], "device_id": command["device_id"],
                        "status": "confirmed", "result": {"device_state": "ready", "device_id": command["device_id"]}}
            self.adapter._on_message(self, None, SimpleNamespace(topic=self.adapter.result_topic,
                                                                  payload=json.dumps(response).encode()))
        return FakePublish()


class MqttAdapterTests(unittest.TestCase):
    def setUp(self):
        self.adapter = MqttAdapter({"device_id": "lab-node", "telemetry_topic": "devices/{machine_id}/telemetry",
                                    "command_topic": "devices/{machine_id}/commands",
                                    "result_topic": "devices/{machine_id}/results"})
        self.adapter._connected.set()

    def test_schema_strict_duplicate_and_telemetry(self):
        telemetry = {"schema_version": 1, "message_id": str(uuid.uuid4()), "type": "telemetry",
                     "device_id": "lab-node", "timestamp": "2026-01-01T00:00:00Z",
                     "payload": {"temperature_c": 20.5}}
        msg = SimpleNamespace(topic="devices/machine-01/telemetry", payload=json.dumps(telemetry).encode())
        self.adapter.telemetry_topic = msg.topic
        self.adapter._on_message(None, None, msg)
        self.assertEqual(self.adapter._telemetry["lab-node"]["temperature_c"], 20.5)
        before = dict(self.adapter._telemetry["lab-node"])
        self.adapter._on_message(None, None, msg)
        self.assertEqual(self.adapter._telemetry["lab-node"], before)
        invalid = SimpleNamespace(topic=msg.topic, payload=b'{"schema_version":1,"schema_version":1}')
        self.adapter._on_message(None, None, invalid)
        self.assertEqual(self.adapter._last_error, "invalid_or_unexpected_message")

    def test_unallowlisted_telemetry_field_is_rejected(self):
        telemetry = {"schema_version": 1, "message_id": str(uuid.uuid4()), "type": "telemetry",
                     "device_id": "lab-node", "timestamp": "2026-01-01T00:00:00Z",
                     "payload": {"password": "must-not-be-stored"}}
        topic = "devices/machine-01/telemetry"
        self.adapter.telemetry_topic = topic
        self.adapter._on_message(None, None, SimpleNamespace(topic=topic, payload=json.dumps(telemetry).encode()))
        self.assertNotIn("lab-node", self.adapter._telemetry)
        self.assertEqual(self.adapter._last_error, "invalid_or_unexpected_message")

    def test_command_waits_for_correlated_application_ack(self):
        self.adapter.device_id = "lab-node"
        self.adapter._client = FakeClient(self.adapter)
        with patch.object(self.adapter, "_require_client", return_value=self.adapter._client):
            result = self.adapter.execute("machine-01", str(uuid.uuid4()), "operator", "device.ping", {})
        self.assertEqual(result.status, "confirmed")
        self.assertTrue(result.verified)
        self.assertFalse(result.simulated)

    def test_command_timeout_is_not_reported_as_success(self):
        self.adapter.device_id = "lab-node"
        self.adapter.timeout = 0.1
        self.adapter._client = FakeClient(self.adapter, respond=False)
        with patch.object(self.adapter, "_require_client", return_value=self.adapter._client):
            result = self.adapter.execute("machine-01", str(uuid.uuid4()), "operator", "device.ping", {})
        self.assertEqual(result.status, "timed_out")
        self.assertFalse(result.verified)
        self.assertTrue(result.result["broker_acknowledged"])
        self.assertFalse(result.result["application_confirmed"])

    def test_capabilities_do_not_claim_vending_control(self):
        capabilities = {item.name: item for item in self.adapter.capabilities()}
        self.assertEqual({name for name, cap in capabilities.items() if cap.state.value == "available"},
                         {"status.read", "telemetry.read", "diagnostics.read", "device.ping"})
        self.assertEqual(capabilities["vend.simulate"].state.value, "unsupported")
        self.assertFalse(capabilities["vend.simulate"].writable)

    def test_disconnect_marks_transport_unavailable(self):
        self.adapter._on_disconnect(None, None, None, 1, None)
        self.assertFalse(self.adapter._connected.is_set())

    def test_successful_connection_subscribes_only_device_topics(self):
        client = SimpleNamespace(subscribe=Mock(side_effect=[(0, 11), (0, 12)]))
        self.adapter.result_topic = "devices/lab-node/results"
        self.adapter.telemetry_topic = "devices/lab-node/telemetry"
        self.adapter._on_connect(client, None, None, 0, None)
        self.assertTrue(self.adapter._connected.is_set())
        self.assertEqual(client.subscribe.call_count, 2)
        self.assertFalse(self.adapter._subscriptions_ready.is_set())
        self.adapter._on_subscribe(client, None, 11, [0], None)
        self.adapter._on_subscribe(client, None, 12, [0], None)
        self.assertTrue(self.adapter._subscriptions_ready.is_set())

    def test_broker_topic_acl_denial_does_not_mark_ready(self):
        client = SimpleNamespace(subscribe=Mock(side_effect=[(0, 21), (0, 22)]))
        self.adapter._on_connect(client, None, None, 0, None)
        self.adapter._on_subscribe(client, None, 21, [SimpleNamespace(is_failure=True)], None)
        self.assertFalse(self.adapter._connected.is_set())
        self.assertFalse(self.adapter._subscriptions_ready.is_set())
        self.assertEqual(self.adapter._last_error, "broker_subscription_denied")


if __name__ == "__main__":
    unittest.main()
