from dataclasses import dataclass, field
import time

from app.domain.errors import DomainError


@dataclass
class ReplayProtector:
    ttl_seconds: int
    used_nonces: dict[str, int] = field(default_factory=dict)

    def consume(self, nonce: str, issued_at: int) -> None:
        now = int(time.time())
        if issued_at + self.ttl_seconds < now:
            raise DomainError("Mensaje expirado", code="expired_message", status_code=400)
        if nonce in self.used_nonces:
            raise DomainError("Nonce duplicado detectado", code="replay_detected", status_code=409)
        self.used_nonces[nonce] = issued_at
        self.used_nonces = {
            key: value
            for key, value in self.used_nonces.items()
            if value + self.ttl_seconds >= now
        }
