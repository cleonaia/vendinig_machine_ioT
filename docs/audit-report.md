# Auditoría inicial del repositorio

Fecha de inspección: 2026-10-10.

## Hallazgos

- El repositorio original contiene una estructura Python prevista para API, dominio, servicios, persistencia, dispositivos, seguridad y pruebas, pero esos archivos estaban vacíos. `pyproject.toml`, `requirements.txt`, Docker, workflows y scripts también están vacíos; no definen dependencias, instalación, CI ni despliegue funcional.
- El único comportamiento ejecutable incorporado en el árbol de trabajo es `scenarios/lab.py` y `scenarios/run_all.py`, añadidos en cambios locales no confirmados. Modelan mensajes de pago, firma HMAC fija de entrenamiento, repetición e interrupción en memoria.
- No se encontró firmware, esquema eléctrico, controlador, modelo de máquina, dispositivo serial/USB/GPIO, cliente MQTT/HTTP/Modbus/MDB, API de fabricante, configuración de hardware ni credenciales. No se puede determinar compatibilidad ni afirmar control físico.
- No hay sensores reales, pagos reales, persistencia de ventas, inventario consultado al controlador, autenticación, roles, autorización por máquina ni auditoría administrativa. Los archivos de pruebas existentes están vacíos.
- Riesgo del simulador: `SECRET` es una clave fija conocida y no apta para producción. El perfil vulnerable desactiva deliberadamente controles. Esto solo es aceptable dentro del ejercicio local; no debe reutilizarse en producto.
- No se detectaron secretos reales en los archivos inspeccionados. La ausencia de dependencias y configuración de CI impide auditar vulnerabilidades de paquetes o hacer un análisis de firmware.

## Arquitectura observada y destino de esta entrega

Estado observado: escenarios deterministas en memoria, sin API ni persistencia. Se conserva el laboratorio y se incorpora una consola/API local aislada para administrar datos explícitamente simulados, con autenticación por token, inventario SQLite, registro de cambios y panel web técnico. No se habilita actuador ni se presenta ninguna solicitud simulada como acción física ejecutada.

## Plan priorizado

1. P0: conservar los cambios locales existentes y dejar documentado el alcance, las limitaciones y la ausencia de interfaz real.
2. P1: crear un servicio administrativo de laboratorio autenticado, ligado a loopback por defecto, con datos persistentes etiquetados como simulados y operaciones de inventario auditables.
3. P1: añadir pruebas para autenticación, validación, estado simulado e idempotencia/registro de cambios.
4. P2: añadir instrucciones reproducibles, configuración de ejemplo y criterios para integrar solo una API oficial identificada.
5. P3: con fabricante/modelo, manual de protocolo, sandbox y credenciales de prueba, implementar un adaptador concreto en modo lectura inicial; habilitar controles solo según documentación y autorización.

## Funcionalidad frente a hardware

| Capacidad | Estado actual tras la entrega | Fuente |
| --- | --- | --- |
| Estado/conexión/temperatura | Simulada | Generador local, no controlador |
| Inventario y catálogo | Gestionable en la base local | No consultado en máquina |
| Historial administrativo | Persistido localmente | No equivale a registro del controlador |
| Pagos/conciliación | No implementado | Sin terminal ni API de pagos |
| Puertas, alarmas y diagnósticos | No disponibles | Sin sensores/controlador |
| Reinicio, mantenimiento y dispensación | No disponibles | Sin interfaz oficial identificada |
| MQTT, REST, WebSocket, Modbus, MDB, serie, USB o GPIO | No confirmado ni implementado | Falta modelo y documentación del equipo |

## Estado de la segunda iteración

Se añadió una capa extensible de adaptadores y flota. `simulation.compact` y `simulation.connected` son los únicos drivers del registro, ambos declaran `simulated=true`. El primero expone estado/inventario/diagnóstico; el segundo añade sensores, alarmas, ventas, estado de pago y operaciones únicamente simuladas. FleetManager persiste registros/comandos, deduplica por máquina/UUID y registra estado no confirmado como `interrupted_unknown` tras un reinicio.

La interfaz web permite inspeccionar perfiles y capacidades, registrar máquinas y probar diagnóstico, ajustes de inventario, mantenimiento, reinicio, recuperación y dispensación sintética. La API incluye roles locales por tokens distintos: viewer, operator y admin. Registros, comandos y estado simulado se persisten en SQLite. Persisten limitaciones: bearer tokens estáticos sin expiración/rotación automatizada, sin ACL por máquina ni rate limiting. No se implementó protocolo físico. El análisis técnico de protocolos está en `docs/architecture.md`.

## Avance posterior: MQTT genérico

Se incorporó `protocol.mqtt.generic.v1` con cliente Paho MQTT 5 y `app.devices.mqtt_lab_device`, junto con esquema JSON versionado, correlación UUID, deduplicación, timeout separado entre broker y aplicación, validación de mensajes y TLS obligatorio para brokers no loopback. Las únicas capacidades anunciadas son `status.read`, `telemetry.read` y `device.ping`; no constituye integración con un controlador vending. La plataforma permite registrar máquinas con este adapter desde el panel/API y consultar telemetría.

La biblioteca `paho-mqtt` se declara como extra opcional `.[mqtt]`. En el entorno auditado no estaban instalados Paho, Mosquitto ni Docker y la descarga falló por falta de resolución DNS. Se ejecutaron pruebas unitarias de callbacks/protocolo, pero no se pudo hacer prueba de integración con broker ni hardware; consultar `docs/mqtt-protocol.md`.
