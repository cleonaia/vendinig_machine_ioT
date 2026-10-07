from datetime import datetime, timezone
from typing import Any

from app.audit.event_store import EventStore
from app.domain.models import AuditEvent


class AuditLogger:
    def __init__(self, event_store: EventStore) -> None:
        self.event_store = event_store

    def log(
        self,
        *,
        transaction_id: str | None,
        event_type: str,
        actor: str,
        status: str,
        reason: str,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        self.event_store.append(
            AuditEvent(
                timestamp=datetime.now(timezone.utc),
                transaction_id=transaction_id,
                event_type=event_type,
                actor=actor,
                status=status,
                reason=reason,
                metadata=metadata or {},
            )
        )

    def list_events(self) -> list[AuditEvent]:
        return self.event_store.list_events()
