# MQTT genérico: contrato y límites

## Alcance probado por código

`MqttAdapter` usa Paho MQTT 5 (`paho-mqtt>=2.1,<3`) y se registra como `protocol.mqtt.generic.v1`. Conecta de forma perezosa, se reconecta mediante el loop de Paho, suscribe telemetría/resultados, publica con QoS 1 y limita los mensajes recibidos. JSON exige UTF-8, objeto superior, claves sin duplicados, números finitos, schema version 1 y UUIDs de mensaje. Los mensajes inválidos se descartan; los logs/errores nunca incluyen su contenido.

Un comando transita por tres hechos diferentes:

1. `publish_queued`: el cliente aceptó el envío local.
2. `broker_acknowledged`: Paho recibió PUBACK QoS 1 del broker.
3. `application_confirmed`: llegó un `command_result` válido con command ID y device ID coincidentes, dentro del plazo.

Solo el tercer hecho marca `verified=true`. El UUID se deduplica también en el historial SQLite de la flota. QoS 1 puede reenviar mensajes; un dispositivo de producción debe deduplicar command IDs de forma duradera si su efecto no es idempotente. El ejemplo de laboratorio cachea respuestas durante la vida del proceso; no es adecuado para actuar sobre hardware.

## Mensajes schema v1

Telemetry, en `devices/{machine_id}/telemetry`:

```json
{"schema_version":1,"message_id":"UUID","type":"telemetry","device_id":"lab-device-01","timestamp":"2026-01-01T00:00:00Z","payload":{"temperature_c":22.0,"device_state":"ready"}}
```

Solicitud, en `devices/{machine_id}/commands`:

```json
{"schema_version":1,"message_id":"UUID","command_id":"UUID","device_id":"lab-device-01","type":"command","capability":"device.ping","parameters":{}}
```

Confirmación, en `devices/{machine_id}/results`:

```json
{"schema_version":1,"message_id":"UUID","type":"command_result","command_id":"UUID","device_id":"lab-device-01","status":"confirmed","result":{"device_state":"ready","device_id":"lab-device-01"}}
```

El dispositivo puede contestar `rejected` o `failed`; en esos casos la operación no se marca verificada. En este esquema genérico el adapter acepta telemetría escalar allowlisted (`temperature_c`, `humidity_pct`, `uptime_s`, `signal_rssi_dbm`, `device_state`) y resultados de ping con `device_state` y `device_id`. Cada integración de fabricante debe definir/validar sus propias unidades y payloads.

## Configuración

Los campos no secretos admitidos al registrar una máquina son `broker`, `port`, `username`, `tls`, `device_id`, `telemetry_topic`, `command_topic`, `result_topic` y `ca_file`. Se admiten como strings por la API actual; `tls` acepta `true` o `false`. Para credenciales usa `VENDING_MQTT_USERNAME`/`VENDING_MQTT_PASSWORD` del entorno del proceso. Configura `VENDING_MQTT_CA_FILE` para una CA privada. No se admite contraseña en el JSON de registro. Brokers fuera de loopback requieren TLS y certificados verificados.

Topics aceptan `{machine_id}` y no admiten comodines. Ajusta configuración/topic ACL para el equipo concreto; los topics por defecto son `devices/{machine_id}/telemetry`, `/commands` y `/results`. Limita ACL del broker para que cada client ID publique/suscriba solo sus topics.

## Ejecución de laboratorio en macOS

Con Homebrew, instala/inicia un broker local si no está ya disponible:

```sh
brew install mosquitto
brew services start mosquitto
```

En el proyecto, instala la extra e inicia la API:

```sh
python3 -m pip install -e '.[mqtt]'
export VENDING_ADMIN_TOKEN="$(openssl rand -hex 32)"
python3 -m app.admin_server
```

En otra terminal (mismo entorno y variables MQTT si configuraste autenticación):

```sh
python3 -m app.devices.mqtt_lab_device --broker 127.0.0.1 --port 1883 --device-id lab-device-01
```

Autentica en el panel, selecciona `protocol.mqtt.generic.v1` y registra ID `lab-device-01` con configuración `{"device_id":"lab-device-01","broker":"127.0.0.1","port":"1883","tls":"false"}`. El dispositivo publica telemetría retenida al conectar y devuelve confirmación de `device.ping`. El panel muestra origen `mqtt_device`; inventario, ventas, pagos y dispensación no están disponibles.

## Adaptador para un fabricante

No reutilices este genérico como prueba de compatibilidad vending. Crea un `app/devices/<fabricante>_<controlador>.py` que implemente `DeviceAdapter`; aporta descriptor con fabricante, modelo, revisión firmware, protocolo, autenticación, configuración, timeouts y limitaciones. Usa una clase/schema de mensaje específica y allowlist de capacidades basada en documentación oficial. Prueba contra simulador del fabricante o gateway de laboratorio; documenta ACL, TLS, topics, unidades y fuentes. Antes de habilitar escritura, demuestra el permiso oficial y un readback/acuse del controlador para cada operación, además de idempotencia, límites, estados de error y parada segura. MDB, MQTT o Modbus por sí solos no prueban disponibilidad de datos vending ni autorización de actuadores.
