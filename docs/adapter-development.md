# Desarrollo de adaptadores multimarca

La plataforma usa una única frontera en `app/devices/device_adapter.py`; la API, el panel y `FleetManager` no deben contener lógica específica de marca. El registro usa un `adapter_id` estable y una fábrica por dispositivo. Los adaptadores reciben solo configuración no secreta persistible; las credenciales se resuelven desde variables de entorno o un gestor de secretos.

## Estado de compatibilidad

| Integración | Estado en este repositorio | Qué demuestra |
| --- | --- | --- |
| Simuladores locales | Implementados y probados | Solo comportamiento simulado; `simulated=true`. |
| MQTT genérico | Implementado; suite unitaria probada, integración de red condicionada a broker local | Mensajería schema v1 y ping genérico; no compatibilidad vending. |
| HTTP/REST de fabricante | No implementado | Añadir solo con OpenAPI/manual oficial, scopes y sandbox/modelo autorizado. |
| WebSocket de fabricante | No implementado | WebSocket solo define transporte; añadir el protocolo de aplicación documentado. |
| TCP o serie | No implementado | Requiere mapa de mensajes, framing, interfaz/pinout, niveles eléctricos y procedimiento del fabricante. |
| Modbus RTU/TCP | No implementado | Requiere mapa de registros del controlador, escalas, permisos y gateway/interfaz adecuada. |
| MDB/ICP | No implementado | Bus VMC-periférico; requiere VMC, gateway MDB-host y especificación aplicable. No implica administración total de máquina. |

No se detecta fabricante automáticamente. Una máquina se declara compatible solo con una combinación validada de fabricante, controlador, firmware, protocolo, configuración y capacidades. `Capability.state=UNVERIFIED`/`verified=false` expresa que el peer concreto aún no se ha demostrado; `UNSUPPORTED` es la respuesta para operaciones que ese driver no implementa.

## Plantilla de fabricante

`docs/templates/vendor_adapter.py.template` es un esqueleto intencionalmente no funcional. No se importa ni registra y no anuncia soporte. Copia el archivo a `app/devices/<fabricante>_<modelo>.py`, sustituye el fabricante/modelo por los identificadores exactos documentados, elimina las operaciones que el equipo no soporta y solo implementa las demás cuando sus endpoints/frames estén respaldados por documentación oficial. No conviertas `NotImplementedError` en una respuesta de éxito.

Al registrar una implementación real, usa `AdapterRegistry.register(factory, descriptor)` y documenta:

- fabricante, modelo y revisión de controlador/firmware comprobados;
- protocolo y transporte: REST, WebSocket, MQTT, serie/TCP u otro documentado;
- configuración allowlisted y nombres de variables secretas, nunca sus valores;
- autenticación, TLS/certificados, ACL y permisos requeridos;
- cada capacidad como disponible, no verificada o no compatible, con método, fuente y modo escritura;
- timeouts acotados, reconexión, errores sanitizados, request/correlation ID e idempotencia;
- reglas de validación estricta para todos los mensajes y respuestas;
- lectura posterior o acuse oficial necesario para marcar una escritura como verificada.

## Pruebas requeridas antes de habilitar un dispositivo

1. Prueba de contrato del adaptador, su descriptor y capacidades; comprueba que ninguna capacidad ausente se informa como disponible.
2. Pruebas unitarias con cliente/transporte falso: entradas malformadas, campos extra, auth fallida, timeout, desconexión, respuesta tardía, reintento y duplicados.
3. Pruebas de integración contra sandbox/simulador oficial o dispositivo de laboratorio autorizado, verificando los mensajes físicos de ida y vuelta y los ACK/readback.
4. Pruebas de integración mediante las rutas existentes de `FleetManager`/API: roles, idempotencia persistente, auditoría y ausencia de secretos en respuestas/historial.
5. Pruebas de seguridad y límites con hardware aislado: lecturas primero, luego escritura inocua documentada, parada segura y recuperación aprobada. Nunca probar dispensación o pagos con este laboratorio.

Mantén los tests de broker real en `tests/test_mqtt_integration.py` o crea un test específico del fabricante. Las pruebas que usan mocks prueban la lógica local; solo las pruebas que se conectan al endpoint autorizado validan el intercambio de red.
