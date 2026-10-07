from copy import deepcopy

from app.domain.models import AuditEvent, InventoryItem, Transaction
from app.storage.interfaces import Repository


class MemoryRepository(Repository):
    def __init__(self) -> None:
        self.transactions: dict[str, Transaction] = {}
        self.inventory: dict[str, InventoryItem] = {}
        self.audit_events: list[AuditEvent] = []

    def save_transaction(self, tx: Transaction) -> None:
        self.transactions[tx.transaction_id] = deepcopy(tx)

    def get_transaction(self, transaction_id: str) -> Transaction | None:
        tx = self.transactions.get(transaction_id)
        return deepcopy(tx) if tx else None

    def list_transactions(self) -> list[Transaction]:
        return [deepcopy(tx) for tx in self.transactions.values()]

    def save_inventory_item(self, item: InventoryItem) -> None:
        self.inventory[item.product_id] = deepcopy(item)

    def get_inventory_item(self, product_id: str) -> InventoryItem | None:
        item = self.inventory.get(product_id)
        return deepcopy(item) if item else None

    def list_inventory(self) -> list[InventoryItem]:
        return [deepcopy(item) for item in self.inventory.values()]

    def save_audit_event(self, event: AuditEvent) -> None:
        self.audit_events.append(deepcopy(event))

    def list_audit_events(self) -> list[AuditEvent]:
        return [deepcopy(event) for event in self.audit_events]
