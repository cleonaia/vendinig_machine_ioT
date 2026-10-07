from abc import ABC, abstractmethod

from app.domain.models import AuditEvent, InventoryItem, Transaction


class Repository(ABC):
    @abstractmethod
    def save_transaction(self, tx: Transaction) -> None: ...

    @abstractmethod
    def get_transaction(self, transaction_id: str) -> Transaction | None: ...

    @abstractmethod
    def list_transactions(self) -> list[Transaction]: ...

    @abstractmethod
    def save_inventory_item(self, item: InventoryItem) -> None: ...

    @abstractmethod
    def get_inventory_item(self, product_id: str) -> InventoryItem | None: ...

    @abstractmethod
    def list_inventory(self) -> list[InventoryItem]: ...

    @abstractmethod
    def save_audit_event(self, event: AuditEvent) -> None: ...

    @abstractmethod
    def list_audit_events(self) -> list[AuditEvent]: ...
