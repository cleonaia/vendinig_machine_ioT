# Controles de seguridad implementados

- El servicio local requiere `VENDING_ADMIN_TOKEN` de 32 o más caracteres y compara cada bearer token en tiempo constante. Los tokens opcionales de operator/viewer deben ser distintos.
- Por defecto escucha en `127.0.0.1`; rechaza host remoto. No se debe hacer port-forward ni publicar el puerto.
- Las rutas API requieren autenticación. La pantalla tampoco se entrega sin token.
- La API requiere `Content-Type: application/json`, limita cuerpos a 4 KiB, rechaza claves JSON duplicadas/NaN, bloquea bool como entero y valida estrictamente campos y rangos. Parámetros de comandos están limitados a 2 KiB.
- Los SQL usan parámetros. Los datos originados manualmente y la telemetría simulada se etiquetan; el navegador usa `textContent` para valores del inventario.
- El resultado de cada comando y el estado local del simulador se guardan en la misma transacción SQLite.
- Se definen tres roles locales: viewer solo GET; operator puede enviar diagnósticos y recuperación; admin puede registrar máquinas y ejecutar capacidades de escritura. Cada comando se vuelve a validar contra capacidades soportadas y declaradas escribibles por el adaptador.
- Los comandos requieren UUID y se deduplican por máquina. Los registros `pending` tras reiniciar el proceso pasan a `interrupted_unknown` y no se reintentan automáticamente.
- `.env`, SQLite, entornos virtuales y bytecode se excluyen de Git.

## Límites y riesgos pendientes

- Es un conjunto de bearer tokens estáticos por rol; no implementa cuentas, sesiones revocables/expirables, MFA, rate limiting ni autorización granular por máquina. El actor de auditoría identifica el rol local, no a una persona.
- HTTP no cifra tráfico. Solo debe usarse por loopback; el acceso remoto requeriría un proxy con TLS y controles de acceso, no enlazar directamente el servicio.
- La auditoría es una bitácora local editable por quien controle el host, sin firma ni exportación inmutable.
- El token es leído desde el entorno. En una instalación multiusuario conviene usar un gestor de secretos.
- La clave fija `training-only-key` de `scenarios/lab.py` es deliberadamente conocida; solo sirve para el laboratorio.
- No hay dependencias externas, por lo que no existe inventario de paquetes de terceros que someter a análisis de vulnerabilidades. Tampoco hay suficiente información para evaluar firmware o red de un producto físico.
- La suite combina unit tests y pruebas HTTP in-process sobre `socketpair` Unix; no abre puertos TCP ni contacta hardware.
