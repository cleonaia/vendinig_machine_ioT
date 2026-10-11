# Investigación de seguridad IoT autorizada

## Alcance y límites

El paquete `app.security_research` contiene dos funciones separadas: descubrimiento TCP de bajo impacto con alcance privado explícito, y evaluación determinista de perfiles sintéticos. Los perfiles no son firmware ni controladores compatibles. El nombre MDB/ICP solo señala una integración pendiente: no hay implementación del bus ni acceso a pagos o dispensación.

El descubrimiento acepta únicamente CIDR IPv4 loopback/RFC1918, hasta 64 direcciones por alcance combinado, timeout máximo de un segundo y puertos permitidos `80, 443, 1883, 8883, 502, 8080, 8443`. Solo intenta abrir TCP y cierra el socket; no autentica, publica, suscribe, escribe registros Modbus ni envía comandos vending. El número de puerto produce una sugerencia de baja confianza (0.20–0.25), no identificación demostrada. IPv6 y redes públicas se rechazan.

La evaluación MQTT/API opera sobre perfiles de laboratorio proporcionados como fixtures, no sobre hosts descubiertos. Revisa transporte, autenticación, ACL, validación, autorización, validación de entradas y exposición sensible a partir de observaciones declaradas. Para elevar estas observaciones a hallazgos reales hacen falta evidencias obtenidas en un banco autorizado: configuración efectiva, pruebas negativas de identidades, respuestas y pruebas de código. El campo `simulated` y el origen de evidencias deben conservarse en cualquier informe.

## Ejecución en macOS

Desde la raíz del repositorio:

```sh
python3 -m venv .venv
source .venv/bin/activate
python -m app.security_research.cli lab --profile iot-mqtt-insecure --json reports/iot-mqtt-insecure.json --markdown reports/iot-mqtt-insecure.md
python -m app.security_research.cli lab --profile vending-api-hardened-example
```

El laboratorio no necesita broker ni máquina física. Para discovery, indica de forma explícita el bloque privado de laboratorio del que tienes autorización; por ejemplo, loopback:

```sh
python -m app.security_research.cli discover --authorized-scope 127.0.0.1/32 --ports 1883,8080
```

La ejecución de discovery es activa (intentos TCP); usar solo loopback o un segmento privado de laboratorio autorizado. La salida marca `simulated: false` porque las conexiones serían de red real, pero contiene exclusivamente hints basados en puertos y evidencias de conexión TCP.

## Lectura de informes

Cada check contiene resultado real del motor (`actual`), resultado esperado independiente a nivel de perfil y evidencia. Las observaciones sintéticas y los hallazgos incluyen consideraciones de falso positivo y mitigación. `expectations_met` compara conjuntos independientes de IDs esperados y observados; no significa que se haya verificado un dispositivo real. Las severidades son una clasificación orientativa para el ejercicio, no una puntuación CVSS.

## Añadir un controlador de fabricante

Añade un adaptador en `app/devices/` que implemente la interfaz común de `device_adapter.py`. Documenta fabricante, modelo y revisión exactos, firmware, transporte, autenticación, fuente de cada campo y capacidad. Añade pruebas de contrato y fixtures basados en documentación oficial. Mantén como `unsupported` cada capacidad no demostrada. No extrapoles compatibilidad desde MQTT, HTTP, Modbus o MDB/ICP genéricos.

## Verificación

```sh
python -m unittest tests.test_security_research -v
python -m unittest discover -s tests -v
```

Las pruebas de este módulo usan fixtures y sockets simulados; no exploran otros hosts ni ejecutan operaciones vending.
