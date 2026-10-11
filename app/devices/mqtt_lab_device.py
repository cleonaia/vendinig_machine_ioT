"""Generic MQTT v1 lab device. It has no vending-machine behavior."""
from __future__ import annotations

import argparse
import json
import os
import signal
import threading
import time
import uuid

try:
    import paho.mqtt.client as mqtt
except ImportError as exc:
    raise SystemExit("Install with: pip install -e '.[mqtt]'") from exc


def make_message(message_type: str, **fields):
    return {"schema_version": 1, "message_id": str(uuid.uuid4()), "type": message_type, **fields}


def run() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--broker", default=os.getenv("VENDING_MQTT_BROKER", "127.0.0.1"))
    parser.add_argument("--port", type=int, default=int(os.getenv("VENDING_MQTT_PORT", "1883")))
    parser.add_argument("--device-id", default=os.getenv("VENDING_MQTT_DEVICE_ID", "lab-device-01"))
    args = parser.parse_args()
    root = f"devices/{args.device_id}"
    telemetry_topic, command_topic, result_topic = (root + "/telemetry", root + "/commands", root + "/results")
    stop = threading.Event()
    seen: dict[str, dict] = {}

    def connected(client, userdata, flags, reason_code, properties):
        if reason_code == 0:
            client.subscribe(command_topic, qos=1)
            client.publish(telemetry_topic, json.dumps(make_message("telemetry", device_id=args.device_id,
                           timestamp=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                           payload={"temperature_c": 22.0, "device_state": "ready"})), qos=1, retain=True)

    def message(client, userdata, msg):
        try:
            if len(msg.payload) > 4096:
                return
            def unique_pairs(items):
                result = {}
                for key, value in items:
                    if key in result:
                        raise ValueError("duplicate_key")
                    result[key] = value
                return result
            command = json.loads(msg.payload.decode("utf-8", "strict"), object_pairs_hook=unique_pairs,
                                 parse_constant=lambda _: (_ for _ in ()).throw(ValueError("invalid_number")))
            if (not isinstance(command, dict) or set(command) != {"schema_version", "command_id", "message_id", "device_id", "type", "capability", "parameters"}
                    or type(command["schema_version"]) is not int or command["schema_version"] != 1
                    or command["type"] != "command" or command["device_id"] != args.device_id
                    or command["capability"] != "device.ping" or command["parameters"] != {}):
                return
            command_id = command["command_id"]
            uuid.UUID(command_id)
            uuid.UUID(command["message_id"])
            # QoS 1 permits duplicate delivery: replay exactly the cached response.
            result = seen.get(command_id)
            if result is None:
                result = make_message("command_result", command_id=command_id, device_id=args.device_id,
                                      status="confirmed", result={"device_state": "ready", "device_id": args.device_id})
                seen[command_id] = result
            client.publish(result_topic, json.dumps(result), qos=1)
        except (ValueError, UnicodeError, KeyError, TypeError, AttributeError):
            return

    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=f"mqtt-lab-{args.device_id}", protocol=mqtt.MQTTv5)
    username, password = os.getenv("VENDING_MQTT_USERNAME"), os.getenv("VENDING_MQTT_PASSWORD")
    if username or password:
        client.username_pw_set(username or None, password or None)
    client.on_connect, client.on_message = connected, message
    client.connect(args.broker, args.port, keepalive=30)
    client.loop_start()
    signal.signal(signal.SIGINT, lambda *_: stop.set())
    signal.signal(signal.SIGTERM, lambda *_: stop.set())
    try:
        while not stop.wait(1):
            pass
    finally:
        client.disconnect()
        client.loop_stop()


if __name__ == "__main__":
    run()
