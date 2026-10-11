"""MQTT 5 adapter for generic IoT controllers using the documented lab schema.

MQTT transport support does not imply vending-machine control. Only telemetry
and the generic device.ping round trip are implemented by this adapter.
"""
from __future__ import annotations

import json
import ipaddress
import os
import re
import ssl
import threading
import time
from datetime import datetime, timezone
from typing import Any
import uuid

from app.devices.device_adapter import AdapterDescriptor
from app.domain.capabilities import Capability, CapabilityState, CommandResult

try:
    import paho.mqtt.client as mqtt
except ImportError:  # Allows simulator-only operation when the optional extra is absent.
    mqtt = None


SCHEMA_VERSION = 1
_TOPIC_PART = re.compile(r"^[A-Za-z0-9._-]{1,96}$")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class MqttAdapter:
    """Lazy, synchronous facade over paho's network loop.

    Passwords are read from an environment variable and never enter machine
    configuration, MQTT diagnostics, or command results.
    """

    CONFIGURATION = ("broker", "port", "username", "tls", "device_id",
                     "telemetry_topic", "command_topic", "result_topic", "ca_file")

    def __init__(self, configuration: dict[str, Any] | None = None):
        cfg = dict(configuration or {})
        self.broker = str(cfg.get("broker", os.getenv("VENDING_MQTT_BROKER", "127.0.0.1")))
        self.port = int(cfg.get("port", os.getenv("VENDING_MQTT_PORT", "1883")))
        self.username = str(cfg.get("username", os.getenv("VENDING_MQTT_USERNAME", "")))
        tls_value = cfg.get("tls", os.getenv("VENDING_MQTT_TLS", "false"))
        self.tls = tls_value is True or str(tls_value).lower() in {"1", "true", "yes"}
        self.ca_file = cfg.get("ca_file", os.getenv("VENDING_MQTT_CA_FILE"))
        self.device_id = str(cfg.get("device_id", os.getenv("VENDING_MQTT_DEVICE_ID", "{machine_id}")))
        self._device_id_template = self.device_id
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{1,63}|\{machine_id\}", self.device_id):
            raise ValueError("invalid MQTT device id")
        prefix = f"devices/{self.device_id}"
        self._telemetry_template = str(cfg.get("telemetry_topic", os.getenv("VENDING_MQTT_TELEMETRY_TOPIC", prefix + "/telemetry")))
        self._command_template = str(cfg.get("command_topic", os.getenv("VENDING_MQTT_COMMAND_TOPIC", prefix + "/commands")))
        self._result_template = str(cfg.get("result_topic", os.getenv("VENDING_MQTT_RESULT_TOPIC", prefix + "/results")))
        self.telemetry_topic = self._telemetry_template
        self.command_topic = self._command_template
        self.result_topic = self._result_template
        self.timeout = float(os.getenv("VENDING_MQTT_TIMEOUT", "5"))
        self._validate_config()
        self.descriptor = AdapterDescriptor(
            adapter_id="protocol.mqtt.generic.v1", manufacturer=None, model="Generic MQTT IoT device",
            protocol="MQTT 5.0", configuration=self.CONFIGURATION,
            authentication=("username/password via VENDING_MQTT_USERNAME and VENDING_MQTT_PASSWORD", "TLS optional; required for remote brokers"),
            default_timeout_seconds=self.timeout, recovery_method="reconnect_with_backoff",
            limitations=("Generic telemetry schema only; no vending controller compatibility implied.",
                         "Only device.ping is writable; vending inventory, payment and dispensing require a vendor/controller adapter."),
            simulated=False)
        self._lock = threading.RLock()
        self._connected = threading.Event()
        self._subscriptions_ready = threading.Event()
        self._subscription_mids: set[int] = set()
        self._disconnected = threading.Event()
        self._telemetry: dict[str, dict[str, Any]] = {}
        self._last_error: str | None = None
        self._seen_messages: set[str] = set()
        self._pending: dict[str, dict[str, Any]] = {}
        self._results: dict[str, dict[str, Any]] = {}
        self._response_event = threading.Event()
        self._client = None

    def _validate_config(self) -> None:
        if not self.broker or len(self.broker) > 253 or not 1 <= self.port <= 65535:
            raise ValueError("invalid MQTT broker configuration")
        try:
            loopback = ipaddress.ip_address(self.broker).is_loopback
        except ValueError:
            loopback = self.broker.lower() == "localhost"
        if not loopback and not self.tls:
            raise ValueError("TLS is required for non-loopback MQTT brokers")
        if not 0.1 <= self.timeout <= 60:
            raise ValueError("invalid MQTT timeout")
        for topic in (self.telemetry_topic, self.command_topic, self.result_topic):
            # Substitutions are validated after machine_id is applied.
            if len(topic) > 240 or "#" in topic or "+" in topic or "\x00" in topic:
                raise ValueError("invalid MQTT topic")
        if self.ca_file and not self.tls:
            raise ValueError("ca_file requires TLS")

    def _topic(self, template: str, machine_id: str) -> str:
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{1,63}", machine_id):
            raise ValueError("invalid machine id")
        topic = template.replace("{machine_id}", machine_id)
        if len(topic) > 240 or any(not _TOPIC_PART.fullmatch(part) for part in topic.split("/")):
            raise ValueError("invalid MQTT topic")
        return topic

    def _bind_machine(self, machine_id: str) -> None:
        self.device_id = self._device_id_template.replace("{machine_id}", machine_id)
        self.telemetry_topic = self._topic(self._telemetry_template, machine_id)
        self.command_topic = self._topic(self._command_template, machine_id)
        self.result_topic = self._topic(self._result_template, machine_id)

    def _require_client(self, machine_id: str):
        if mqtt is None:
            raise RuntimeError("MQTT dependency missing; install project with pip install -e '.[mqtt]'")
        self._bind_machine(machine_id)
        if self._client is not None:
            if not self._connected.wait(self.timeout):
                raise TimeoutError("MQTT broker connection timed out")
            if not self._subscriptions_ready.wait(self.timeout):
                raise TimeoutError("MQTT topic subscription timed out")
            return self._client
        with self._lock:
            if self._client is not None:
                return self._client
            client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=f"vending-admin-{uuid.uuid4().hex[:12]}", protocol=mqtt.MQTTv5)
            password = os.getenv("VENDING_MQTT_PASSWORD")
            if self.username or password:
                client.username_pw_set(self.username or None, password or None)
            if self.tls:
                client.tls_set(ca_certs=self.ca_file or None, cert_reqs=ssl.CERT_REQUIRED, tls_version=ssl.PROTOCOL_TLS_CLIENT)
            client.on_connect = self._on_connect
            client.on_subscribe = self._on_subscribe
            client.on_disconnect = self._on_disconnect
            client.on_message = self._on_message
            client.connect_async(self.broker, self.port, keepalive=30)
            client.loop_start()
            self._client = client
        if not self._connected.wait(self.timeout):
            self._last_error = "broker_connection_timeout"
            raise TimeoutError("MQTT broker connection timed out")
        if not self._subscriptions_ready.wait(self.timeout):
            self._last_error = "broker_subscription_timeout"
            raise TimeoutError("MQTT topic subscription timed out")
        return self._client

    def _on_connect(self, client, userdata, flags, reason_code, properties):
        if reason_code != 0:
            self._last_error = "broker_connection_refused"
            self._connected.clear()
            return
        self._last_error = None
        self._disconnected.clear()
        self._subscriptions_ready.clear()
        self._subscription_mids.clear()
        self._connected.set()
        for topic in (self.result_topic, self.telemetry_topic):
            rc, mid = client.subscribe(topic, qos=1)
            if rc != 0:
                self._last_error = "broker_subscription_failed"
                self._connected.clear()
                return
            self._subscription_mids.add(mid)
        if not self._subscription_mids:
            self._subscriptions_ready.set()

    def _on_subscribe(self, client, userdata, mid, reason_code_list, properties):
        with self._lock:
            if mid not in self._subscription_mids:
                return
            if any(getattr(reason_code, "is_failure", False) for reason_code in reason_code_list):
                self._last_error = "broker_subscription_denied"
                self._connected.clear()
                return
            self._subscription_mids.discard(mid)
            if not self._subscription_mids:
                self._subscriptions_ready.set()

    def _on_disconnect(self, client, userdata, disconnect_flags, reason_code, properties=None):
        self._connected.clear()
        self._subscriptions_ready.clear()
        self._disconnected.set()
        if reason_code != 0:
            self._last_error = "broker_disconnected"

    @staticmethod
    def _decode(payload: bytes) -> dict[str, Any]:
        if len(payload) > 8192:
            raise ValueError("message_too_large")
        def pairs(items):
            result = {}
            for key, value in items:
                if key in result:
                    raise ValueError("duplicate_json_key")
                result[key] = value
            return result
        obj = json.loads(payload.decode("utf-8", "strict"), object_pairs_hook=pairs,
                         parse_constant=lambda _: (_ for _ in ()).throw(ValueError("invalid_json_number")))
        if not isinstance(obj, dict):
            raise ValueError("message_must_be_object")
        return obj

    def _on_message(self, client, userdata, message):
        try:
            obj = self._decode(message.payload)
            if type(obj.get("schema_version")) is not int or obj.get("schema_version") != SCHEMA_VERSION or not isinstance(obj.get("message_id"), str):
                raise ValueError("invalid_envelope")
            message_id = obj["message_id"]
            uuid.UUID(message_id)
            with self._lock:
                if message_id in self._seen_messages:
                    return
                if message.topic == self.telemetry_topic:
                    if set(obj) != {"schema_version", "message_id", "type", "device_id", "timestamp", "payload"} or obj["type"] != "telemetry" or not isinstance(obj["device_id"], str) or not isinstance(obj["timestamp"], str) or not isinstance(obj["payload"], dict):
                        raise ValueError("invalid_telemetry")
                    if len(obj["timestamp"]) > 40:
                        raise ValueError("invalid_timestamp")
                    datetime.fromisoformat(obj["timestamp"].replace("Z", "+00:00"))
                    if obj["device_id"] != self.device_id:
                        raise ValueError("unexpected_device")
                    payload = obj["payload"]
                    numeric_fields = {"temperature_c", "humidity_pct", "uptime_s", "signal_rssi_dbm"}
                    if (not payload or set(payload) - (numeric_fields | {"device_state"})
                            or any(type(value) not in {int, float} for key, value in payload.items() if key in numeric_fields)
                            or any(not isinstance(value, str) or len(value) > 64 for key, value in payload.items() if key == "device_state")):
                        raise ValueError("invalid_telemetry_payload")
                    self._remember_message(message_id)
                    self._telemetry[obj["device_id"]] = {**obj["payload"], "timestamp": obj["timestamp"], "message_id": message_id, "data_origin": "mqtt_device"}
                elif message.topic == self.result_topic:
                    if set(obj) != {"schema_version", "message_id", "type", "command_id", "device_id", "status", "result"} or obj["type"] != "command_result" or not isinstance(obj["command_id"], str) or not isinstance(obj["device_id"], str) or obj["status"] not in {"confirmed", "rejected", "failed"} or not isinstance(obj["result"], dict):
                        raise ValueError("invalid_command_result")
                    expected_device = self._pending.get(obj["command_id"], {}).get("device_id")
                    result = obj["result"]
                    valid_result = (set(result) == {"device_state", "device_id"}
                                    and isinstance(result["device_state"], str) and len(result["device_state"]) <= 64
                                    and result["device_id"] == obj["device_id"])
                    if expected_device == obj["device_id"] and valid_result:
                        self._remember_message(message_id)
                        self._results[obj["command_id"]] = obj
                        self._response_event.set()
                    else:
                        raise ValueError("uncorrelated_command_result")
                else:
                    raise ValueError("unexpected_topic")
        except Exception:
            # Payload and credentials are deliberately never included in logs/errors.
            self._last_error = "invalid_or_unexpected_message"

    def _remember_message(self, message_id: str) -> None:
        self._seen_messages.add(message_id)
        if len(self._seen_messages) > 10000:
            # IDs are message-level only; command idempotency is retained by the
            # fleet database and is never inferred from this short dedup cache.
            self._seen_messages.clear()
            self._seen_messages.add(message_id)

    def disconnect(self) -> None:
        with self._lock:
            client, self._client = self._client, None
        if client:
            client.disconnect()
            client.loop_stop()
        self._connected.clear()
        self._subscriptions_ready.clear()

    def capabilities(self) -> list[Capability]:
        implemented = [Capability("status.read", CapabilityState.AVAILABLE, "mqtt_connection", "read_status", False,
                                  "Broker/device connection must be verified in the target environment."),
                       Capability("telemetry.read", CapabilityState.AVAILABLE, "mqtt_telemetry_schema_v1", "read_resource", False,
                                  "Requires a peer that publishes the versioned schema."),
                       Capability("diagnostics.read", CapabilityState.AVAILABLE, "mqtt_transport_diagnostics", "diagnostics", True),
                       Capability("device.ping", CapabilityState.AVAILABLE, "generic_mqtt_command_schema_v1", "device.ping", False,
                                  "Connectivity check only; does not operate vending hardware.", True)]
        vending_capabilities = ("alarms.read", "inventory.read", "inventory.adjust", "sales.read", "payment.status",
                                "diagnostics.run", "maintenance.set", "device.restart", "vend.simulate")
        unsupported = [Capability(name, CapabilityState.UNSUPPORTED, "no_vendor_controller_schema", None, False,
                                  "Requires a documented and tested vending-controller adapter.")
                       for name in vending_capabilities]
        return implemented + unsupported

    def read_status(self, machine_id: str) -> dict[str, Any]:
        try:
            self._require_client(machine_id)
            return {"machine_id": machine_id, "connection": "connected" if self._connected.is_set() else "disconnected",
                    "availability": "unknown", "last_communication": self._telemetry.get(self._device_id_template.replace("{machine_id}", machine_id), {}).get("timestamp"),
                    "data_origin": "mqtt_transport", "simulated": False, "last_error": self._last_error}
        except (OSError, TimeoutError, RuntimeError):
            return {"machine_id": machine_id, "connection": "disconnected", "availability": "unknown",
                    "last_communication": self._telemetry.get(self._device_id_template.replace("{machine_id}", machine_id), {}).get("timestamp"),
                    "data_origin": "mqtt_transport", "simulated": False, "last_error": self._last_error or "broker_unavailable"}

    def read_inventory(self, machine_id: str) -> list[dict[str, Any]]:
        return []

    def diagnostics(self, machine_id: str) -> dict[str, Any]:
        return {"machine_id": machine_id, "broker_connected": self._connected.is_set(), "last_error": self._last_error,
                "data_origin": "mqtt_transport", "simulated": False}

    def read_resource(self, machine_id: str, capability: str) -> Any:
        if capability != "telemetry.read":
            raise LookupError("Capability unsupported")
        try:
            self._require_client(machine_id)
        except (OSError, TimeoutError, RuntimeError):
            pass
        with self._lock:
            return {"machine_id": machine_id, **self._telemetry.get(self._device_id_template.replace("{machine_id}", machine_id), {}), "simulated": False}

    def recover(self, machine_id: str) -> dict[str, Any]:
        self.disconnect()
        try:
            self._require_client(machine_id)
            return {"machine_id": machine_id, "connection": "connected", "verified": True, "simulated": False}
        except (OSError, TimeoutError, RuntimeError):
            return {"machine_id": machine_id, "connection": "disconnected", "verified": False, "simulated": False}

    def execute(self, machine_id: str, command_id: str, actor: str, capability: str, parameters: dict[str, Any]) -> CommandResult:
        requested = _now()
        if capability != "device.ping" or parameters:
            return CommandResult(command_id, machine_id, actor, capability, "rejected", requested, _now(), False, False, None, {}, "unsupported_command")
        try:
            client = self._require_client(machine_id)
            device_id = self.device_id
            command = {"schema_version": SCHEMA_VERSION, "command_id": command_id, "message_id": str(uuid.uuid4()),
                       "device_id": device_id, "type": "command", "capability": "device.ping", "parameters": {}}
            with self._lock:
                self._response_event.clear()
                self._pending[command_id] = command
            deadline = time.monotonic() + self.timeout
            publish = client.publish(self.command_topic, json.dumps(command, separators=(",", ":")), qos=1)
            if publish.rc != 0:
                raise ConnectionError("mqtt_publish_failed")
            # QoS 1 publication acknowledgement proves broker receipt only.
            publish.wait_for_publish(timeout=max(0, deadline - time.monotonic()))
            broker_acknowledged = publish.is_published()
            if not broker_acknowledged:
                return CommandResult(command_id, machine_id, actor, capability, "timed_out", requested, _now(), False,
                                     False, None, {"publish_queued": True, "broker_acknowledged": False}, "broker_publish_timeout")
            while time.monotonic() < deadline:
                with self._lock:
                    response = self._results.pop(command_id, None)
                if response:
                    confirmed = response["status"] == "confirmed"
                    return CommandResult(command_id, machine_id, actor, capability, response["status"], requested,
                                         _now(), False, confirmed, "device_application_ack" if confirmed else None,
                                         {**response["result"], "publish_queued": True,
                                          "broker_acknowledged": broker_acknowledged,
                                          "application_confirmed": confirmed},
                                         None if confirmed else "device_rejected_or_failed")
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    break
                self._response_event.wait(remaining)
            return CommandResult(command_id, machine_id, actor, capability, "timed_out", requested, _now(), False,
                                 False, None, {"publish_queued": True, "broker_acknowledged": broker_acknowledged,
                                              "application_confirmed": False}, "device_confirmation_timeout")
        except (OSError, TimeoutError, RuntimeError, ConnectionError):
            return CommandResult(command_id, machine_id, actor, capability, "failed", requested, _now(), False,
                                 False, None, {}, "mqtt_transport_error")
        finally:
            with self._lock:
                self._pending.pop(command_id, None)
                self._results.pop(command_id, None)
                self._response_event.clear()
