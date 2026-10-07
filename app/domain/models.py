from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from app.domain.states import TransactionState


@dataclass
class Transaction:
    transaction_id: str
    expected_amount: Decimal
    state: TransactionState = TransactionState.IDLE
    product_id: str | None = None
    paid_amount: Decimal = Decimal("0")
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class InventoryItem:
    product_id: str
    name: str
    price: Decimal
    stock: int


@dataclass
class AuditEvent:
    timestamp: datetime
    transaction_id: str | None
    event_type: str
    actor: str
    status: str
    reason: str
    metadata: dict[str, Any]
