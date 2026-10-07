import json
from datetime import datetime
from decimal import Decimal
import sqlite3

from app.domain.models import AuditEvent, InventoryItem, Transaction
from app.domain.states import TransactionState
from app.storage.interfaces import Repository


class SQLiteRepository(Repository):
    def __init__(self, connection: sqlite3.Connection) -> None:
        self.conn = connection

    def save_transaction(self, tx: Transaction) -> None:
        self.conn.execute(
            """
            INSERT INTO transactions(transaction_id, expected_amount, state, product_id, paid_amount, created_at, updated_at)
            VALUES(?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(transaction_id)
            DO UPDATE SET expected_amount=excluded.expected_amount, state=excluded.state,
            product_id=excluded.product_id, paid_amount=excluded.paid_amount, updated_at=excluded.updated_at
            """,
            (
                tx.transaction_id,
                str(tx.expected_amount),
                tx.state.value,
                tx.product_id,
                str(tx.paid_amount),
                tx.created_at.isoformat(),
                tx.updated_at.isoformat(),
            ),
        )
        self.conn.commit()

    def get_transaction(self, transaction_id: str) -> Transaction | None:
        row = self.conn.execute(
            "SELECT transaction_id, expected_amount, state, product_id, paid_amount, created_at, updated_at FROM transactions WHERE transaction_id = ?",
            (transaction_id,),
        ).fetchone()
        if not row:
            return None
        return Transaction(
            transaction_id=row[0],
            expected_amount=Decimal(row[1]),
            state=TransactionState(row[2]),
            product_id=row[3],
            paid_amount=Decimal(row[4]),
            created_at=datetime.fromisoformat(row[5]),
            updated_at=datetime.fromisoformat(row[6]),
        )

    def list_transactions(self) -> list[Transaction]:
        rows = self.conn.execute(
            "SELECT transaction_id, expected_amount, state, product_id, paid_amount, created_at, updated_at FROM transactions"
        ).fetchall()
        return [
            Transaction(
                transaction_id=row[0],
                expected_amount=Decimal(row[1]),
                state=TransactionState(row[2]),
                product_id=row[3],
                paid_amount=Decimal(row[4]),
                created_at=datetime.fromisoformat(row[5]),
                updated_at=datetime.fromisoformat(row[6]),
            )
            for row in rows
        ]

    def save_inventory_item(self, item: InventoryItem) -> None:
        self.conn.execute(
            """
            INSERT INTO inventory(product_id, name, price, stock)
            VALUES(?, ?, ?, ?)
            ON CONFLICT(product_id)
            DO UPDATE SET name=excluded.name, price=excluded.price, stock=excluded.stock
            """,
            (item.product_id, item.name, str(item.price), item.stock),
        )
        self.conn.commit()

    def get_inventory_item(self, product_id: str) -> InventoryItem | None:
        row = self.conn.execute(
            "SELECT product_id, name, price, stock FROM inventory WHERE product_id = ?",
            (product_id,),
        ).fetchone()
        if not row:
            return None
        return InventoryItem(product_id=row[0], name=row[1], price=Decimal(row[2]), stock=row[3])

    def list_inventory(self) -> list[InventoryItem]:
        rows = self.conn.execute("SELECT product_id, name, price, stock FROM inventory").fetchall()
        return [InventoryItem(product_id=row[0], name=row[1], price=Decimal(row[2]), stock=row[3]) for row in rows]

    def save_audit_event(self, event: AuditEvent) -> None:
        self.conn.execute(
            """
            INSERT INTO audit_events(timestamp, transaction_id, event_type, actor, status, reason, metadata)
            VALUES(?, ?, ?, ?, ?, ?, ?)
            """,
            (
                event.timestamp.isoformat(),
                event.transaction_id,
                event.event_type,
                event.actor,
                event.status,
                event.reason,
                json.dumps(event.metadata, ensure_ascii=False),
            ),
        )
        self.conn.commit()

    def list_audit_events(self) -> list[AuditEvent]:
        rows = self.conn.execute(
            "SELECT timestamp, transaction_id, event_type, actor, status, reason, metadata FROM audit_events ORDER BY id"
        ).fetchall()
        return [
            AuditEvent(
                timestamp=datetime.fromisoformat(row[0]),
                transaction_id=row[1],
                event_type=row[2],
                actor=row[3],
                status=row[4],
                reason=row[5],
                metadata=json.loads(row[6]),
            )
            for row in rows
        ]
