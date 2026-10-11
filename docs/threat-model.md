# Modelo de amenazas

## Activo y objetivo

El activo es el inventario del simulador. El objetivo didáctico adversario es conseguir una dispensación sin un pago válido. El modelo solo vive en memoria y usa productos y pagos ficticios.

## Límites

El emisor de pagos, el transporte, el inventario y el actuador son abstracciones locales. No se modelan redes, servicios reales, firmware, llaves de producción ni acceso físico. El perfil `vulnerable` desactiva controles en el simulador para demostrar fallos; no describe un dispositivo ni una configuración recomendada.

## Casos representados

- Repetición: se vuelve a entregar el mismo mensaje de pago.
- Manipulación: se cambia el importe después de firmar.
- Orden inválida: se altera el producto a uno fuera del catálogo.
- Interrupción: se simula un corte durante una operación.
- Cadena: se combinan repetición, manipulación e intento sin firma.

## Controles del modelo

El perfil `hardened` valida producto e importe, verifica la firma del mensaje, rechaza identificadores de pago repetidos y aborta de forma segura ante una interrupción simulada. El HMAC usa una clave fija de entrenamiento y **no** debe reutilizarse en productos reales. Este laboratorio no sustituye un análisis de amenazas de hardware o de un sistema de pagos.
