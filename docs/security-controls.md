# Controles de seguridad

- HMAC-SHA256 con clave por variable de entorno (`HMAC_SECRET`).
- Nonce de un solo uso y expiración (`NONCE_TTL_SECONDS`).
- Validación estricta de estado para impedir dispensación sin pago autorizado.
- Auditoría con `timestamp`, `transaction_id`, `event_type`, `actor`, `status`, `reason`, `metadata`.
- Fail-secure: ante error, timeout, desconexión o reinicio no se dispensa.
