from app.audit.audit_logger import AuditLogger
from app.domain import events
from app.domain.models import Transaction
from app.domain.states import TransactionState


class RecoveryService:
    def __init__(self, audit_logger: AuditLogger) -> None:
        self.audit_logger = audit_logger

    def timeout(self, tx: Transaction, actor: str = "sensor_simulator") -> Transaction:
        tx.state = TransactionState.CANCELLED
        self.audit_logger.log(
            transaction_id=tx.transaction_id,
            event_type=events.TRANSACTION_CANCELLED,
            actor=actor,
            status="timeout",
            reason="Transacción expirada por timeout",
        )
        return tx

    def disconnect(self, tx: Transaction, actor: str = "sensor_simulator") -> Transaction:
        tx.state = TransactionState.CANCELLED
        self.audit_logger.log(
            transaction_id=tx.transaction_id,
            event_type=events.TRANSACTION_CANCELLED,
            actor=actor,
            status="device_disconnected",
            reason="Lector desconectado",
        )
        return tx

    def restart(self, tx: Transaction, actor: str = "controller") -> Transaction:
        if tx.state not in (TransactionState.COMPLETED, TransactionState.CANCELLED):
            tx.state = TransactionState.ERROR
            self.audit_logger.log(
                transaction_id=tx.transaction_id,
                event_type=events.TRANSACTION_ERROR,
                actor=actor,
                status="fail_secure",
                reason="Reinicio durante transacción activa",
            )
        return tx
