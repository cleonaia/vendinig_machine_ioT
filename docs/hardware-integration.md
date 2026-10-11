# Guía para integrar una máquina real

Esta guía establece cómo añadir integración cuando se conozca el equipo. El repositorio incluye `protocol.mqtt.generic.v1` para dispositivos MQTT IoT genéricos y un dispositivo MQTT de laboratorio. **No existe adaptador de una máquina expendedora o fabricante**, y no se ha conectado ni probado equipo físico. `scenarios/lab.py` permanece como laboratorio de seguridad independiente.

## 1. Datos necesarios del equipo

Antes de escribir el driver, identifica:

- Fabricante, modelo exacto de la máquina y modelo/versión del controlador.
- Interfaz oficialmente soportada y su documentación: API local o cloud, MQTT, Modbus, MDB a través de un gateway, GPIO u otra.
- Cómo se conecta el equipo (por ejemplo, Ethernet, Wi-Fi o puerto serie) y en qué modo se permite leer o mandar órdenes.
- Qué funciones quieres: solo monitorización, inventario, alertas o también iniciar una dispensación.
- Un equipo de prueba propio/autorizado, credenciales de sandbox y procedimientos de parada segura.

Comparte modelo y documentación pública o un extracto técnico relevante. **No incluyas contraseñas, tokens, claves privadas, datos de tarjetas ni direcciones públicas de acceso**. Las credenciales de prueba se configurarán localmente, fuera del código y del control de versiones.

## 2. Dónde irá cada pieza

| Archivo | Responsabilidad prevista |
| --- | --- |
| `app/devices/device_adapter.py` | Contrato común para descriptor, capacidades, estado, inventario, diagnósticos y comandos. |
| `app/devices/registry.py` | Registro de fábricas y selección por `adapter_id`; no hay drivers de fabricante todavía. |
| `app/devices/simulator.py` | Perfiles locales `compact` y `connected`, con capacidades diferenciadas y fallos controlables. |
| `app/devices/mqtt_adapter.py` | Cliente MQTT 5 genérico: telemetría versionada y `device.ping` con confirmación correlacionada. No declara funciones vending. |
| `app/devices/mqtt_lab_device.py` | Dispositivo IoT genérico de prueba que responde `device.ping`; requiere un broker MQTT local. |
| `app/devices/<fabricante>_<modelo>.py` | Driver concreto según el protocolo documentado del equipo. Aquí se traduce el protocolo a la interfaz común. |
| `app/services/fleet_manager.py` | Registro persistente de máquinas, selección del adaptador, capacidades y motor de comandos idempotente. |
| `app/admin_server.py` | API de administración local. No contiene driver ni acciona el hardware directamente. |
| `.env.example` | Nombres y valores de ejemplo vacíos para configuración local. El archivo `.env` real debe ignorarse en Git. |
| `tests/` | Pruebas con un driver falso/simulador para errores, desconexiones, timeouts y órdenes duplicadas; las pruebas de hardware se hacen separadas en equipo de pruebas. |

El contrato, registro, simuladores, gestor de flota y transporte MQTT genérico ya existen. La ruta de fabricante sigue necesitando documentación específica y evidencia de cada capacidad.

## 3. Pasos de implementación

1. Confirmar el protocolo y las operaciones permitidas en el manual del fabricante.
2. Implementar `DeviceAdapter` y `AdapterDescriptor`, describiendo protocolo, fabricante/modelo, configuración, limitaciones y cada capacidad como disponible/no compatible/no verificada. Marca origen y verificación de datos.
3. Registrar una fábrica nueva en `AdapterRegistry`; crear una instancia separada por máquina. Añade schema/versionado del protocolo y prueba contra un simulador oficial o stub antes de dispositivo.
4. Configurar credenciales por variables de entorno/gestor de secretos. No poner contraseñas, tokens, datos de pago ni claves privadas en repositorio o registros.
5. Ejecutar comandos con UUID e idempotencia, aplicar permisos por máquina/capacidad, timeout, límites de parámetros, auditoría y verificación posterior. Los reintentos con el mismo ID no deben accionar dos veces.
6. Probar en lectura primero, después sandbox/gateway, y solo entonces en máquina propia autorizada con procedimiento de parada segura, límites físicos y recuperación documentada.
7. Documentar modelo probado, versión de firmware, protocolo, mapa/register set, interfaz eléctrica, capacidades verificadas, operación de deshabilitación y resultados.

No conectes las demostraciones de ataque del laboratorio al controlador real. Las evaluaciones sobre equipo real deben centrarse en pruebas defensivas autorizadas, con aislamiento y procedimiento del fabricante.

## 4. ¿Con el equipo ya se puede terminar el proyecto?

El modelo/manual permite **empezar el driver**, pero no basta por sí solo para completar y validar el proyecto. También hacen falta acceso autorizado al equipo o sandbox, detalles de conexión, el alcance funcional, credenciales de prueba proporcionadas de forma segura y pruebas en entorno no productivo. Si el fabricante no documenta una interfaz de control, no se debe improvisar una conexión eléctrica o protocolo: habrá que elegir un gateway compatible o limitarse a monitorización soportada.

## Requisitos físicos y por protocolo

- **API HTTP/WebSocket oficial:** documentación de endpoints, autenticación, scopes, modelo de datos, límites, eventos y sandbox. WebSocket define el canal, no el significado vending de los mensajes.
- **MQTT:** broker/gateway autorizado, certificado TLS, ACL por topics, client ID, esquema, QoS y mecanismo request/response con correlation ID y confirmación de resultado.
- **Modbus TCP/RTU:** gateway/interfaz Ethernet o RS-485 aislada según equipo, unit ID, baud/paridad para RTU, mapa de registros y definición de escalas/endianness; obtener permiso de escritura para cada registro.
- **MDB/ICP:** VMC compatible, gateway MDB-host diseñado para la capa eléctrica/temporal del bus, especificación aplicable/versión y rol maestro/periférico documentado. Un adaptador de pago MDB no proporciona API general de inventario/administración.
- **USB/serie:** pinout, voltajes, interfaz aislada si hace falta, VID/PID, protocolo/framing, velocidad, paridad, firmware y autorización del fabricante. La presencia de un puerto no prueba que sea una interfaz de control.
- **GPIO:** esquema eléctrico, aislamiento, niveles y estado fail-safe. No se contempla como camino universal de actuadores.

Ninguno de estos requisitos se conoce para el equipo de este repositorio, por eso no se incluye transporte físico ni se declaran perfiles vendor.
