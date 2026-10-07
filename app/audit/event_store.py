from app.domain.models import AuditEvent
from app.storage.interfaces import Repository


class EventStore:
    def __init__(self, repository: Repository) -> None:
        self.repository = repository

    def append(self, event: AuditEvent) -> None:
        self.repository.save_audit_event(event)

    def list_events(self) -> list[AuditEvent]:
        return self.repository.list_audit_events()
