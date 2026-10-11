# Arquitectura de adaptadores y simulación

```text
Navegador ── HTTP loopback + Bearer ── app.admin_server
                                          └── FleetManager ── SQLite (máquinas/comandos)
                                                └── AdapterRegistry ── DeviceAdapter
                                                                         ├── Simulator: compact
                                                                         └── Simulator: connected

scenarios.run_all ── scenarios.lab (modelo independiente en memoria)
```

`app.devices.device_adapter.DeviceAdapter` define la frontera común para descriptor, capacidades, telemetría, inventario, diagnósticos y ejecución de comandos. `AdapterRegistry` selecciona una fábrica por `adapter_id`; cada máquina recibe su propia instancia de adaptador y una configuración no secreta restringida por el descriptor. Los constructores de adapters deben ser libres de I/O: conectar debe ser explícito o perezoso. `FleetManager` persiste identidad de máquinas, estado simulado y resultados de comandos en SQLite, valida capacidades antes de escribir y deduplica operaciones por `(machine_id, request_id)`. Las respuestas separan `simulated`, `verified`, `confirmation`, estado y error.

`app.admin_server` ofrece las vistas de flota y un panel para registrar adaptadores disponibles, inspeccionar capacidades y ejecutar comandos. Acepta tokens separados por los roles locales viewer, operator y admin. El servicio se mantiene enlazado a loopback; no hay cuentas, expiración de token ni política granular por máquina.

Los perfiles `simulation.compact` y `simulation.connected` tienen capacidades distintas. El segundo modela telemetría, alarmas, ventas, estado de pago, mantenimiento, reinicio, recuperación y dispensación simulada. Sus datos se originan en código local y nunca equivalen a información de un controlador real. El adaptador `protocol.mqtt.generic.v1` usa Paho MQTT 5 y el contrato de `docs/mqtt-protocol.md`: lee telemetría y solicita únicamente `device.ping`. El dispositivo `mqtt_lab_device` es un dispositivo IoT genérico de laboratorio, no una máquina expendedora. El adaptador no declara inventario, pagos, ventas o actuadores vending.

Los comandos llevan UUID, actor por rol (`local-admin`, `local-operator`), parámetros, timestamps, resultado y confirmación; reintentar el mismo UUID devuelve el registro existente sin volver a invocar el adaptador. Para MQTT, el QoS PUBACK se distingue de la confirmación de aplicación correlacionada. El estado de inventario/ventas del simulador se guarda junto con cada resultado en SQLite.

El flujo `scenarios.*` es otro programa de línea de comandos, completamente en memoria. La clave HMAC de entrenamiento es fija y solo permite reproducir los ejemplos educativos; no brinda autenticación de máquina ni debe trasladarse a producción.

No hay driver ni firmware de una expendedora. MQTT está integrado como transporte genérico, pero no se ha confirmado para un controlador de máquina concreto. MQTT y WebSocket son transportes de mensajería; REST requiere una API de fabricante; Modbus necesita mapa de registros del controlador; USB/serie requieren interfaz eléctrica y protocolo documentados. MDB/ICP comunica el VMC con periféricos de vending y pagos, y no otorga por sí solo acceso administrativo completo. La API REST de la plataforma sirve únicamente a la consola local.

## Camino de integración soportado

Para una futura máquina autorizada, registra un adaptador concreto mediante `AdapterRegistry.register(factory, descriptor)`, añade el modelo/protocolo ensayado y declara cada capacidad junto con su origen, método, estado de verificación, modo de escritura y limitación. `AdapterDescriptor` enumera campos de configuración no secretos, requisitos de autenticación, timeout por defecto, recuperación y límites conocidos. Las credenciales deben resolverse desde el entorno/gestor de secretos del adaptador y no almacenarse en el registro de máquinas. Cada transporte debe hacer cumplir su timeout y verificar la respuesta; el motor marca operaciones que cruzan un reinicio sin confirmación como `interrupted_unknown`, sin reejecutarlas. No se habilitará un actuador genérico por GPIO ni se inferirá el protocolo a partir de MDB u otros nombres de bus.

## Priorización técnica de protocolos

| Opción | Uso típico | Decisión para este repositorio |
| --- | --- | --- |
| API oficial HTTP/REST del fabricante | Administración y telemetría según el fabricante | Primera opción si el equipo tiene API documentada y sandbox. No se puede codificar antes de conocer fabricante y contrato de API. |
| MQTT | Eventos/telemetría pub-sub; request/response requiere convención de aplicación y confirmaciones | Integrado para el esquema genérico v1 y probado mediante cliente de prueba. No demuestra compatibilidad vending; TLS y autorización de broker requeridos fuera de loopback. |
| WebSocket | Canal bidireccional persistente para una API definida por aplicación | Solo cuando API oficial lo documente. No define comandos de vending por sí mismo. |
| Modbus TCP/RTU | Registros de equipos industriales/controladores | Posible a través de PLC/gateway con mapa de registros del fabricante. Sin mapa no se conocen direcciones, escalas, permisos ni escrituras seguras. |
| Serie/USB | Transporte físico hacia controlador/gateway | Requiere niveles eléctricos, pinout, baud/paridad, framing y protocolo documentados; USB no identifica el protocolo de aplicación. |
| MDB/ICP | Bus VMC-periférico, incluyendo dispositivos cashless, moneda, billetes y otros periféricos definidos | No se añade como conexión directa a PC: suele requerir hardware/gateway compatible con la capa física y un rol de bus documentado. Su soporte periférico no equivale a gestionar toda la máquina. |
| GPIO | Señales digitales discretas | No se recomienda para control universal: carece de semántica de estado/transacción y exige diseño eléctrico/seguridad específico. No implementado. |

MQTT 5.0 define transporte pub/sub y un patrón request/response de aplicación; OASIS recomienda autenticación, autorización y comunicación segura. Modbus Organization publica especificaciones separadas para aplicación, TCP y serial, y su opción Modbus Security encapsula TLS. NAMA publica MDB/ICP para comunicación entre VMC y periféricos. Referencias primarias: [OASIS MQTT 5.0](https://docs.oasis-open.org/mqtt/mqtt/v5.0/mqtt-v5.0.html), [Modbus Organization](https://www.modbus.org/modbus-specifications), [especificación NAMA MDB/ICP](https://www.namanow.org/wp-content/uploads/Multi-Drop-Bus-and-Internal-Communication-Protocol.pdf), [RFC 6455 WebSocket](https://www.rfc-editor.org/rfc/rfc6455).
